from fastapi import APIRouter, HTTPException, Query

import app.redis_client as rc
from app.models import PropertyIn, StatusResult
from app.ranking import recalculate_ranking

router = APIRouter(tags=["Instalações"])


@router.post(
    "/save-property",
    status_code=200,
    response_model=StatusResult,
    summary="Cadastrar ou atualizar instalação",
    description=(
        "Grava os dados da instalação e a associação com a organização. "
        "Somente classificações cujo grupo começa com COMERCIAL são aceitas. "
        "A área é opcional; quando informada, deve ser maior que zero. "
        "Alterações de organização ou área recalculam os rankings existentes."
    ),
    responses={422: {"description": "Grupo residencial ou área igual ou menor que zero."}},
)
def save_property(body: PropertyIn):
    if not body.classificationGroup.startswith("COMERCIAL"):
        raise HTTPException(
            status_code=422,
            detail=(
                f"classificationGroup '{body.classificationGroup}' não é permitida. "
                "Apenas unidades COMERCIAL_* entram no ranking."
            ),
        )
    if body.areaM2 is not None and body.areaM2 <= 0:
        raise HTTPException(status_code=422, detail="areaM2 deve ser maior que zero.")

    prop_key = f"property:{body.propertyId}"
    existing = rc.r.hgetall(prop_key)

    old_area = existing.get("areaM2")
    new_area = str(body.areaM2) if body.areaM2 is not None else None
    area_changed = old_area != new_area

    old_org_id = existing.get("organizationId")
    org_changed = old_org_id is not None and old_org_id != str(body.organizationId)

    # Se a organização mudou, limpa os dados da org anterior
    if org_changed:
        member = f"{body.propertyId:06d}"
        pipe = rc.r.pipeline()
        pipe.srem(f"org:{old_org_id}:properties", str(body.propertyId))
        for key in rc.r.scan_iter(f"consumption:{body.propertyId}:*"):
            period = key.split(":")[-1]
            pipe.zrem(f"ranking:org:{old_org_id}:{period}:perm2", member)
            pipe.zrem(f"ranking:org:{old_org_id}:{period}:consumo", member)
        pipe.execute()

    mapping: dict = {
        "name": body.name,
        "organizationId": str(body.organizationId),
    }
    if body.areaM2 is not None:
        mapping["areaM2"] = str(body.areaM2)
    else:
        rc.r.hdel(prop_key, "areaM2")

    rc.r.hset(prop_key, mapping=mapping)
    rc.r.sadd(f"org:{body.organizationId}:properties", str(body.propertyId))

    if area_changed or org_changed:
        for key in rc.r.scan_iter(f"consumption:{body.propertyId}:*"):
            period = key.split(":")[-1]
            recalculate_ranking(body.propertyId, period)

    return {"status": "ok"}


@router.delete(
    "/remove-property",
    status_code=200,
    response_model=StatusResult,
    summary="Remover instalação",
    description=(
        "Remove o cadastro da instalação, seus consumos e sua participação nos rankings de todos os períodos. "
        "organizationId é um parâmetro obrigatório da requisição; a organização vinculada é obtida do cadastro da instalação."
    ),
    responses={404: {"description": "Instalação não encontrada."}},
)
def remove_property(
    organizationId: int = Query(..., alias="organizationId", description="Identificador da organização enviado pelo cliente", examples=[3]),
    propertyId: int = Query(..., alias="propertyId", description="Identificador da instalação a remover", examples=[42]),
):
    prop = rc.r.hgetall(f"property:{propertyId}")
    if not prop:
        raise HTTPException(status_code=404, detail="Unidade não encontrada.")

    org_id = prop["organizationId"]
    consumption_keys = list(rc.r.scan_iter(f"consumption:{propertyId}:*"))
    member = f"{propertyId:06d}"

    pipe = rc.r.pipeline(transaction=True)
    pipe.delete(f"property:{propertyId}")
    pipe.srem(f"org:{org_id}:properties", str(propertyId))

    for key in consumption_keys:
        period = key.split(":")[-1]  # "YYYY-MM"
        pipe.delete(key)
        pipe.zrem(f"ranking:org:{org_id}:{period}:perm2", member)
        pipe.zrem(f"ranking:org:{org_id}:{period}:consumo", member)

    pipe.execute()
    return {"status": "ok"}

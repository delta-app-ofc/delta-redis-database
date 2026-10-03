from fastapi import APIRouter, HTTPException, Query

import app.redis_client as rc
from app.models import PropertyIn
from app.ranking import recalculate_ranking

router = APIRouter()


@router.post("/save-property", status_code=200)
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

    # Verifica se a área mudou para decidir se recalcula os rankings históricos
    old_area = existing.get("areaM2")
    new_area = str(body.areaM2) if body.areaM2 is not None else None
    area_changed = old_area != new_area

    mapping: dict = {
        "name": body.name,
        "organizationId": str(body.organizationId),
    }
    if body.areaM2 is not None:
        mapping["areaM2"] = str(body.areaM2)
    else:
        # Área não foi enviada — remove o campo se existia
        rc.r.hdel(prop_key, "areaM2")

    rc.r.hset(prop_key, mapping=mapping)
    rc.r.sadd(f"org:{body.organizationId}:properties", str(body.propertyId))

    # Se a área mudou, recalcula todos os períodos com dados desta unidade
    if area_changed:
        for key in rc.r.scan_iter(f"consumption:{body.propertyId}:*"):
            period = key.split(":")[-1]  # "YYYY-MM"
            recalculate_ranking(body.propertyId, period)

    return {"status": "ok"}


@router.delete("/remove-property", status_code=200)
def remove_property(
    organizationId: int = Query(..., alias="organizationId"),
    propertyId: int = Query(..., alias="propertyId"),
):
    prop = rc.r.hgetall(f"property:{propertyId}")
    if not prop:
        raise HTTPException(status_code=404, detail="Unidade não encontrada.")

    org_id = prop["organizationId"]
    consumption_keys = list(rc.r.scan_iter(f"consumption:{propertyId}:*"))
    member = f"{propertyId:06d}"

    pipe = rc.r.pipeline(transaction=True)
    pipe.delete(f"property:{propertyId}")
    pipe.srem(f"org:{organizationId}:properties", str(propertyId))

    for key in consumption_keys:
        period = key.split(":")[-1]  # "YYYY-MM"
        pipe.delete(key)
        pipe.zrem(f"ranking:org:{org_id}:{period}:perm2", member)
        pipe.zrem(f"ranking:org:{org_id}:{period}:consumo", member)

    pipe.execute()
    return {"status": "ok"}

from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from fastapi import APIRouter, HTTPException

import app.redis_client as rc
from app.config import POSTGRES_API_EMAIL, POSTGRES_API_PASSWORD, POSTGRES_API_URL
from app.models import SyncResult
from app.ranking import period_ttl_seconds, recalculate_ranking

router = APIRouter(tags=["Sincronização"])
SYNC_WORKERS = 8


def _positive_organization_id(value: object) -> int | None:
    """Reject missing and sentinel IDs so unassigned properties never enter an org set."""
    if value is None or isinstance(value, bool):
        return None
    try:
        organization_id = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return organization_id if organization_id > 0 else None


def _get_token() -> str:
    resp = requests.post(
        f"{POSTGRES_API_URL}/delta/auth/login",
        json={"email": POSTGRES_API_EMAIL, "password": POSTGRES_API_PASSWORD},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["accessToken"]


@router.post(
    "/sync",
    status_code=200,
    response_model=SyncResult,
    summary="Sincronizar instalações e consumo",
    description=(
        "Busca instalações comerciais e consumo diário na delta-api-postgres, "
        "atualiza os dados no Redis e recalcula os rankings do mês atual e do anterior. "
        "Deve ser executado após a atualização dos dados de consumo. Falhas individuais "
        "são retornadas em errors; se a API PostgreSQL estiver indisponível ou nenhuma "
        "instalação puder ser sincronizada, a operação retorna erro."
    ),
    responses={502: {"description": "Não foi possível consultar a API PostgreSQL ou sincronizar qualquer instalação."}},
)
def sync_from_postgres():
    """
    Busca propriedades e consumo da delta-api-postgres e popula o Redis.

    Sincroniza o mês corrente e o anterior para cobrir viradas de mês.
    Deve ser chamado após o ETL bi_etl.py (que roda às 03:00).
    """
    today = date.today()
    current_period = today.strftime("%Y-%m")
    previous_period = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

    try:
        token = _get_token()
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"{POSTGRES_API_URL}/delta/property", headers=headers, timeout=30)
        resp.raise_for_status()
        properties = []
        for item in resp.json():
            if not isinstance(item, dict) or not str(item.get("classification", "")).startswith("COMERCIAL"):
                continue
            organization_id = _positive_organization_id(item.get("organizationId"))
            if organization_id is None:
                continue
            properties.append({**item, "organizationId": organization_id})
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao buscar unidades: {e}")

    def sync_property(prop: dict) -> tuple[int, str | None]:
        pid = prop["id"]
        try:
            mapping: dict = {
                "name": prop["name"],
                "organizationId": str(prop["organizationId"]),
            }
            if prop.get("builtAreaM2"):
                mapping["areaM2"] = str(prop["builtAreaM2"])
            else:
                rc.r.hdel(f"property:{pid}", "areaM2")
            rc.r.hset(f"property:{pid}", mapping=mapping)
            rc.r.sadd(f"org:{prop['organizationId']}:properties", str(pid))

            r2 = requests.get(
                f"{POSTGRES_API_URL}/delta/analytics/consumption-daily/{pid}",
                headers=headers,
                timeout=30,
            )
            r2.raise_for_status()

            relevant = [
                d for d in r2.json()
                if d["fullDate"][:7] in (current_period, previous_period)
            ]

            if relevant:
                periods_updated: set[str] = set()
                pipe = rc.r.pipeline()
                for d in relevant:
                    period = d["fullDate"][:7]
                    day = d["fullDate"][8:10]
                    consumption_key = f"consumption:{pid}:{period}"
                    pipe.hset(consumption_key, day, str(d["totalLiters"]))
                    pipe.expire(consumption_key, period_ttl_seconds(period))
                    periods_updated.add(period)
                pipe.execute()

                for period in periods_updated:
                    recalculate_ranking(pid, period)

            return pid, None
        except Exception as e:
            return pid, str(e)

    synced = 0
    errors: list[dict] = []
    with ThreadPoolExecutor(max_workers=SYNC_WORKERS) as executor:
        futures = [executor.submit(sync_property, prop) for prop in properties]
        for future in as_completed(futures):
            pid, error = future.result()
            if error:
                errors.append({"propertyId": pid, "error": error})
            else:
                synced += 1

    errors.sort(key=lambda item: item["propertyId"])
    if properties and synced == 0:
        raise HTTPException(status_code=502, detail={"message": "Nenhuma unidade pôde ser sincronizada.", "errors": errors})

    return {"synced": synced, "total": len(properties), "errors": errors}

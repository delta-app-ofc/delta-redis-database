from datetime import date, timedelta

import requests
from fastapi import APIRouter, HTTPException

import app.redis_client as rc
from app.config import POSTGRES_API_URL
from app.ranking import period_ttl_seconds, recalculate_ranking

router = APIRouter()


@router.post("/sync", status_code=200)
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
        resp = requests.get(f"{POSTGRES_API_URL}/delta/property", timeout=30)
        resp.raise_for_status()
        properties = [
            p for p in resp.json()
            if str(p.get("classification", "")).startswith("COMERCIAL")
        ]
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao buscar unidades: {e}")

    synced = 0
    errors: list[dict] = []

    for prop in properties:
        pid = prop["id"]
        try:
            # Salva metadados da unidade
            mapping: dict = {
                "name": prop["name"],
                "organizationId": str(prop["organizationId"]),
            }
            if prop.get("builtAreaM2"):
                mapping["areaM2"] = str(prop["builtAreaM2"])
            rc.r.hset(f"property:{pid}", mapping=mapping)
            rc.r.sadd(f"org:{prop['organizationId']}:properties", str(pid))

            # Busca consumo diário
            r2 = requests.get(
                f"{POSTGRES_API_URL}/delta/analytics/consumption-daily/{pid}",
                timeout=30,
            )
            r2.raise_for_status()

            # Filtra apenas os períodos de interesse
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

            synced += 1
        except Exception as e:
            errors.append({"propertyId": pid, "error": str(e)})

    return {"synced": synced, "total": len(properties), "errors": errors}

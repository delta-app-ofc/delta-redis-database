from fastapi import APIRouter, HTTPException

import app.redis_client as rc
from app.models import ConsumptionIn
from app.ranking import period_ttl_seconds, recalculate_ranking

router = APIRouter()


@router.post("/save-consumption", status_code=200)
def save_consumption(body: ConsumptionIn):
    """
    Grava dias de consumo de uma unidade e atualiza o ranking em tempo real.

    - Aceita um ou vários dias por chamada.
    - Reenviar o mesmo dia sobrescreve (última escrita vence).
    - O dia corrente é gravado, mas ignorado no cálculo até fechar.
    - O ranking Redis é atualizado atomicamente ao final de cada período afetado.
    """
    if not rc.r.exists(f"property:{body.propertyId}"):
        raise HTTPException(status_code=404, detail="Unidade não cadastrada.")

    periods_to_update: set[str] = set()

    # Grava todos os dias em pipeline (atômico, sem round-trips extras)
    pipe = rc.r.pipeline()
    for entry in body.days:
        period = entry.date.strftime("%Y-%m")
        day = entry.date.strftime("%d")
        consumption_key = f"consumption:{body.propertyId}:{period}"
        pipe.hset(consumption_key, day, str(entry.liters))
        pipe.expire(consumption_key, period_ttl_seconds(period))
        periods_to_update.add(period)
    pipe.execute()

    # Recalcula o ranking para cada período afetado
    for period in periods_to_update:
        recalculate_ranking(body.propertyId, period)

    return {"status": "ok"}

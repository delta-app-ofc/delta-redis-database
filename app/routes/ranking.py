from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

import app.redis_client as rc

router = APIRouter()

VALID_CRITERIA = ("perm2", "consumo")


def _build_item(position: int, property_id: int, period: str) -> dict:
    """
    Monta um item do ranking a partir do Hash da unidade e do Hash de consumo.

    Todos os campos vêm dos dados gravados, não do score do ZSET,
    para garantir que os valores exibidos estejam sempre corretos.
    """
    prop = rc.r.hgetall(f"property:{property_id}")
    day_data = rc.r.hgetall(f"consumption:{property_id}:{period}")

    area_m2 = float(prop["areaM2"]) if prop.get("areaM2") else None
    today = date.today()
    year, month = int(period[:4]), int(period[5:7])

    total_liters = 0.0
    days_with_reading = 0
    for day_str, liters_str in day_data.items():
        try:
            d = date(year, month, int(day_str))
            if d < today:
                total_liters += float(liters_str)
                days_with_reading += 1
        except (ValueError, TypeError):
            continue

    media_diaria = total_liters / days_with_reading if days_with_reading else 0.0

    return {
        "position": position,
        "propertyId": property_id,
        "name": prop.get("name", ""),
        "areaM2": area_m2,
        "consumptionLiters": round(total_liters, 2),
        "litersPerM2": round(total_liters / area_m2, 2) if area_m2 else None,
        "litersPerM2PerDay": round(media_diaria / area_m2, 2) if area_m2 else None,
        "closedDaysWithReading": days_with_reading,
    }


@router.get("/get-ranking")
def get_ranking(
    organizationId: int = Query(..., alias="organizationId"),
    period: str = Query(..., alias="period"),
    criterion: str = Query("perm2", alias="criterion"),
    limit: Optional[int] = Query(None, alias="limit"),
):
    if criterion not in VALID_CRITERIA:
        raise HTTPException(status_code=422, detail="criterion deve ser 'perm2' ou 'consumo'.")

    ranking_key = f"ranking:org:{organizationId}:{period}:{criterion}"
    end = (limit - 1) if limit else -1
    ranked = rc.r.zrange(ranking_key, 0, end, withscores=True)

    # Unidades da organização sem área (informativo para o gestor)
    all_ids = rc.r.smembers(f"org:{organizationId}:properties")
    without_area = []
    for pid_str in all_ids:
        if not rc.r.hget(f"property:{pid_str}", "areaM2"):
            name = rc.r.hget(f"property:{pid_str}", "name") or ""
            without_area.append({"propertyId": int(pid_str), "name": name})

    items = [
        _build_item(i + 1, int(member), period)
        for i, (member, _) in enumerate(ranked)
    ]

    return {
        "organizationId": organizationId,
        "period": period,
        "criterion": criterion,
        "items": items,
        "withoutArea": without_area,
    }


@router.get("/get-position")
def get_position(
    organizationId: int = Query(..., alias="organizationId"),
    propertyId: int = Query(..., alias="propertyId"),
    period: str = Query(..., alias="period"),
    criterion: str = Query("perm2", alias="criterion"),
):
    if criterion not in VALID_CRITERIA:
        raise HTTPException(status_code=422, detail="criterion deve ser 'perm2' ou 'consumo'.")

    ranking_key = f"ranking:org:{organizationId}:{period}:{criterion}"
    member = f"{propertyId:06d}"

    rank = rc.r.zrank(ranking_key, member)
    if rank is None:
        raise HTTPException(
            status_code=404,
            detail="Unidade não está no ranking para este critério e período.",
        )

    score = rc.r.zscore(ranking_key, member)
    total = rc.r.zcard(ranking_key)

    return {
        "propertyId": propertyId,
        "period": period,
        "criterion": criterion,
        "position": rank + 1,
        "totalInRanking": total,
        "score": round(score, 4) if score is not None else None,
    }


@router.get("/get-best")
def get_best(
    organizationId: int = Query(..., alias="organizationId"),
    period: str = Query(..., alias="period"),
    criterion: str = Query("perm2", alias="criterion"),
):
    if criterion not in VALID_CRITERIA:
        raise HTTPException(status_code=422, detail="criterion deve ser 'perm2' ou 'consumo'.")

    ranking_key = f"ranking:org:{organizationId}:{period}:{criterion}"
    result = rc.r.zrange(ranking_key, 0, 0, withscores=True)

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Nenhuma unidade no ranking para este período.",
        )

    member, _ = result[0]
    item = _build_item(1, int(member), period)

    return {
        "organizationId": organizationId,
        "period": period,
        "criterion": criterion,
        "best": item,
    }

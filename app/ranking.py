"""
Funções de cálculo e atualização do ranking Redis.

Usado por routes/consumption.py (ao gravar consumo) e routes/properties.py
(ao mudar a área de uma unidade).
"""
import calendar
from datetime import date

import app.redis_client as rc
from app.config import MIN_COVERAGE_RATIO, RETENTION_MONTHS


def period_ttl_seconds(period: str) -> int:
    """Segundos até RETENTION_MONTHS meses após o início do período (YYYY-MM)."""
    year, month = int(period[:4]), int(period[5:7])
    expiry_month = month + RETENTION_MONTHS
    expiry_year = year + (expiry_month - 1) // 12
    expiry_month = ((expiry_month - 1) % 12) + 1
    expiry_date = date(expiry_year, expiry_month, 1)
    remaining = (expiry_date - date.today()).days
    return max(remaining * 86400, 86400)  # mínimo 1 dia


def recalculate_ranking(property_id: int, period: str) -> None:
    """
    Recalcula os scores de perm2 e consumo para uma unidade em um período.

    Regras aplicadas:
    - O dia corrente é ignorado (só dias com date < hoje entram no cálculo).
    - Unidade abaixo de MIN_COVERAGE_RATIO de dias com leitura sai dos dois ZSETs.
    - Unidade sem área sai do ZSET perm2, mas permanece no ZSET consumo.
    - Desempate no ZSET é feito pelo member (propertyId com zeros à esquerda).
    """
    prop = rc.r.hgetall(f"property:{property_id}")
    if not prop:
        return

    org_id = prop["organizationId"]
    area_m2 = float(prop["areaM2"]) if prop.get("areaM2") else None

    day_data = rc.r.hgetall(f"consumption:{property_id}:{period}")

    today = date.today()
    year, month = int(period[:4]), int(period[5:7])
    days_in_month = calendar.monthrange(year, month)[1]
    last_day = date(year, month, days_in_month)

    # Quantos dias deste período já fecharam (date < hoje)
    if today > last_day:
        total_closed = days_in_month
    elif today.year == year and today.month == month:
        total_closed = today.day - 1  # ontem e antes
    else:
        total_closed = 0  # período futuro

    # Leituras dos dias fechados
    closed_readings: dict[str, float] = {}
    for day_str, liters_str in day_data.items():
        try:
            d = date(year, month, int(day_str))
            if d < today:
                closed_readings[day_str] = float(liters_str)
        except (ValueError, TypeError):
            continue

    member = f"{property_id:06d}"
    perm2_key = f"ranking:org:{org_id}:{period}:perm2"
    consumo_key = f"ranking:org:{org_id}:{period}:consumo"
    ttl = period_ttl_seconds(period)

    pipe = rc.r.pipeline(transaction=True)

    # Sem dias fechados ou sem leituras → remove dos dois ZSETs
    if total_closed == 0 or not closed_readings:
        pipe.zrem(perm2_key, member)
        pipe.zrem(consumo_key, member)
        pipe.execute()
        return

    coverage = len(closed_readings) / total_closed
    total_liters = sum(closed_readings.values())

    # Abaixo da cobertura mínima → remove dos dois ZSETs
    if coverage < MIN_COVERAGE_RATIO:
        pipe.zrem(perm2_key, member)
        pipe.zrem(consumo_key, member)
        pipe.execute()
        return

    # ZSET consumo: score = litros totais do mês (sem média — só para ordenação)
    pipe.zadd(consumo_key, {member: total_liters})
    pipe.expire(consumo_key, ttl)

    # ZSET perm2: score = média diária / área (L/m²·dia)
    if area_m2:
        media_diaria = total_liters / len(closed_readings)
        perm2_score = media_diaria / area_m2
        pipe.zadd(perm2_key, {member: perm2_score})
        pipe.expire(perm2_key, ttl)
    else:
        pipe.zrem(perm2_key, member)

    pipe.execute()

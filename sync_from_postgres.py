"""
sync_from_postgres.py — Sincronização diária: delta-api-postgres → API Redis Ranking

Lê propriedades e consumo diário da API do PostgreSQL e grava no ranking Redis.
Deve ser executado após o ETL bi_etl.py (que atualiza a camada gold às 03:00).

Uso:
    python sync_from_postgres.py

Variáveis de ambiente (via .env):
    POSTGRES_API_URL  URL base da delta-api-postgres (ex.: http://localhost:8080)
    REDIS_API_URL     URL base desta API (padrão: http://localhost:8000)
"""
import sys
from datetime import date, timedelta

import requests

from app.config import POSTGRES_API_URL

REDIS_API_URL = "http://localhost:8000"

# Sincroniza o mês corrente e o mês anterior para cobrir viradas de mês
today = date.today()
first_of_month = today.replace(day=1)
CURRENT_PERIOD = today.strftime("%Y-%m")
PREVIOUS_PERIOD = (first_of_month - timedelta(days=1)).strftime("%Y-%m")


def get_commercial_properties() -> list[dict]:
    r = requests.get(f"{POSTGRES_API_URL}/delta/property", timeout=30)
    r.raise_for_status()
    return [p for p in r.json() if str(p.get("classification", "")).startswith("COMERCIAL")]


def get_daily_consumption(property_id: int) -> list[dict]:
    r = requests.get(
        f"{POSTGRES_API_URL}/delta/analytics/consumption-daily/{property_id}",
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def save_property(prop: dict) -> None:
    body = {
        "organizationId": prop["organizationId"],
        "propertyId": prop["id"],
        "name": prop["name"],
        "classificationGroup": prop["classification"],
    }
    if prop.get("builtAreaM2"):
        body["areaM2"] = prop["builtAreaM2"]
    requests.post(f"{REDIS_API_URL}/save-property", json=body, timeout=10).raise_for_status()


def save_consumption(property_id: int, days: list[dict]) -> None:
    relevant = [
        {"date": d["fullDate"], "liters": d["totalLiters"]}
        for d in days
        if d["fullDate"][:7] in (CURRENT_PERIOD, PREVIOUS_PERIOD)
    ]
    if not relevant:
        return
    body = {"propertyId": property_id, "days": relevant}
    requests.post(f"{REDIS_API_URL}/save-consumption", json=body, timeout=10).raise_for_status()


def main() -> None:
    print("Iniciando sincronização Postgres → Redis Ranking...")

    try:
        properties = get_commercial_properties()
    except Exception as e:
        print(f"Erro ao buscar unidades: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"  {len(properties)} unidade(s) comercial(is) encontrada(s).")
    erros = 0

    for prop in properties:
        pid = prop["id"]
        try:
            save_property(prop)
            consumption = get_daily_consumption(pid)
            save_consumption(pid, consumption)
            print(f"  OK  Unidade {pid} ({prop['name']})")
        except Exception as e:
            print(f"  ERRO  Unidade {pid}: {e}", file=sys.stderr)
            erros += 1

    print(f"Sincronização concluída. Erros: {erros}/{len(properties)}.")
    if erros:
        sys.exit(1)


if __name__ == "__main__":
    main()

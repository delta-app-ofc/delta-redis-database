"""
Testes de ranking de eficiência hídrica — delta-redis-database

Exige Redis rodando em localhost:6379 (docker compose -f docker-compose.dev.yml up -d).
"""
from datetime import date, timedelta

import pytest


# ── helpers ─────────────────────────────────────────────────────────────────

def register_property(client, org_id, prop_id, name, group="COMERCIAL_VAREJO", area=None):
    body = {
        "organizationId": org_id,
        "propertyId": prop_id,
        "name": name,
        "classificationGroup": group,
    }
    if area is not None:
        body["areaM2"] = area
    return client.post("/save-property", json=body)


def send_consumption(client, prop_id, days_dict):
    """days_dict: {"YYYY-MM-DD": liters}"""
    days = [{"date": d, "liters": l} for d, l in days_dict.items()]
    return client.post("/save-consumption", json={"propertyId": prop_id, "days": days})


# ── validação de entrada ─────────────────────────────────────────────────────

def test_residencial_rejeitado(client):
    r = register_property(client, 1, 1, "Unidade Residencial", group="RESIDENCIAL_PADRAO", area=100.0)
    assert r.status_code == 422


def test_area_zero_rejeitada(client):
    r = register_property(client, 1, 1, "Loja A", area=0)
    assert r.status_code == 422


def test_area_negativa_rejeitada(client):
    r = register_property(client, 1, 1, "Loja A", area=-50.0)
    assert r.status_code == 422


def test_consumo_sem_cadastro_retorna_404(client):
    r = send_consumption(client, 99, {"2025-01-01": 100.0})
    assert r.status_code == 404


# ── justiça por m² ───────────────────────────────────────────────────────────

def test_justica_por_m2(client):
    """
    Unidade grande (A, 3200 m²) com menor L/m²·dia deve ser 1ª no ranking perm2,
    mesmo consumindo mais litros no total do que a unidade pequena (B, 650 m²).
    """
    register_property(client, 1, 1, "Loja A - Grande", area=3200.0)
    register_property(client, 1, 2, "Loja B - Pequena", area=650.0)

    # A: 32 L/dia → 960 L/mês → perm2 = 32 / 3200 = 0.01 L/m²·dia
    # B: 21.67 L/dia → ~650 L/mês → perm2 = 21.67 / 650 ≈ 0.0333 L/m²·dia
    days_a = {f"2025-01-{d:02d}": 32.0 for d in range(1, 31)}
    days_b = {f"2025-01-{d:02d}": 21.67 for d in range(1, 31)}

    send_consumption(client, 1, days_a)
    send_consumption(client, 2, days_b)

    r = client.get("/get-ranking?organizationId=1&period=2025-01&criterion=perm2")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 2
    assert items[0]["propertyId"] == 1   # A mais eficiente (menor perm2)
    assert items[1]["propertyId"] == 2
    # A consome mais litros no total, mas ganha no perm2
    assert items[0]["consumptionLiters"] > items[1]["consumptionLiters"]


# ── justiça entre meses ──────────────────────────────────────────────────────

def test_justica_por_mes(client):
    """Mesma média diária em fev e mar deve resultar no mesmo score perm2."""
    register_property(client, 1, 1, "Loja A", area=100.0)

    # Fev 2025: 28 dias × 20 L = 560 L → média 20 L/dia → perm2 = 0.2
    days_feb = {f"2025-02-{d:02d}": 20.0 for d in range(1, 29)}
    # Mar 2025: 31 dias × 20 L = 620 L → média 20 L/dia → perm2 = 0.2
    days_mar = {f"2025-03-{d:02d}": 20.0 for d in range(1, 32)}

    send_consumption(client, 1, days_feb)
    send_consumption(client, 1, days_mar)

    r_feb = client.get("/get-position?organizationId=1&propertyId=1&period=2025-02&criterion=perm2")
    r_mar = client.get("/get-position?organizationId=1&propertyId=1&period=2025-03&criterion=perm2")

    assert r_feb.status_code == 200
    assert r_mar.status_code == 200
    assert r_feb.json()["score"] == r_mar.json()["score"]


# ── dia corrente ─────────────────────────────────────────────────────────────

def test_dia_corrente_nao_altera_score(client):
    """
    Dados do dia de hoje não devem mudar o score até o dia fechar.
    Envia dados históricos, captura o score, adiciona hoje com valor absurdo
    e verifica que o score não mudou.
    """
    register_property(client, 1, 1, "Loja A", area=100.0)
    today = date.today()
    period = today.strftime("%Y-%m")

    # Dias históricos do mês corrente (ontem e antes)
    historical = {}
    for i in range(1, today.day):
        d = date(today.year, today.month, i)
        historical[d.strftime("%Y-%m-%d")] = 20.0

    if not historical:
        pytest.skip("Primeiro dia do mês: nenhum dia fechado disponível.")

    send_consumption(client, 1, historical)
    r1 = client.get(f"/get-position?organizationId=1&propertyId=1&period={period}&criterion=perm2")

    if r1.status_code == 404:
        pytest.skip("Cobertura insuficiente para o mês corrente (início do mês).")

    score_antes = r1.json()["score"]

    # Adiciona hoje com consumo absurdo — não deve mudar o score
    send_consumption(client, 1, {today.strftime("%Y-%m-%d"): 99999.0})
    r2 = client.get(f"/get-position?organizationId=1&propertyId=1&period={period}&criterion=perm2")

    assert r2.json()["score"] == score_antes


# ── área ausente ─────────────────────────────────────────────────────────────

def test_area_null_aparece_em_without_area(client):
    """Unidade sem área não entra no perm2 e aparece em withoutArea."""
    register_property(client, 1, 1, "Loja sem área")  # sem areaM2

    r = client.get("/get-ranking?organizationId=1&period=2025-01&criterion=perm2")
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 0
    assert any(u["propertyId"] == 1 for u in data["withoutArea"])


# ── idempotência e sobrescrita ────────────────────────────────────────────────

def test_idempotencia(client):
    """Enviar os mesmos dados duas vezes não altera o score."""
    register_property(client, 1, 1, "Loja A", area=100.0)
    days = {f"2025-01-{d:02d}": 20.0 for d in range(1, 31)}

    send_consumption(client, 1, days)
    score1 = client.get("/get-position?organizationId=1&propertyId=1&period=2025-01&criterion=perm2").json()["score"]

    send_consumption(client, 1, days)
    score2 = client.get("/get-position?organizationId=1&propertyId=1&period=2025-01&criterion=perm2").json()["score"]

    assert score1 == score2


def test_sobrescrita_atualiza_score(client):
    """Reenvio do mesmo dia com valor diferente deve atualizar o score."""
    register_property(client, 1, 1, "Loja A", area=100.0)

    days_original = {f"2025-01-{d:02d}": 20.0 for d in range(1, 31)}
    send_consumption(client, 1, days_original)
    score1 = client.get("/get-position?organizationId=1&propertyId=1&period=2025-01&criterion=perm2").json()["score"]

    days_dobro = {f"2025-01-{d:02d}": 40.0 for d in range(1, 31)}
    send_consumption(client, 1, days_dobro)
    score2 = client.get("/get-position?organizationId=1&propertyId=1&period=2025-01&criterion=perm2").json()["score"]

    assert score2 == pytest.approx(score1 * 2, rel=1e-3)


# ── mudança de área ──────────────────────────────────────────────────────────

def test_mudanca_de_area_recalcula_ranking(client):
    """Alterar a área deve recalcular o score dos períodos históricos."""
    register_property(client, 1, 1, "Loja A", area=100.0)
    days = {f"2025-01-{d:02d}": 20.0 for d in range(1, 31)}
    send_consumption(client, 1, days)

    score_100 = client.get("/get-position?organizationId=1&propertyId=1&period=2025-01&criterion=perm2").json()["score"]

    # Dobra a área → score deve cair pela metade
    register_property(client, 1, 1, "Loja A", area=200.0)
    score_200 = client.get("/get-position?organizationId=1&propertyId=1&period=2025-01&criterion=perm2").json()["score"]

    assert score_200 == pytest.approx(score_100 / 2, rel=1e-3)


# ── cobertura mínima ─────────────────────────────────────────────────────────

def test_cobertura_minima(client):
    """Menos de 50% dos dias com leitura → fora do ranking."""
    register_property(client, 1, 1, "Loja A", area=100.0)

    # Janeiro 2025: 31 dias → mínimo 50% = 15,5 → precisa de ao menos 16 dias
    # Envia apenas 5 dias → abaixo do mínimo
    days_poucos = {f"2025-01-{d:02d}": 20.0 for d in range(1, 6)}
    send_consumption(client, 1, days_poucos)

    r = client.get("/get-ranking?organizationId=1&period=2025-01&criterion=perm2")
    assert len(r.json()["items"]) == 0

    # Envia dias suficientes para superar 50%
    days_suficientes = {f"2025-01-{d:02d}": 20.0 for d in range(1, 17)}
    send_consumption(client, 1, days_suficientes)

    r2 = client.get("/get-ranking?organizationId=1&period=2025-01&criterion=perm2")
    assert len(r2.json()["items"]) == 1


# ── remoção ──────────────────────────────────────────────────────────────────

def test_remocao_limpa_todas_as_chaves(client, clean_redis):
    """Remover unidade deve apagar Hash, Set, consumo e membros dos ZSETs."""
    register_property(client, 1, 1, "Loja A", area=100.0)
    days = {f"2025-01-{d:02d}": 20.0 for d in range(1, 31)}
    send_consumption(client, 1, days)

    r = client.delete("/remove-property?organizationId=1&propertyId=1")
    assert r.status_code == 200

    # Não deve aparecer no ranking
    r_rank = client.get("/get-ranking?organizationId=1&period=2025-01&criterion=perm2")
    assert len(r_rank.json()["items"]) == 0
    assert len(r_rank.json()["withoutArea"]) == 0

    # Não deve ter posição
    r_pos = client.get("/get-position?organizationId=1&propertyId=1&period=2025-01&criterion=perm2")
    assert r_pos.status_code == 404

    # Chaves Redis devem estar removidas
    assert clean_redis.exists("property:1") == 0
    assert len(clean_redis.smembers("org:1:properties")) == 0
    assert not list(clean_redis.scan_iter("consumption:1:*"))


# ── desempate por propertyId ─────────────────────────────────────────────────

def test_empate_desempate_por_property_id(client):
    """Mesmo score → desempate pelo propertyId crescente (member zero-padded)."""
    register_property(client, 1, 1, "Loja A", area=100.0)
    register_property(client, 1, 2, "Loja B", area=100.0)

    # Mesmo consumo e mesma área → mesmo perm2 score
    days = {f"2025-01-{d:02d}": 20.0 for d in range(1, 31)}
    send_consumption(client, 1, days)
    send_consumption(client, 2, days)

    r = client.get("/get-ranking?organizationId=1&period=2025-01&criterion=perm2")
    items = r.json()["items"]
    assert len(items) == 2
    # "000001" < "000002" lexicograficamente → propertyId 1 em primeiro lugar
    assert items[0]["propertyId"] == 1
    assert items[1]["propertyId"] == 2

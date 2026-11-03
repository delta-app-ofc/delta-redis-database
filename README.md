Delta | API de ranking de eficiência hídrica

![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white) ![Redis](https://img.shields.io/badge/dados-Redis-DC382D?logo=redis&logoColor=white) ![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)

Esta API mantém no Redis o ranking mensal de eficiência hídrica das unidades comerciais do Delta. Ela registra o consumo, calcula litros por metro quadrado por dia e atualiza as posições conforme recebe novas leituras.

**Tags:** `#Delta` `#Redis` `#FastAPI` `#Ranking` `#EficiênciaHídrica`

## Sumário

- [Visão geral](#visão-geral)
- [Como o ranking calcula eficiência](#como-o-ranking-calcula-eficiência)
- [Como subir](#como-subir)
- [Variáveis de ambiente](#variáveis-de-ambiente)
- [Endpoints](#endpoints)
- [Modelo de chaves](#modelo-de-chaves-no-redis)
- [Sincronização com PostgreSQL](#sincronização-com-o-postgresql)

## Visão geral

| Finalidade | Atualizar e consultar posições de eficiência hídrica por organização e mês. |
| Tecnologia | FastAPI, Redis e Python 3.12+. |
| Métrica | Consumo médio diário por área (`L/m²·dia`), calculado a partir dos dias fechados. |
| Estado do ranking | Sorted Sets no Redis, atualizados a cada envio de consumo. |

## Como o ranking calcula eficiência

O critério `perm2` divide o consumo médio diário pela área da unidade e permite comparar instalações de tamanhos diferentes:

```
consumo_medio_diario = soma(litros dos dias fechados) / dias_com_leitura
perm2                = consumo_medio_diario / area_m2       (L/m²·dia)
```

- **Menor `perm2` = 1º lugar**: menor consumo por metro quadrado ao dia.
- O cálculo usa a média diária dos dias fechados do mês.
- A leitura do dia corrente entra no ranking após o fechamento do dia.

---

## Como subir

### Requisitos

- Docker e Docker Compose
- Python 3.12+

### 1. Clone e configure o `.env`

```bash
cp .env.example .env
# configure REDIS_URL para o Redis do ambiente ou use localhost no desenvolvimento
```

### 2. Suba o Redis local para desenvolvimento

```bash
docker compose -f docker-compose.dev.yml up -d
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 4. Rode os testes em um Redis descartável

```bash
docker compose --env-file docker-compose.test.env -p delta-redis-audit-test -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from tests
docker compose --env-file docker-compose.test.env -p delta-redis-audit-test -f docker-compose.test.yml down
```

O runner instala as dependências de teste e grava os relatórios JUnit e cobertura em `reports/`. A pasta é local e ignorada pelo Git. Ele usa um Redis temporário, sem publicar porta e sem montar um arquivo `.env` local.

Para executar `pytest` diretamente, defina `TEST_REDIS_URL` para apontar a um Redis descartável: a fixture limpa o banco selecionado antes e depois de cada teste.

### 5. Suba a API

```bash
uvicorn app.main:app --reload
```

Acesse a documentação interativa em: `http://localhost:8000/docs`

---

## Variáveis de ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379` | URL de conexão com o Redis |
| `POSTGRES_API_URL` | `http://localhost:8080` | URL base da `delta-api-postgres` (para o sync) |
| `POSTGRES_API_EMAIL` | — | E-mail de acesso à `delta-api-postgres` (obrigatório para o `/sync`) |
| `POSTGRES_API_PASSWORD` | — | Senha de acesso à `delta-api-postgres` (obrigatório para o `/sync`) |
| `MIN_COVERAGE_RATIO` | `0.5` | Proporção mínima de dias com leitura para entrar no ranking |
| `RETENTION_MONTHS` | `13` | Meses de retenção dos dados no Redis |

---

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/health` | Verifica conexão com o Redis |
| `POST` | `/save-property` | Cadastra ou atualiza uma unidade |
| `DELETE` | `/remove-property` | Remove uma unidade e todos os seus dados |
| `POST` | `/save-consumption` | Grava consumo e atualiza o ranking em tempo real |
| `POST` | `/sync` | Busca unidades e consumo da delta-api-postgres e popula o Redis |
| `GET` | `/get-ranking` | Lista o ranking de uma organização em um mês |
| `GET` | `/get-position` | Posição de uma unidade no ranking |
| `GET` | `/get-best` | Primeira colocada (card "Unidade mais eficiente") |

### Exemplos com curl

**Cadastrar unidade:**
```bash
curl -X POST http://localhost:8000/save-property \
  -H "Content-Type: application/json" \
  -d '{"organizationId": 1, "propertyId": 5, "name": "Loja Swift · Moema", "classificationGroup": "COMERCIAL_VAREJO", "areaM2": 650.0}'
```

**Registrar consumo (atualiza ranking em tempo real):**
```bash
curl -X POST http://localhost:8000/save-consumption \
  -H "Content-Type: application/json" \
  -d '{"propertyId": 5, "days": [{"date": "2026-10-01", "liters": 130.0}, {"date": "2026-10-02", "liters": 125.0}]}'
```

**Consultar ranking:**
```bash
curl "http://localhost:8000/get-ranking?organizationId=1&period=2026-10&criterion=perm2"
```

**Consultar melhor unidade:**
```bash
curl "http://localhost:8000/get-best?organizationId=1&period=2026-10&criterion=perm2"
```

---

## Modelo de chaves no Redis

| Chave | Tipo | Conteúdo |
|---|---|---|
| `property:{propertyId}` | Hash | `name`, `organizationId`, `areaM2` |
| `org:{organizationId}:properties` | Set | IDs das unidades da organização |
| `consumption:{propertyId}:{YYYY-MM}` | Hash | campo = dia (`01`..`31`), valor = litros |
| `ranking:org:{organizationId}:{YYYY-MM}:perm2` | ZSET | member = ID com zeros à esquerda, score = L/m²·dia |
| `ranking:org:{organizationId}:{YYYY-MM}:consumo` | ZSET | score = média diária de litros |

---

## Sincronização com o PostgreSQL

O endpoint `POST /sync` busca unidades comerciais e consumo diário da `delta-api-postgres` e carrega esses dados no Redis:

```bash
curl -X POST http://localhost:8000/sync
```

Deve ser chamado após o ETL `bi_etl.py` (que roda às 03:00). Sincroniza o mês corrente e o anterior para cobrir viradas de mês. A resposta mostra quantas unidades foram sincronizadas e eventuais erros por unidade:

```json
{"synced": 42, "total": 42, "errors": []}
```

---

Os testes usam `TEST_REDIS_ISOLATED=1`, definido pelo Compose e pelo CI, para identificar o Redis descartável da suíte.

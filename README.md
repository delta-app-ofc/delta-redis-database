Delta | API de ranking de eficiÃªncia hÃ­drica

![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white) ![Redis](https://img.shields.io/badge/dados-Redis-DC382D?logo=redis&logoColor=white) ![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)

Esta API mantÃ©m no Redis o ranking mensal de eficiÃªncia hÃ­drica das unidades comerciais do Delta. Ela registra o consumo, calcula litros por metro quadrado por dia e atualiza as posiÃ§Ãµes conforme recebe novas leituras.

**Tags:** `#Delta` `#Redis` `#FastAPI` `#Ranking` `#EficiÃªnciaHÃ­drica`

## SumÃ¡rio

- [VisÃ£o geral](#visÃ£o-geral)
- [Como o ranking calcula eficiÃªncia](#como-o-ranking-calcula-eficiÃªncia)
- [Como subir](#como-subir)
- [VariÃ¡veis de ambiente](#variÃ¡veis-de-ambiente)
- [Endpoints](#endpoints)
- [Modelo de chaves](#modelo-de-chaves-no-redis)
- [SincronizaÃ§Ã£o com PostgreSQL](#sincronizaÃ§Ã£o-com-o-postgresql)

## VisÃ£o geral

| Finalidade | Atualizar e consultar posiÃ§Ãµes de eficiÃªncia hÃ­drica por organizaÃ§Ã£o e mÃªs. |
| Tecnologia | FastAPI, Redis e Python 3.12+. |
| MÃ©trica | Consumo mÃ©dio diÃ¡rio por Ã¡rea (`L/mÂ²Â·dia`), calculado a partir dos dias fechados. |
| Estado do ranking | Sorted Sets no Redis, atualizados a cada envio de consumo. |

## Como o ranking calcula eficiÃªncia

O critÃ©rio `perm2` divide o consumo mÃ©dio diÃ¡rio pela Ã¡rea da unidade e permite comparar instalaÃ§Ãµes de tamanhos diferentes:

```
consumo_medio_diario = soma(litros dos dias fechados) / dias_com_leitura
perm2                = consumo_medio_diario / area_m2       (L/mÂ²Â·dia)
```

- **Menor `perm2` = 1Âº lugar**: menor consumo por metro quadrado ao dia.
- O cÃ¡lculo usa a mÃ©dia diÃ¡ria dos dias fechados do mÃªs.
- A leitura do dia corrente entra no ranking apÃ³s o fechamento do dia.

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

### 3. Instale as dependÃªncias

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 4. Rode os testes em um Redis descartÃ¡vel

```bash
docker compose --env-file docker-compose.test.env -p delta-redis-audit-test -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from tests
docker compose --env-file docker-compose.test.env -p delta-redis-audit-test -f docker-compose.test.yml down
```

O runner instala as dependÃªncias de teste e grava os relatÃ³rios JUnit e cobertura em `reports/`. A pasta Ã© local e ignorada pelo Git. Ele usa um Redis temporÃ¡rio, sem publicar porta e sem montar um arquivo `.env` local.

Para executar `pytest` diretamente, defina `TEST_REDIS_URL` para apontar a um Redis descartÃ¡vel: a fixture limpa o banco selecionado antes e depois de cada teste.

### 5. Suba a API

```bash
uvicorn app.main:app --reload
```

Acesse a documentaÃ§Ã£o interativa em: `http://localhost:8000/docs`

---

## VariÃ¡veis de ambiente

| VariÃ¡vel | PadrÃ£o | DescriÃ§Ã£o |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379` | URL de conexÃ£o com o Redis |
| `POSTGRES_API_URL` | `http://localhost:8080` | URL base da `delta-api-postgres` (para o sync) |
| `POSTGRES_API_EMAIL` | â€” | E-mail de acesso Ã  `delta-api-postgres` (obrigatÃ³rio para o `/sync`) |
| `POSTGRES_API_PASSWORD` | â€” | Senha de acesso Ã  `delta-api-postgres` (obrigatÃ³rio para o `/sync`) |
| `MIN_COVERAGE_RATIO` | `0.5` | ProporÃ§Ã£o mÃ­nima de dias com leitura para entrar no ranking |
| `RETENTION_MONTHS` | `13` | Meses de retenÃ§Ã£o dos dados no Redis |

---

## Endpoints

| MÃ©todo | Rota | DescriÃ§Ã£o |
|---|---|---|
| `GET` | `/health` | Verifica conexÃ£o com o Redis |
| `POST` | `/save-property` | Cadastra ou atualiza uma unidade |
| `DELETE` | `/remove-property` | Remove uma unidade e todos os seus dados |
| `POST` | `/save-consumption` | Grava consumo e atualiza o ranking em tempo real |
| `POST` | `/sync` | Busca unidades e consumo da delta-api-postgres e popula o Redis |
| `GET` | `/get-ranking` | Lista o ranking de uma organizaÃ§Ã£o em um mÃªs |
| `GET` | `/get-position` | PosiÃ§Ã£o de uma unidade no ranking |
| `GET` | `/get-best` | Primeira colocada (card "Unidade mais eficiente") |

### Exemplos com curl

**Cadastrar unidade:**
```bash
curl -X POST http://localhost:8000/save-property \
  -H "Content-Type: application/json" \
  -d '{"organizationId": 1, "propertyId": 5, "name": "Loja Swift Â· Moema", "classificationGroup": "COMERCIAL_VAREJO", "areaM2": 650.0}'
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

| Chave | Tipo | ConteÃºdo |
|---|---|---|
| `property:{propertyId}` | Hash | `name`, `organizationId`, `areaM2` |
| `org:{organizationId}:properties` | Set | IDs das unidades da organizaÃ§Ã£o |
| `consumption:{propertyId}:{YYYY-MM}` | Hash | campo = dia (`01`..`31`), valor = litros |
| `ranking:org:{organizationId}:{YYYY-MM}:perm2` | ZSET | member = ID com zeros Ã  esquerda, score = L/mÂ²Â·dia |
| `ranking:org:{organizationId}:{YYYY-MM}:consumo` | ZSET | score = mÃ©dia diÃ¡ria de litros |

---

## SincronizaÃ§Ã£o com o PostgreSQL

O endpoint `POST /sync` busca unidades comerciais e consumo diÃ¡rio da `delta-api-postgres` e carrega esses dados no Redis:

```bash
curl -X POST http://localhost:8000/sync
```

Deve ser chamado apÃ³s o ETL `bi_etl.py` (que roda Ã s 03:00). Sincroniza o mÃªs corrente e o anterior para cobrir viradas de mÃªs. A resposta mostra quantas unidades foram sincronizadas e eventuais erros por unidade:

```json
{"synced": 42, "total": 42, "errors": []}
```

---

Os testes usam `TEST_REDIS_ISOLATED=1`, definido pelo Compose e pelo CI, para identificar o Redis descartÃ¡vel da suÃ­te.
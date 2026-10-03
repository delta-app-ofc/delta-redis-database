# delta-redis-database — API de Ranking Redis

API FastAPI que mantém no **Redis** o ranking de eficiência hídrica das instalações comerciais do Projeto Delta, por organização e mês.

> **Requisito BD2 atendido:** o Redis é usado para ranking em tempo real — cada `POST /save-consumption` atualiza os Sorted Sets atomicamente, sem nenhum job em lote.

---

## Por que L/m²·dia e não litros totais?

Comparar consumo bruto entre unidades de tamanhos diferentes é injusto. Uma loja de 3.200 m² **sempre** vai consumir mais do que uma de 650 m², mesmo sendo mais eficiente. O critério `perm2` corrige isso:

```
consumo_medio_diario = soma(litros dos dias fechados) / dias_com_leitura
perm2                = consumo_medio_diario / area_m2       (L/m²·dia)
```

- **Menor `perm2` = 1º lugar** (consome menos por m², por dia).
- Usa média por dia (não total do mês) para tratar fevereiro e março com justiça.
- O dia corrente não entra no cálculo até fechar — um dia parcial inflaria a eficiência.

---

## Como subir

### Requisitos

- Docker e Docker Compose
- Python 3.12+

### 1. Clone e configure o `.env`

```bash
cp .env.example .env
# edite .env com REDIS_URL real (Redis Cloud) ou deixe localhost para dev
```

### 2. Suba o Redis local para desenvolvimento e testes

```bash
docker compose -f docker-compose.dev.yml up -d
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 4. Rode os testes

```bash
python -m pytest -q
```

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
| `ranking:org:{organizationId}:{YYYY-MM}:consumo` | ZSET | score = litros totais do mês |

---

## Sincronização com o PostgreSQL

O endpoint `POST /sync` busca dados da `delta-api-postgres` e popula o Redis diretamente:

```bash
curl -X POST http://localhost:8000/sync
```

Deve ser chamado após o ETL `bi_etl.py` (que roda às 03:00). Sincroniza o mês corrente e o anterior para cobrir viradas de mês. A resposta inclui quantas unidades foram sincronizadas e eventuais erros por unidade.

---

## Evolução futura (fora do escopo atual)

- Endpoint de consumo em lote por organização (P9 do TASK.md).
- Normalização por turnos e dias de operação.
- Atualização intradiária via Mongo (o `POST /save-consumption` já suporta, basta ligar o produtor).

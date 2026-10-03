# AGENTS.md — Contexto do repositório `delta-redis-database`

Este arquivo orienta agentes de IA e pessoas desenvolvedoras que atuem neste repositório. Antes de alterar qualquer arquivo, confirme o estado da branch, leia as instruções locais e inspecione a implementação disponível. Não transforme intenções descritas na documentação em funcionalidades supostamente existentes.

## 1. Visão geral do Projeto Delta

O Projeto Delta é uma plataforma acadêmica de monitoramento inteligente do consumo de água residencial. Dispositivos IoT instalados em hidrômetros coletam pulsos para que a solução consolide consumo, detecte vazamentos, estime gastos e apresente informações por aplicações web e mobile, além de um chatbot.

A organização `delta-app-ofc` mantém repositórios Git independentes para documentação, bancos de dados e demais partes da solução:

- **PostgreSQL** (`delta-sql-database`): dados cadastrais e transacionais.
- **MongoDB** (`delta-mongo-database`): telemetria IoT e dados de aplicação.
- **Redis** (`delta-redis-database`): este repositório — ranking de eficiência em tempo real.
- **Neo4j** (`delta-neo4j`): grafo de relações entre entidades.

## 2. Contexto deste repositório

O `delta-redis-database` implementa a **API de Ranking Redis** do Projeto Delta: uma API FastAPI que mantém no Redis o ranking de eficiência hídrica (`L/m²·dia`) das instalações comerciais por organização e mês.

O critério principal é o **consumo médio diário por m² de área construída (L/m²·dia)**, chamado `perm2`. O ranking é atualizado em tempo real a cada registro de consumo, usando Redis Sorted Sets — sem batch, sem delay.

### Estrutura atual

```text
.
├── app/
│   ├── main.py           # FastAPI app
│   ├── config.py         # variáveis de ambiente
│   ├── redis_client.py   # conexão Redis
│   ├── models.py         # modelos Pydantic
│   ├── ranking.py        # lógica de cálculo e atualização dos ZSETs
│   └── routes/
│       ├── health.py     # GET /health
│       ├── properties.py # POST /save-property, DELETE /remove-property
│       ├── consumption.py# POST /save-consumption
│       └── ranking.py    # GET /get-ranking, /get-position, /get-best
├── tests/
│   ├── conftest.py       # fixtures pytest (Redis de teste)
│   └── test_ranking.py   # suite completa de testes
├── sync_from_postgres.py # carga diária a partir da delta-api-postgres
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
├── docker-compose.dev.yml
├── .env.example
├── .github/workflows/trigger_actions.yml
├── AGENTS.md
├── TASK.md
└── README.md
```

## 3. Leitura obrigatória do `TASK.md`

Antes de executar qualquer tarefa, leia integralmente o `TASK.md` da raiz deste repositório. Seus critérios de aceite, limites e ordem de execução fazem parte obrigatória do escopo.

Não crie, copie ou improvise um `TASK.md`. Se ele não existir, trabalhe somente a partir da tarefa fornecida explicitamente.

## 4. Padrão de branches e commits

Siga as convenções definidas em `delta-handbook/DEVOPS/convencoes-desenvolvimento.md`.

```text
<tipo>/<descricao-da-alteracao>
```

| Tipo | Uso |
| --- | --- |
| `feat` | Nova funcionalidade |
| `fix` | Correção de bug |
| `refactor` | Refatoração |
| `docs` | Alteração de documentação |
| `test` | Criação ou manutenção de testes |
| `style` | Alteração de estilização |

Os commits seguem Conventional Commits no formato `<tipo>: descrição`.

## 5. Padrão de documentação

Ao criar ou atualizar arquivos Markdown:

- Comece com título principal claro usando `#`.
- Apresente objetivo e contexto antes dos detalhes operacionais.
- Organize em seções `##` e subseções `###` em ordem lógica.
- Use listas para responsabilidades, regras e etapas.
- Use tabelas quando houver comparação ou mapeamento.
- Escreva em português claro, objetivo e tecnicamente correto.
- Diferencie o que já foi implementado do que está planejado.

## 6. Limites de atuação

- Não invente endpoints, estruturas de dados, integrações ou dependências não registradas no `TASK.md`.
- Não suponha a estrutura interna de outros repositórios do Projeto Delta.
- Não versione `.env`, credenciais, tokens ou strings de conexão.
- Restrinja alterações aos arquivos e ao repositório definidos pela tarefa.
- Não altere o modelo de chaves do Redis sem revisar o `TASK.md` (seção 4).

## 7. Limite de complexidade e nível técnico

As soluções devem ser compatíveis com o conhecimento de estudantes do Ensino Médio Técnico em Análise e Desenvolvimento de Sistemas.

- Priorize código simples, legível e dividido em pequenas responsabilidades.
- Utilize os recursos já presentes no repositório e conhecidos pela equipe.
- Não adicione frameworks ou padrões arquiteturais sem necessidade comprovada.

### Stack e nível de aprofundamento da equipe

| Tecnologia ou assunto | Nível atual | Limite esperado |
| --- | --- | --- |
| Python | Intermediário | Avançado |
| FastAPI | Básico | Intermediário |
| Redis (Sorted Sets, Hashes, Sets) | Básico | Intermediário |
| pytest | Básico | Intermediário |
| Docker e docker-compose | Básico | Intermediário |
| APIs REST | Intermediário | Intermediário |

## 8. Aviso de manutenção

A seção **Estrutura atual** deve ser revisada e atualizada após commits oficiais que adicionem, removam ou reorganizem arquivos. Compare sempre com a árvore real da `main` antes de atualizar.

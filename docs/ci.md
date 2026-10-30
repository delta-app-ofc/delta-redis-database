# CI técnico

O workflow `Testes técnicos` executa a suíte pytest em pull requests e também pode ser iniciado manualmente. Ele instala as dependências em Python 3.12 e utiliza um serviço Redis 7 isolado no runner. A suíte verifica os endpoints e o ranking com Redis real; os testes de sincronização simulam as respostas da API PostgreSQL, portanto não validam essa integração real. Um teste pode ser ignorado no começo do mês por falta de dias fechados.

## Execução local

Com Python 3.12, Docker e Docker Compose instalados:

```bash
docker compose -f docker-compose.dev.yml up -d
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
docker compose -f docker-compose.dev.yml down
```

Os testes limpam o banco lógico 1 do Redis em `localhost:6379` antes e depois de cada teste. Use uma instância local descartável, sem dados que precisem ser preservados.

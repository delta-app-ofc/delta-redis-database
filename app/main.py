from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import consumption, health, properties, ranking, sync

app = FastAPI(
    title="Delta Ranking API",
    description=(
        "Ranking de eficiência hídrica (L/m²·dia) por organização e mês. "
        "O ranking é atualizado em tempo real via Redis Sorted Sets a cada "
        "registro de consumo — sem batch, sem delay."
    ),
    version="1.0.0",
    openapi_tags=[
        {"name": "Saúde", "description": "Disponibilidade da API e conexão com o Redis."},
        {"name": "Instalações", "description": "Cadastro, atualização e remoção das instalações usadas no ranking."},
        {"name": "Consumo", "description": "Registro de leituras diárias e atualização do ranking."},
        {"name": "Ranking", "description": "Consulta das classificações por organização, mês e critério."},
        {"name": "Sincronização", "description": "Carga de instalações e consumo a partir da API PostgreSQL."},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://delta-web-app.onrender.com",
    ],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health.router)
app.include_router(properties.router)
app.include_router(consumption.router)
app.include_router(ranking.router)
app.include_router(sync.router)

from fastapi import FastAPI

from app.routes import consumption, health, properties, ranking

app = FastAPI(
    title="Delta Ranking API",
    description=(
        "Ranking de eficiência hídrica (L/m²·dia) por organização e mês. "
        "O ranking é atualizado em tempo real via Redis Sorted Sets a cada "
        "registro de consumo — sem batch, sem delay."
    ),
    version="1.0.0",
)

app.include_router(health.router)
app.include_router(properties.router)
app.include_router(consumption.router)
app.include_router(ranking.router)

from fastapi import APIRouter, HTTPException
from app.models import StatusResult

import app.redis_client as rc

router = APIRouter(tags=["Saúde"])


@router.get(
    "/health",
    response_model=StatusResult,
    summary="Verificar a saúde da API",
    description="Confirma que a API consegue executar PING no Redis.",
    responses={503: {"description": "Redis indisponível."}},
)
def health():
    try:
        rc.r.ping()
        return {"status": "ok"}
    except Exception:
        raise HTTPException(status_code=503, detail="Redis indisponível.")

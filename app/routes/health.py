from fastapi import APIRouter, HTTPException

import app.redis_client as rc

router = APIRouter()


@router.get("/health")
def health():
    try:
        rc.r.ping()
        return {"status": "ok"}
    except Exception:
        raise HTTPException(status_code=503, detail="Redis indisponível.")

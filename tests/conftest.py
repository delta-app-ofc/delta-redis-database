import os

import pytest
import redis
from fastapi.testclient import TestClient

import app.redis_client as redis_client
from app.main import app

# Usa o banco 1 do Redis local para não interferir com dados de desenvolvimento
TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/1")


@pytest.fixture(autouse=True)
def clean_redis():
    """Limpa o banco de testes antes e depois de cada teste."""
    if os.getenv("TEST_REDIS_ISOLATED") != "1":
        raise RuntimeError("Use o Compose de testes ou um Redis descartavel com TEST_REDIS_ISOLATED=1")
    r = redis.from_url(TEST_REDIS_URL, decode_responses=True)
    r.flushdb()
    yield r
    r.flushdb()


@pytest.fixture
def client(clean_redis, monkeypatch):
    """TestClient com o Redis substituído pelo banco de testes."""
    monkeypatch.setattr(redis_client, "r", clean_redis)
    return TestClient(app)

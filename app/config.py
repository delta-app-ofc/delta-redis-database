import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
POSTGRES_API_URL = os.getenv("POSTGRES_API_URL", "http://localhost:8080")

MIN_COVERAGE_RATIO = float(os.getenv("MIN_COVERAGE_RATIO", "0.5"))
RETENTION_MONTHS = int(os.getenv("RETENTION_MONTHS", "13"))

import redis as redis_lib

from app.config import REDIS_URL

r = redis_lib.from_url(REDIS_URL, decode_responses=True)

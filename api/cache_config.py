import os
import redis.asyncio as redis
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

async def init_cache():
    # Initialize connection pool for redis
    redis_client = redis.from_url(REDIS_URL, encoding="utf8", decode_responses=True)
    FastAPICache.init(RedisBackend(redis_client), prefix="fastapi-cache")

async def close_cache():
    # Optional cleanup if needed (fastapi-cache doesn't have an explicit close for redis, but good practice)
    pass

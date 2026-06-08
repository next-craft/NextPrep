import logging

from fastapi import Request
from redis.asyncio import Redis, from_url

from app.core.config import REDIS_URL

logger = logging.getLogger(__name__)


def create_redis() -> Redis:
    """Build a standalone client for non-request-scoped contexts (app lifespan,
    APScheduler jobs). Routes should use `Depends(get_redis)` / `app.state.redis` instead."""
    return from_url(REDIS_URL, decode_responses=True)


async def get_redis(request: Request):
    yield request.app.state.redis

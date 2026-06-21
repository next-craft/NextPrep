import logging

from fastapi import HTTPException, Request
from redis.asyncio import Redis, from_url

from app.core.config import REDIS_URL

logger = logging.getLogger(__name__)


def create_redis() -> Redis:
    """Build a standalone client for non-request-scoped contexts (app lifespan,
    APScheduler jobs). Routes should use `Depends(get_redis)` / `app.state.redis` instead."""
    return from_url(REDIS_URL, decode_responses=True)


async def get_redis(request: Request):
    yield request.app.state.redis


async def enforce_rate_limit(redis, key: str, limit: int, ttl_seconds: int) -> None:
    """Fixed-window per-key rate limit: increment the counter (setting the TTL on the
    first hit) and raise 429 once it exceeds `limit` within the window.

    Fails OPEN: if Redis is unavailable the request is allowed. These are anti-abuse
    limits on core user actions (creating a listing/conversation), not security-critical
    controls like the passkey limiter — so availability is favoured, matching the chat
    rate limiter. The 429 is raised outside the try so a Redis outage can't swallow it."""
    try:
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, ttl_seconds)
    except Exception as e:
        logger.warning("Rate-limit check failed open for key=%s: %s", key, str(e))
        return
    if count > limit:
        raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")

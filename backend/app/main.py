from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from app.core.config import FRONTEND_URL, ENVIRONMENT
from app.core.redis import create_redis
from app.jobs.scheduler import scheduler
from app.routers import chat, listings, payments, users
import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = create_redis()
    scheduler.start()
    yield
    scheduler.shutdown()
    await app.state.redis.aclose()


app = FastAPI(title="SMEI API", docs_url="/docs" if ENVIRONMENT == "development" else None, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(listings.router, prefix="/v1")
app.include_router(payments.router, prefix="/v1")
app.include_router(payments.status_router, prefix="/v1")
app.include_router(users.router, prefix="/v1")
app.include_router(chat.router, prefix="/v1")


def _custom_openapi():
    """Add a Bearer (JWT) security scheme so Swagger shows the global Authorize button.
    verify_token still reads the token from the `Authorization` header exactly as before —
    this only documents the scheme for the docs UI, so it does not change request handling."""
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version="1.0.0", routes=app.routes)
    schema.setdefault("components", {})["securitySchemes"] = {
        "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
    }
    schema["security"] = [{"BearerAuth": []}]
    app.openapi_schema = schema
    return schema


app.openapi = _custom_openapi

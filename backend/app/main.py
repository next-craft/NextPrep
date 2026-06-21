from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from app.core.config import FRONTEND_URL, ENVIRONMENT
from app.core.logging import configure_logging
from app.core.redis import create_redis
from app.jobs.scheduler import scheduler
from app.routers import chat, listings, reports, transactions, users
import logging

configure_logging()  # ensure app.* audit logs (transactions, JWT/Redis failures) are emitted
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = create_redis()
    scheduler.start()
    yield
    scheduler.shutdown()
    await app.state.redis.aclose()


_DEV = ENVIRONMENT == "development"
# In production every schema/docs surface is disabled (not just /docs): /redoc and the
# raw /openapi.json would otherwise leak the full API shape.
app = FastAPI(
    title="SMEI API",
    docs_url="/docs" if _DEV else None,
    redoc_url="/redoc" if _DEV else None,
    openapi_url="/openapi.json" if _DEV else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request, call_next):
    """Defense-in-depth response headers for the JSON API (the frontend sets its own
    CSP/X-Frame-Options via next.config.js)."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if ENVIRONMENT != "development":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response

app.include_router(listings.router, prefix="/v1")
app.include_router(transactions.router, prefix="/v1")
app.include_router(users.router, prefix="/v1")
app.include_router(chat.router, prefix="/v1")
app.include_router(reports.router, prefix="/v1")


@app.get("/health", include_in_schema=False)
async def health():
    """Liveness probe for Railway healthcheck. Unconditional and PII-free,
    so it survives the production flag that disables /docs."""
    return {"status": "ok"}


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

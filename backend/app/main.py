from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import FRONTEND_URL, ENVIRONMENT
from app.core.redis import create_redis
from app.jobs.scheduler import scheduler
from app.routers import listings, payments, users
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

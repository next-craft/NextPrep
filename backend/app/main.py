from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import FRONTEND_URL, ENVIRONMENT
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="SMEI API", docs_url="/docs" if ENVIRONMENT == "development" else None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

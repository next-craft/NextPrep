import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
# Fail secure: default to production so a deploy that forgets to set ENVIRONMENT does
# NOT silently enable /docs, /openapi.json, and SQL echo (which would log user rows).
# Local development must set ENVIRONMENT=development explicitly.
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")

_REQUIRED = [
    "NEXT_PUBLIC_SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "DATABASE_URL",
    "REDIS_URL",
    "RESEND_API_KEY",
    # Image upload is a core feature — fail fast at boot rather than at first upload.
    "CLOUDINARY_CLOUD_NAME",
    "CLOUDINARY_API_KEY",
    "CLOUDINARY_API_SECRET",
]
_missing = [k for k in _REQUIRED if not os.getenv(k)]
if _missing:
    raise RuntimeError(f"Missing required environment variables: {', '.join(_missing)}")

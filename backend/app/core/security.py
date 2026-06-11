from fastapi import Header, HTTPException
from jose import jwt, JWTError
from dotenv import load_dotenv
import asyncio
import requests
import hmac
import hashlib
import logging
import os
import secrets

logger = logging.getLogger(__name__)
load_dotenv()

_SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
if not _SUPABASE_URL:
    raise RuntimeError("Missing required environment variable: NEXT_PUBLIC_SUPABASE_URL")

JWKS_URL = f"{_SUPABASE_URL}/auth/v1/.well-known/jwks.json"

_PASSKEY_HMAC_SECRET = os.getenv("PASSKEY_HMAC_SECRET")
if not _PASSKEY_HMAC_SECRET or len(_PASSKEY_HMAC_SECRET) < 64:
    raise RuntimeError("PASSKEY_HMAC_SECRET must be at least 32 bytes (64 hex chars)")


def _get_jwks_sync():
    return requests.get(JWKS_URL).json()


async def _get_jwks():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_jwks_sync)


async def verify_token(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing token")

    try:
        token = authorization.split(" ")[1]
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")

        jwks = await _get_jwks()
        key = next(
            (k for k in jwks["keys"] if k["kid"] == kid),
            None
        )

        if not key:
            logger.warning("JWKS public key not found for kid=%s", kid)
            raise HTTPException(status_code=401, detail="Public key not found")

        payload = jwt.decode(
            token,
            key,
            algorithms=["ES256"],
            audience="authenticated"
        )
        return payload

    except (JWTError, IndexError) as e:
        # IndexError: Authorization header present but without a space (no scheme) —
        # surface as 401, not an uncaught 500.
        logger.warning("JWT verification failed: %s", str(e))
        raise HTTPException(status_code=401, detail="Invalid token")


def generate_passkey() -> str:
    """8-digit zero-padded passkey from a CSPRNG. Plaintext is shown to the seller once."""
    return str(secrets.randbelow(100_000_000)).zfill(8)


def hash_passkey(passkey: str, listing_id: str) -> str:
    message = f"{passkey}{listing_id}".encode()
    return hmac.new(
        _PASSKEY_HMAC_SECRET.encode(),
        message,
        hashlib.sha256
    ).hexdigest()


def verify_passkey(submitted: str, listing_id: str, stored_hash: str) -> bool:
    expected = hash_passkey(submitted, listing_id)
    return hmac.compare_digest(expected, stored_hash)

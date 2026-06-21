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
    # Timeout is mandatory: this runs on every authenticated request (no JWKS cache in
    # v1), so a hung Supabase endpoint without it would exhaust the executor thread pool
    # and stall all auth.
    resp = requests.get(JWKS_URL, timeout=5)
    resp.raise_for_status()
    return resp.json()


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

        try:
            jwks = await _get_jwks()
        except Exception as e:
            # A network/timeout/non-200/malformed-JSON failure from the JWKS endpoint is
            # an auth-infrastructure outage, not a bad token. Surface 503 (so it isn't
            # mistaken for "invalid token") and log it per the "log every JWT failure" rule.
            logger.error("JWKS fetch failed: %s", str(e))
            raise HTTPException(status_code=503, detail="Authentication temporarily unavailable")

        key = next(
            (k for k in jwks.get("keys", []) if k.get("kid") == kid),
            None
        )

        if not key:
            logger.warning("JWKS public key not found for kid=%s", kid)
            raise HTTPException(status_code=401, detail="Public key not found")

        # NOTE: do NOT pin `issuer` or require an `iss` claim here. Supabase access
        # tokens' issuer format varies (legacy `"supabase"` vs `"<url>/auth/v1"`), and
        # pinning it rejects valid tokens. Trust is already anchored by ES256 signature
        # verification against THIS project's JWKS, so issuer pinning adds little. The
        # `exp` claim is still verified by jose automatically. (Matches AUTH.md.)
        payload = jwt.decode(
            token,
            key,
            algorithms=["ES256"],
            audience="authenticated",
        )
        return payload

    except (JWTError, IndexError) as e:
        # IndexError: Authorization header present but without a space (no scheme) —
        # surface as 401, not an uncaught 500.
        logger.warning("JWT verification failed: %s", str(e))
        raise HTTPException(status_code=401, detail="Invalid token")


async def optional_user(authorization: str = Header(None)):
    """Like verify_token, but for public endpoints that personalise when signed
    in: returns the JWT payload if a valid token is present, otherwise None
    (never raises). Used by GET /listings/{id} to identify the viewer."""
    if not authorization:
        return None
    try:
        return await verify_token(authorization)
    except HTTPException:
        return None


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

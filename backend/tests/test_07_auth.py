"""
test_07_auth.py
===============
Spec-driven tests for the auth layer described in spec 07-auth.md and AUTH.md.

Strategy:
- Pure unit tests against `verify_token`, `hash_passkey`, and `verify_passkey`
  in `app.core.security`.
- JWKS network calls are mocked with `unittest.mock.patch` — no live network
  required.
- A minimal FastAPI test app is used for route-level 401 guard tests; it
  re-uses the real `verify_token` dependency so the full execution path runs.
- Source introspection tests (SUPABASE_SERVICE_ROLE_KEY, PASSKEY_HMAC_SECRET
  in source text) confirm security invariants without coupling to internals.

Run from project root:
    cd backend && ..\\.venv\\Scripts\\python.exe -m pytest tests/test_07_auth.py -v
"""

import hmac
import hashlib
import importlib
import inspect
import logging
import os
import pathlib
import sys
import time
import unittest.mock
import uuid

import pytest

# ---------------------------------------------------------------------------
# Env stubs — must be set before any app module is imported.
# ---------------------------------------------------------------------------
_TEST_PASSKEY_SECRET = "a" * 64  # 64 hex chars = 32 bytes
os.environ.setdefault("NEXT_PUBLIC_SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test")
os.environ.setdefault("PASSKEY_HMAC_SECRET", _TEST_PASSKEY_SECRET)
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("RAZORPAY_KEY_ID", "rzp_test_dummy")
os.environ.setdefault("RAZORPAY_KEY_SECRET", "dummy_secret")
os.environ.setdefault("RAZORPAY_WEBHOOK_SECRET", "dummy_webhook_secret")
os.environ.setdefault("RESEND_API_KEY", "re_dummy")

# ---------------------------------------------------------------------------
# App imports (safe after env stubs above)
# ---------------------------------------------------------------------------
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import app.core.security as security_module
from app.core.security import hash_passkey, verify_passkey, verify_token

# ---------------------------------------------------------------------------
# Helpers — build a real ES256 key pair + JWT for testing
# ---------------------------------------------------------------------------

def _make_es256_keypair():
    """Return (private_key, public_jwk_dict) using cryptography library."""
    from cryptography.hazmat.primitives.asymmetric.ec import (
        ECDH,
        SECP256R1,
        generate_private_key,
    )
    from cryptography.hazmat.backends import default_backend
    from jose.backends import ECKey

    private_key = generate_private_key(SECP256R1(), default_backend())
    # Wrap in python-jose ECKey to get the JWK representation
    jose_key = ECKey(private_key, algorithm="ES256")
    public_jwk = jose_key.public_key().to_dict()
    return jose_key, public_jwk


def _make_valid_jwt(jose_private_key, kid: str, sub: str, email: str) -> str:
    """Sign a minimal Supabase-style payload with ES256."""
    from jose import jwt as jose_jwt

    now = int(time.time())
    payload = {
        "sub": sub,
        "email": email,
        "aud": "authenticated",
        "iss": f"{os.environ['NEXT_PUBLIC_SUPABASE_URL']}/auth/v1",
        "iat": now,
        "exp": now + 3600,
        "role": "authenticated",
    }
    token = jose_jwt.encode(
        payload,
        jose_private_key.to_dict(),  # private key dict for signing
        algorithm="ES256",
        headers={"kid": kid},
    )
    return token


# ---------------------------------------------------------------------------
# A minimal protected FastAPI app used only in route-level tests.
# It uses the real verify_token dependency (no override) so the full auth
# path is exercised, including JWKS mock.
# ---------------------------------------------------------------------------

_mini_app = FastAPI()


@_mini_app.get("/protected")
def _protected_endpoint(user=Depends(verify_token)):
    return {"sub": user["sub"], "email": user["email"]}


# ===========================================================================
# 1. verify_token — happy path
# ===========================================================================

class TestVerifyTokenHappyPath:
    """Valid ES256 JWT with audience='authenticated' must return a payload
    containing 'sub' (UUID) and 'email'."""

    def test_valid_token_returns_payload_with_sub_and_email(self):
        kid = "test-kid-001"
        user_uuid = str(uuid.uuid4())
        user_email = "buyer@example.com"

        jose_key, public_jwk = _make_es256_keypair()
        public_jwk["kid"] = kid
        token = _make_valid_jwt(jose_key, kid, user_uuid, user_email)

        with unittest.mock.patch.object(
            security_module, "_get_jwks", return_value={"keys": [public_jwk]}
        ):
            with TestClient(_mini_app) as client:
                response = client.get(
                    "/protected", headers={"authorization": f"Bearer {token}"}
                )

        assert response.status_code == 200
        body = response.json()
        assert body["sub"] == user_uuid
        assert body["email"] == user_email

    def test_valid_token_sub_is_uuid_format(self):
        kid = "test-kid-002"
        user_uuid = str(uuid.uuid4())
        user_email = "seller@example.com"

        jose_key, public_jwk = _make_es256_keypair()
        public_jwk["kid"] = kid
        token = _make_valid_jwt(jose_key, kid, user_uuid, user_email)

        with unittest.mock.patch.object(
            security_module, "_get_jwks", return_value={"keys": [public_jwk]}
        ):
            with TestClient(_mini_app) as client:
                response = client.get(
                    "/protected", headers={"authorization": f"Bearer {token}"}
                )

        assert response.status_code == 200
        returned_sub = response.json()["sub"]
        # Must be parseable as a UUID — no other format is valid
        parsed = uuid.UUID(returned_sub)
        assert str(parsed) == returned_sub

    def test_valid_token_does_not_return_401(self):
        kid = "test-kid-003"
        user_uuid = str(uuid.uuid4())

        jose_key, public_jwk = _make_es256_keypair()
        public_jwk["kid"] = kid
        token = _make_valid_jwt(jose_key, kid, user_uuid, "u@example.com")

        with unittest.mock.patch.object(
            security_module, "_get_jwks", return_value={"keys": [public_jwk]}
        ):
            with TestClient(_mini_app) as client:
                response = client.get(
                    "/protected", headers={"authorization": f"Bearer {token}"}
                )

        assert response.status_code != 401


# ===========================================================================
# 2. verify_token — missing Authorization header → 401 "Missing token"
# ===========================================================================

class TestVerifyTokenMissingHeader:
    def test_no_authorization_header_returns_401(self):
        with TestClient(_mini_app) as client:
            response = client.get("/protected")
        assert response.status_code == 401

    def test_no_authorization_header_detail_is_missing_token(self):
        with TestClient(_mini_app) as client:
            response = client.get("/protected")
        assert response.json()["detail"] == "Missing token"

    def test_empty_authorization_header_returns_401(self):
        with TestClient(_mini_app) as client:
            response = client.get("/protected", headers={"authorization": ""})
        assert response.status_code == 401


# ===========================================================================
# 3. verify_token — malformed or expired token → 401 "Invalid token"
# ===========================================================================

class TestVerifyTokenInvalidToken:
    def test_malformed_token_returns_401(self):
        with unittest.mock.patch.object(
            security_module, "_get_jwks", return_value={"keys": []}
        ):
            with TestClient(_mini_app) as client:
                response = client.get(
                    "/protected", headers={"authorization": "Bearer not.a.jwt"}
                )
        # Malformed tokens raise JWTError before JWKS lookup in some cases,
        # or return 401 "Public key not found" / "Invalid token" — both are 401.
        assert response.status_code == 401

    def test_expired_token_returns_401_invalid_token(self):
        """A token whose exp is in the past must return 401 with detail 'Invalid token'."""
        kid = "test-kid-expired"
        user_uuid = str(uuid.uuid4())

        jose_key, public_jwk = _make_es256_keypair()
        public_jwk["kid"] = kid

        from jose import jwt as jose_jwt
        expired_payload = {
            "sub": user_uuid,
            "email": "x@example.com",
            "aud": "authenticated",
            "iat": int(time.time()) - 7200,
            "exp": int(time.time()) - 3600,  # already expired
            "role": "authenticated",
        }
        expired_token = jose_jwt.encode(
            expired_payload,
            jose_key.to_dict(),
            algorithm="ES256",
            headers={"kid": kid},
        )

        with unittest.mock.patch.object(
            security_module, "_get_jwks", return_value={"keys": [public_jwk]}
        ):
            with TestClient(_mini_app) as client:
                response = client.get(
                    "/protected", headers={"authorization": f"Bearer {expired_token}"}
                )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid token"

    def test_wrong_algorithm_token_returns_401(self):
        """A token signed with HS256 (not ES256) must be rejected as Invalid token."""
        import secrets as _secrets
        hs256_secret = _secrets.token_hex(32)

        from jose import jwt as jose_jwt
        hs_payload = {
            "sub": str(uuid.uuid4()),
            "email": "x@example.com",
            "aud": "authenticated",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        }
        hs_token = jose_jwt.encode(hs_payload, hs256_secret, algorithm="HS256")

        # Provide an unrelated EC key in JWKS — kid may not match, but the
        # algorithm guard in jose.jwt.decode should also reject HS256 tokens.
        kid = "test-kid-hs256"
        jose_key, public_jwk = _make_es256_keypair()
        public_jwk["kid"] = kid

        with unittest.mock.patch.object(
            security_module, "_get_jwks", return_value={"keys": [public_jwk]}
        ):
            with TestClient(_mini_app) as client:
                response = client.get(
                    "/protected", headers={"authorization": f"Bearer {hs_token}"}
                )

        assert response.status_code == 401


# ===========================================================================
# 4. verify_token — unknown kid → 401 "Public key not found"
# ===========================================================================

class TestVerifyTokenUnknownKid:
    def test_unknown_kid_returns_401(self):
        kid = "known-kid"
        unknown_kid = "totally-different-kid"
        user_uuid = str(uuid.uuid4())

        jose_key, public_jwk = _make_es256_keypair()
        public_jwk["kid"] = kid  # JWKS has "known-kid"
        token = _make_valid_jwt(jose_key, unknown_kid, user_uuid, "u@example.com")
        # token header contains "totally-different-kid" — not in JWKS

        with unittest.mock.patch.object(
            security_module, "_get_jwks", return_value={"keys": [public_jwk]}
        ):
            with TestClient(_mini_app) as client:
                response = client.get(
                    "/protected", headers={"authorization": f"Bearer {token}"}
                )

        assert response.status_code == 401

    def test_unknown_kid_detail_is_public_key_not_found(self):
        kid = "known-kid"
        unknown_kid = "missing-kid"
        user_uuid = str(uuid.uuid4())

        jose_key, public_jwk = _make_es256_keypair()
        public_jwk["kid"] = kid
        token = _make_valid_jwt(jose_key, unknown_kid, user_uuid, "u@example.com")

        with unittest.mock.patch.object(
            security_module, "_get_jwks", return_value={"keys": [public_jwk]}
        ):
            with TestClient(_mini_app) as client:
                response = client.get(
                    "/protected", headers={"authorization": f"Bearer {token}"}
                )

        assert response.json()["detail"] == "Public key not found"

    def test_empty_jwks_keys_list_returns_public_key_not_found(self):
        kid = "any-kid"
        user_uuid = str(uuid.uuid4())

        jose_key, public_jwk = _make_es256_keypair()
        public_jwk["kid"] = kid
        token = _make_valid_jwt(jose_key, kid, user_uuid, "u@example.com")

        # JWKS returns an empty keys array
        with unittest.mock.patch.object(
            security_module, "_get_jwks", return_value={"keys": []}
        ):
            with TestClient(_mini_app) as client:
                response = client.get(
                    "/protected", headers={"authorization": f"Bearer {token}"}
                )

        assert response.status_code == 401
        assert response.json()["detail"] == "Public key not found"


# ===========================================================================
# 5. JWT failures are logged at WARNING level
# ===========================================================================

class TestJWTFailuresAreLogged:
    def test_missing_header_does_not_call_logger_warning_for_missing_token(self):
        """
        The missing-header branch raises HTTPException directly before the try block,
        so no logger.warning is expected for that case.
        This test confirms the 401 is returned without needing a log assertion
        (the log path differs from the JWTError path).
        """
        with TestClient(_mini_app) as client:
            response = client.get("/protected")
        assert response.status_code == 401

    def test_unknown_kid_triggers_logger_warning(self):
        kid = "real-kid"
        unknown_kid = "ghost-kid"
        user_uuid = str(uuid.uuid4())

        jose_key, public_jwk = _make_es256_keypair()
        public_jwk["kid"] = kid
        token = _make_valid_jwt(jose_key, unknown_kid, user_uuid, "u@example.com")

        with unittest.mock.patch.object(
            security_module, "_get_jwks", return_value={"keys": [public_jwk]}
        ):
            with unittest.mock.patch.object(security_module.logger, "warning") as mock_warn:
                with TestClient(_mini_app) as client:
                    client.get("/protected", headers={"authorization": f"Bearer {token}"})

        mock_warn.assert_called()

    def test_expired_token_triggers_logger_warning(self):
        kid = "kid-exp"
        user_uuid = str(uuid.uuid4())

        jose_key, public_jwk = _make_es256_keypair()
        public_jwk["kid"] = kid

        from jose import jwt as jose_jwt
        exp_payload = {
            "sub": user_uuid,
            "email": "x@example.com",
            "aud": "authenticated",
            "iat": int(time.time()) - 7200,
            "exp": int(time.time()) - 3600,
            "role": "authenticated",
        }
        expired_token = jose_jwt.encode(
            exp_payload, jose_key.to_dict(), algorithm="ES256", headers={"kid": kid}
        )

        with unittest.mock.patch.object(
            security_module, "_get_jwks", return_value={"keys": [public_jwk]}
        ):
            with unittest.mock.patch.object(security_module.logger, "warning") as mock_warn:
                with TestClient(_mini_app) as client:
                    client.get(
                        "/protected",
                        headers={"authorization": f"Bearer {expired_token}"},
                    )

        mock_warn.assert_called()


# ===========================================================================
# 6. JWT string is never logged
# ===========================================================================

class TestJWTNotLogged:
    def test_logger_warning_does_not_contain_raw_token_on_expired(self):
        """The warning message must not contain the actual token string."""
        kid = "kid-log-check"
        user_uuid = str(uuid.uuid4())

        jose_key, public_jwk = _make_es256_keypair()
        public_jwk["kid"] = kid

        from jose import jwt as jose_jwt
        exp_payload = {
            "sub": user_uuid,
            "email": "x@example.com",
            "aud": "authenticated",
            "iat": int(time.time()) - 7200,
            "exp": int(time.time()) - 3600,
            "role": "authenticated",
        }
        expired_token = jose_jwt.encode(
            exp_payload, jose_key.to_dict(), algorithm="ES256", headers={"kid": kid}
        )

        logged_messages = []

        def capture_warning(msg, *args, **kwargs):
            # Reconstruct the formatted message as the logger would
            logged_messages.append(msg % args if args else str(msg))

        with unittest.mock.patch.object(
            security_module, "_get_jwks", return_value={"keys": [public_jwk]}
        ):
            with unittest.mock.patch.object(
                security_module.logger, "warning", side_effect=capture_warning
            ):
                with TestClient(_mini_app) as client:
                    client.get(
                        "/protected",
                        headers={"authorization": f"Bearer {expired_token}"},
                    )

        for msg in logged_messages:
            assert expired_token not in msg, (
                f"Raw JWT token found in log message: {msg[:60]}..."
            )

    def test_logger_warning_does_not_contain_raw_token_on_unknown_kid(self):
        kid = "kid-log-kid-check"
        unknown_kid = "not-in-jwks"
        user_uuid = str(uuid.uuid4())

        jose_key, public_jwk = _make_es256_keypair()
        public_jwk["kid"] = kid
        token = _make_valid_jwt(jose_key, unknown_kid, user_uuid, "u@example.com")

        logged_messages = []

        def capture_warning(msg, *args, **kwargs):
            logged_messages.append(msg % args if args else str(msg))

        with unittest.mock.patch.object(
            security_module, "_get_jwks", return_value={"keys": [public_jwk]}
        ):
            with unittest.mock.patch.object(
                security_module.logger, "warning", side_effect=capture_warning
            ):
                with TestClient(_mini_app) as client:
                    client.get(
                        "/protected", headers={"authorization": f"Bearer {token}"}
                    )

        for msg in logged_messages:
            assert token not in msg, (
                "Raw JWT token must never appear in log messages."
            )

    def test_security_source_has_no_logger_token_interpolation(self):
        """
        Static check: security.py source must not contain any log call that
        directly interpolates the 'token' local variable into the message string.
        Patterns like `logger.warning("... %s", token)` or f"...{token}" must
        not exist.
        """
        source_path = (
            pathlib.Path(__file__).parents[1] / "app" / "core" / "security.py"
        )
        source = source_path.read_text()
        # The token variable is called 'token' in security.py.
        # Guard against logger calls that pass 'token' as a format argument.
        import re
        bad_patterns = [
            r'logger\.\w+\(.*?,\s*token\b',   # logger.warning("...", token)
            r'logger\.\w+\(.*?f".*?\{token\}',  # f-string with token
        ]
        for pattern in bad_patterns:
            matches = re.findall(pattern, source)
            assert not matches, (
                f"Pattern '{pattern}' found in security.py — JWT must never be logged. "
                f"Matches: {matches}"
            )


# ===========================================================================
# 7. hash_passkey returns a hex string (HMAC-SHA256 digest)
# ===========================================================================

class TestHashPasskey:
    def test_hash_passkey_returns_string(self):
        result = hash_passkey("12345678", "listing-abc")
        assert isinstance(result, str)

    def test_hash_passkey_returns_hex_string(self):
        result = hash_passkey("12345678", "listing-abc")
        # A valid hex string contains only 0-9 a-f
        int(result, 16)  # raises ValueError if not hex

    def test_hash_passkey_returns_64_char_hex_for_sha256(self):
        """SHA-256 produces a 256-bit digest = 32 bytes = 64 hex chars."""
        result = hash_passkey("12345678", "listing-abc")
        assert len(result) == 64

    # ===========================================================================
    # 8. verify_passkey returns True for correct match
    # ===========================================================================

    def test_verify_passkey_returns_true_for_correct_match(self):
        passkey = "87654321"
        listing_id = "listing-xyz"
        stored = hash_passkey(passkey, listing_id)
        assert verify_passkey(passkey, listing_id, stored) is True

    # ===========================================================================
    # 9. verify_passkey returns False for wrong passkey
    # ===========================================================================

    def test_verify_passkey_returns_false_for_wrong_passkey(self):
        passkey = "11111111"
        listing_id = "listing-xyz"
        stored = hash_passkey(passkey, listing_id)
        assert verify_passkey("22222222", listing_id, stored) is False

    def test_verify_passkey_returns_false_for_wrong_listing_id(self):
        passkey = "33333333"
        stored = hash_passkey(passkey, "listing-A")
        # Same passkey but different listing_id — must not match
        assert verify_passkey(passkey, "listing-B", stored) is False

    # ===========================================================================
    # 10. verify_passkey uses hmac.compare_digest (constant-time)
    # ===========================================================================

    def test_verify_passkey_calls_hmac_compare_digest(self):
        """
        verify_passkey must call hmac.compare_digest, never plain == for
        hash comparison. We mock hmac.compare_digest and confirm it is invoked.
        """
        passkey = "44444444"
        listing_id = "listing-cd"
        stored = hash_passkey(passkey, listing_id)

        with unittest.mock.patch("app.core.security.hmac.compare_digest", wraps=hmac.compare_digest) as mock_cd:
            verify_passkey(passkey, listing_id, stored)

        mock_cd.assert_called_once()

    def test_verify_passkey_compare_digest_receives_two_hash_strings(self):
        """
        The two arguments passed to hmac.compare_digest must both be hex
        digest strings (equal length, hex chars only), not the raw passkey.
        """
        passkey = "55555555"
        listing_id = "listing-ef"
        stored = hash_passkey(passkey, listing_id)

        captured_args = []
        _real_compare_digest = hmac.compare_digest

        def capturing_compare_digest(a, b):
            captured_args.extend([a, b])
            return _real_compare_digest(a, b)

        with unittest.mock.patch(
            "app.core.security.hmac.compare_digest",
            side_effect=capturing_compare_digest,
        ):
            verify_passkey(passkey, listing_id, stored)

        assert len(captured_args) == 2
        for arg in captured_args:
            assert isinstance(arg, str)
            assert len(arg) == 64, "Each arg to compare_digest must be a 64-char hex digest"
            int(arg, 16)  # confirms hex

    # ===========================================================================
    # 11. hash_passkey is deterministic — same inputs → same output
    # ===========================================================================

    def test_hash_passkey_is_deterministic(self):
        passkey = "66666666"
        listing_id = "listing-gh"
        first = hash_passkey(passkey, listing_id)
        second = hash_passkey(passkey, listing_id)
        assert first == second

    # ===========================================================================
    # 12. hash_passkey output differs when listing_id changes
    # ===========================================================================

    def test_hash_passkey_differs_for_different_listing_ids(self):
        passkey = "77777777"
        hash_a = hash_passkey(passkey, "listing-001")
        hash_b = hash_passkey(passkey, "listing-002")
        assert hash_a != hash_b

    def test_hash_passkey_differs_for_different_passkeys(self):
        listing_id = "listing-ij"
        hash_a = hash_passkey("10000000", listing_id)
        hash_b = hash_passkey("10000001", listing_id)
        assert hash_a != hash_b


# ===========================================================================
# 13. CORS middleware uses FRONTEND_URL, not "*"
# ===========================================================================

class TestCORSConfiguration:
    def test_cors_middleware_is_registered_on_app(self):
        from fastapi.middleware.cors import CORSMiddleware
        from app.main import app as main_app

        cors_found = any(
            m.cls is CORSMiddleware
            for m in main_app.user_middleware
        )
        assert cors_found, "CORSMiddleware must be registered on the FastAPI app"

    def test_cors_allow_origins_is_not_wildcard(self):
        """
        The allow_origins list must never be ["*"] in the app configuration.
        It should be set to FRONTEND_URL.
        """
        from fastapi.middleware.cors import CORSMiddleware
        from app.main import app as main_app

        for m in main_app.user_middleware:
            if m.cls is CORSMiddleware:
                origins = m.kwargs.get("allow_origins", [])
                assert "*" not in origins, (
                    "CORS allow_origins must not contain '*' — use FRONTEND_URL only"
                )
                return
        raise AssertionError("CORSMiddleware not found in app middleware stack")

    def test_cors_allow_origins_contains_frontend_url(self):
        from fastapi.middleware.cors import CORSMiddleware
        from app.main import app as main_app
        from app.core.config import FRONTEND_URL

        for m in main_app.user_middleware:
            if m.cls is CORSMiddleware:
                origins = m.kwargs.get("allow_origins", [])
                assert FRONTEND_URL in origins, (
                    f"CORS allow_origins must contain FRONTEND_URL ({FRONTEND_URL})"
                )
                return
        raise AssertionError("CORSMiddleware not found in app middleware stack")

    def test_cors_allow_credentials_is_true(self):
        """allow_credentials=True is required for httpOnly cookie sessions."""
        from fastapi.middleware.cors import CORSMiddleware
        from app.main import app as main_app

        for m in main_app.user_middleware:
            if m.cls is CORSMiddleware:
                assert m.kwargs.get("allow_credentials") is True
                return
        raise AssertionError("CORSMiddleware not found in app middleware stack")

    def test_main_py_source_does_not_hardcode_wildcard_origins(self):
        source_path = (
            pathlib.Path(__file__).parents[1] / "app" / "main.py"
        )
        source = source_path.read_text()
        # Guard against allow_origins=["*"] appearing anywhere in main.py
        assert 'allow_origins=["*"]' not in source
        assert "allow_origins=['*']" not in source


# ===========================================================================
# 14. SUPABASE_SERVICE_ROLE_KEY does not appear in security.py
# ===========================================================================

class TestServiceRoleKeyAbsent:
    def test_supabase_service_role_key_not_in_security_py(self):
        """
        SUPABASE_SERVICE_ROLE_KEY is for background jobs only.
        It must not appear in security.py (the request-handler auth module).
        """
        source_path = (
            pathlib.Path(__file__).parents[1] / "app" / "core" / "security.py"
        )
        source = source_path.read_text()
        assert "SUPABASE_SERVICE_ROLE_KEY" not in source, (
            "SUPABASE_SERVICE_ROLE_KEY must not be referenced in security.py — "
            "it is for background jobs only, never request handlers."
        )

    def test_security_module_object_has_no_service_role_attribute(self):
        """
        Confirm at runtime that no module-level name in security.py
        holds the service role key string.
        """
        assert not hasattr(security_module, "SUPABASE_SERVICE_ROLE_KEY"), (
            "security module must not expose SUPABASE_SERVICE_ROLE_KEY as a module-level name"
        )


# ===========================================================================
# 15. PASSKEY_HMAC_SECRET is never logged
# ===========================================================================

class TestPasskeySecretNotLogged:
    def test_security_py_source_has_no_log_of_passkey_secret_variable(self):
        """
        Static source check: security.py must not pass `PASSKEY_HMAC_SECRET`
        as an argument to any logger call.
        """
        import re
        source_path = (
            pathlib.Path(__file__).parents[1] / "app" / "core" / "security.py"
        )
        source = source_path.read_text()
        bad_patterns = [
            r'logger\.\w+\(.*?PASSKEY_HMAC_SECRET',
            r'log.*?PASSKEY_HMAC_SECRET',
        ]
        for pattern in bad_patterns:
            matches = re.findall(pattern, source)
            assert not matches, (
                f"PASSKEY_HMAC_SECRET found in a log statement in security.py: {matches}"
            )

    def test_codebase_has_no_log_passkey_pattern(self):
        """
        Scan all Python files under backend/app/ for any logger call that
        references PASSKEY_HMAC_SECRET by name.
        """
        import re
        app_root = pathlib.Path(__file__).parents[1] / "app"
        pattern = re.compile(r'logger\.\w+\(.*?PASSKEY_HMAC_SECRET')
        violations = []
        for py_file in app_root.rglob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            if pattern.search(source):
                violations.append(str(py_file))
        assert not violations, (
            f"PASSKEY_HMAC_SECRET found in a logger call in: {violations}"
        )

    def test_hash_passkey_does_not_log_secret_value_at_runtime(self):
        """
        Call hash_passkey and verify that the PASSKEY_HMAC_SECRET value
        never appears in any logger.warning/info/debug/error call during execution.
        """
        passkey = "99999999"
        listing_id = "listing-secret-test"
        secret_value = os.environ["PASSKEY_HMAC_SECRET"]

        logged_messages = []

        def capture(*args, **kwargs):
            msg = args[0] % args[1:] if len(args) > 1 else str(args[0])
            logged_messages.append(msg)

        with unittest.mock.patch.object(security_module.logger, "warning", side_effect=capture), \
             unittest.mock.patch.object(security_module.logger, "info", side_effect=capture), \
             unittest.mock.patch.object(security_module.logger, "debug", side_effect=capture), \
             unittest.mock.patch.object(security_module.logger, "error", side_effect=capture):
            hash_passkey(passkey, listing_id)

        for msg in logged_messages:
            assert secret_value not in msg, (
                "PASSKEY_HMAC_SECRET value must never appear in any log message."
            )


# ===========================================================================
# 16. No FastAPI auth routes exist — verify_token is a dependency only
# ===========================================================================

class TestNoAuthRoutesOnFastAPI:
    def test_no_auth_register_route(self):
        from app.main import app as main_app
        paths = [route.path for route in main_app.routes]
        assert "/auth/register" not in paths
        assert "/v1/auth/register" not in paths

    def test_no_auth_login_route(self):
        from app.main import app as main_app
        paths = [route.path for route in main_app.routes]
        assert "/auth/login" not in paths
        assert "/v1/auth/login" not in paths

    def test_no_auth_refresh_route(self):
        from app.main import app as main_app
        paths = [route.path for route in main_app.routes]
        assert "/auth/refresh" not in paths
        assert "/v1/auth/refresh" not in paths

    def test_no_auth_logout_route(self):
        from app.main import app as main_app
        paths = [route.path for route in main_app.routes]
        assert "/auth/logout" not in paths
        assert "/v1/auth/logout" not in paths


# ===========================================================================
# 17. Algorithm guard — verify_token only accepts ES256
# ===========================================================================

class TestAlgorithmGuard:
    def test_security_py_only_specifies_es256_algorithm(self):
        """
        The algorithms list passed to jwt.decode in security.py must be
        ["ES256"] — no HS256 or RS256 is permitted.
        """
        import re
        source_path = (
            pathlib.Path(__file__).parents[1] / "app" / "core" / "security.py"
        )
        source = source_path.read_text()

        # Confirm ES256 appears in an algorithms list
        assert "ES256" in source, "ES256 must be specified in security.py"

        # Confirm HS256 is not present anywhere in the algorithms argument
        hs256_in_algorithms = re.search(r'algorithms\s*=\s*\[.*?HS256.*?\]', source)
        assert hs256_in_algorithms is None, (
            "HS256 must not appear in the algorithms list in security.py"
        )

    def test_verify_token_audience_is_authenticated(self):
        """
        jwt.decode must be called with audience="authenticated" — the Supabase
        standard audience for access tokens.
        """
        source_path = (
            pathlib.Path(__file__).parents[1] / "app" / "core" / "security.py"
        )
        source = source_path.read_text()
        assert 'audience="authenticated"' in source or "audience='authenticated'" in source, (
            'jwt.decode in security.py must use audience="authenticated"'
        )


# ===========================================================================
# 18. passkey plaintext is never stored — hash_passkey output is not the input
# ===========================================================================

class TestPasskeyNotStoredPlaintext:
    def test_hash_passkey_output_is_not_equal_to_input_passkey(self):
        passkey = "12340000"
        result = hash_passkey(passkey, "listing-plain")
        assert result != passkey

    def test_hash_passkey_output_is_not_equal_to_listing_id(self):
        passkey = "00001234"
        listing_id = "listing-plain-2"
        result = hash_passkey(passkey, listing_id)
        assert result != listing_id

    def test_verify_passkey_false_when_plaintext_passkey_used_as_stored_hash(self):
        """
        If someone accidentally stores the plaintext passkey instead of its hash,
        verify_passkey must return False — not True.
        """
        passkey = "99998888"
        listing_id = "listing-plain-3"
        # stored_hash is the raw passkey (wrong — should be a hash)
        assert verify_passkey(passkey, listing_id, passkey) is False

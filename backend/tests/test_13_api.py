"""
Tests for Spec 13 — API Reference.

This file validates the full API surface of the SMEI backend against the
documented contracts in .claude/specs/technical/13-api.md. Tests are
derived from what the spec says each endpoint SHOULD do — not from reading
implementation code.

Endpoints covered:
  GET    /v1/listings
  POST   /v1/listings
  GET    /v1/listings/{id}
  PATCH  /v1/listings/{id}
  DELETE /v1/listings/{id}
  PATCH  /v1/listings/{id}/passkey
  GET    /v1/users/me
  PATCH  /v1/users/me
  GET    /v1/users/{id}
  GET    /v1/conversations
  POST   /v1/conversations
  GET    /v1/conversations/{id}/messages
  POST   /v1/conversations/{id}/messages
  PATCH  /v1/conversations/{id}/messages/read
  POST   /v1/payments/verify-passkey
  POST   /v1/payments/webhook
  GET    /v1/transactions/{id}/status

Run from project root:
    cd backend && ..\\.venv\\Scripts\\python.exe -m pytest tests/test_13_api.py -v
"""

import asyncio
import hashlib
import hmac
import json
import sys
import uuid
from datetime import datetime
from unittest import mock
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

# ---------------------------------------------------------------------------
# Windows asyncio policy — must be set before app imports
# ---------------------------------------------------------------------------
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ---------------------------------------------------------------------------
# Env stubs — must be set before any app module is imported
# ---------------------------------------------------------------------------
import os

os.environ.setdefault("NEXT_PUBLIC_SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("PASSKEY_HMAC_SECRET", "a" * 64)
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("RAZORPAY_KEY_ID", "rzp_test_dummy")
os.environ.setdefault("RAZORPAY_KEY_SECRET", "dummy_secret")
os.environ.setdefault("RAZORPAY_WEBHOOK_SECRET", "dummy_webhook_secret")
os.environ.setdefault("RESEND_API_KEY", "re_dummy")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "eyJdummy")

# ---------------------------------------------------------------------------
# App imports (safe after env stubs)
# ---------------------------------------------------------------------------
from app.main import app
from app.core.security import verify_token, hash_passkey
from app.core.database import get_db, AsyncSessionLocal
from app.core.redis import get_redis
from app.schemas.listing import ListingOut
from app.schemas.user import UserMe, UserPublic
from app.services import payment_service

# ---------------------------------------------------------------------------
# Stable test identity UUIDs
# ---------------------------------------------------------------------------
SELLER_ID = str(uuid.uuid4())
BUYER_ID = str(uuid.uuid4())
OTHER_USER_ID = str(uuid.uuid4())

# ---------------------------------------------------------------------------
# Fields that must NEVER appear in any API response — Spec 13 "Fields never
# returned" section, plus the passkey_hash / passkey rules
# ---------------------------------------------------------------------------
FORBIDDEN_LISTING_FIELDS = {
    "passkey_hash",
    "passkey_invalidated",
    "passkey_invalidated_at",
    "sold_at",
    "deleted_at",
}

FORBIDDEN_TRANSACTION_FIELDS = {
    "razorpay_payment_link_id",
    "razorpay_payment_id",
    "platform_fee_rupees",
    "seller_payout_rupees",
    "refunded_at",
    "released_at",
}

FORBIDDEN_CONVERSATION_FIELDS = {"first_message_notified"}

FORBIDDEN_USER_PUBLIC_FIELDS = {"razorpay_account_id"}

# ===========================================================================
# FakeRedis — identical to the in-memory substitute used in test_10_chat.py
# ===========================================================================


class FakeRedis:
    """In-memory async Redis substitute.

    Supports get, set, incr, expire, delete, pipeline().
    """

    def __init__(self):
        self._store: dict = {}
        self._deleted_keys: list = []
        self._set_calls: list = []

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value, ex=None):
        self._store[key] = str(value)
        self._set_calls.append((key, value))
        return True

    async def incr(self, key: str) -> int:
        current = int(self._store.get(key, "0")) + 1
        self._store[key] = str(current)
        return current

    async def expire(self, key: str, ttl: int) -> bool:
        return True

    async def delete(self, key: str) -> int:
        self._deleted_keys.append(key)
        if key in self._store:
            del self._store[key]
            return 1
        return 0

    def pipeline(self):
        outer = self

        class _Pipe:
            def __init__(self):
                self._ops = []

            def incr(self, key: str):
                self._ops.append(("incr", key))
                return self

            def expire(self, key: str, ttl: int):
                self._ops.append(("expire", key, ttl))
                return self

            async def execute(self):
                results = []
                for op in self._ops:
                    if op[0] == "incr":
                        key = op[1]
                        current = int(outer._store.get(key, "0")) + 1
                        outer._store[key] = str(current)
                        results.append(current)
                    elif op[0] == "expire":
                        results.append(True)
                self._ops = []
                return results

        return _Pipe()


# ===========================================================================
# Helpers
# ===========================================================================


def _override_verify_token(user_id: str):
    """Return a no-arg callable that yields a fake JWT payload."""
    def _inner():
        return {"sub": user_id, "email": f"{user_id}@test.example.com"}
    return _inner


def _seed_users():
    async def _run():
        async with AsyncSessionLocal() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO public.users (id, full_name, razorpay_account_id, city, avatar_url)
                    VALUES
                        (:seller_id, 'Test Seller', 'acc_test_seller123', 'Mumbai', 'https://res.cloudinary.com/demo/image/upload/v1/seller.jpg'),
                        (:buyer_id,  'Test Buyer',  NULL,                 'Delhi',  NULL),
                        (:other_id,  'Test Other',  NULL,                 NULL,     NULL)
                    ON CONFLICT (id) DO UPDATE
                        SET razorpay_account_id = EXCLUDED.razorpay_account_id,
                            full_name           = EXCLUDED.full_name
                    """
                ),
                {
                    "seller_id": SELLER_ID,
                    "buyer_id": BUYER_ID,
                    "other_id": OTHER_USER_ID,
                },
            )
            await session.commit()

    asyncio.run(_run())


def _cleanup():
    async def _run():
        ids = [SELLER_ID, BUYER_ID, OTHER_USER_ID]
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("DELETE FROM public.messages WHERE sender_id = ANY(:ids)"),
                {"ids": ids},
            )
            await session.execute(
                text(
                    "DELETE FROM public.conversations "
                    "WHERE buyer_id = ANY(:ids) OR seller_id = ANY(:ids)"
                ),
                {"ids": ids},
            )
            await session.execute(
                text(
                    "DELETE FROM public.transactions "
                    "WHERE buyer_id = ANY(:ids) OR seller_id = ANY(:ids)"
                ),
                {"ids": ids},
            )
            await session.execute(
                text("DELETE FROM public.listings WHERE seller_id = ANY(:ids)"),
                {"ids": ids},
            )
            await session.execute(
                text("DELETE FROM public.users WHERE id = ANY(:ids)"),
                {"ids": ids},
            )
            await session.commit()

    asyncio.run(_run())


def _create_listing(
    seller_id: str = None,
    is_available: bool = True,
    exam_category: str = "JEE_MAINS",
    asking_price: int = 350,
    passkey: str = "12345678",
) -> str:
    seller_id = seller_id or SELLER_ID
    listing_id = str(uuid.uuid4())
    passkey_hash = hash_passkey(passkey, listing_id)

    async def _run():
        async with AsyncSessionLocal() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO public.listings
                        (id, seller_id, title, description, exam_category, subject,
                         listing_type, condition, asking_price, original_price, city,
                         images, is_available, passkey_hash)
                    VALUES
                        (:id, :seller_id, 'HC Verma Part 1', 'Good condition book',
                         :exam_category, 'Physics', 'BOOK', 'A',
                         :asking_price, 600, 'Delhi',
                         ARRAY['https://res.cloudinary.com/demo/image/upload/v1/x.jpg'],
                         :is_available, :passkey_hash)
                    """
                ),
                {
                    "id": listing_id,
                    "seller_id": seller_id,
                    "exam_category": exam_category,
                    "asking_price": asking_price,
                    "is_available": is_available,
                    "passkey_hash": passkey_hash,
                },
            )
            await session.commit()

    asyncio.run(_run())
    return listing_id


def _create_conversation(
    listing_id: str,
    buyer_id: str = None,
    seller_id: str = None,
    first_message_notified: bool = False,
) -> str:
    buyer_id = buyer_id or BUYER_ID
    seller_id = seller_id or SELLER_ID
    conv_id = str(uuid.uuid4())

    async def _run():
        async with AsyncSessionLocal() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO public.conversations
                        (id, listing_id, buyer_id, seller_id, first_message_notified)
                    VALUES
                        (:id, :listing_id, :buyer_id, :seller_id, :notified)
                    ON CONFLICT (listing_id, buyer_id) DO NOTHING
                    """
                ),
                {
                    "id": conv_id,
                    "listing_id": listing_id,
                    "buyer_id": buyer_id,
                    "seller_id": seller_id,
                    "notified": first_message_notified,
                },
            )
            await session.commit()

    asyncio.run(_run())
    return conv_id


def _create_message(
    conv_id: str,
    sender_id: str = None,
    body: str = "Hello, is this available?",
    is_read: bool = False,
) -> str:
    sender_id = sender_id or BUYER_ID
    msg_id = str(uuid.uuid4())

    async def _run():
        async with AsyncSessionLocal() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO public.messages
                        (id, conversation_id, sender_id, body, is_read)
                    VALUES
                        (:id, :conv_id, :sender_id, :body, :is_read)
                    """
                ),
                {
                    "id": msg_id,
                    "conv_id": conv_id,
                    "sender_id": sender_id,
                    "body": body,
                    "is_read": is_read,
                },
            )
            await session.commit()

    asyncio.run(_run())
    return msg_id


def _seed_transaction(
    listing_id: str,
    buyer_id: str,
    status: str = "initiated",
    amount_rupees: int = 350,
    payment_link_id: str = None,
) -> tuple[str, str]:
    txn_id = str(uuid.uuid4())
    payment_link_id = payment_link_id or f"plink_{uuid.uuid4().hex[:12]}"

    async def _run():
        async with AsyncSessionLocal() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO public.transactions
                        (id, listing_id, buyer_id, seller_id, amount_rupees,
                         platform_fee_rupees, seller_payout_rupees,
                         razorpay_payment_link_id, razorpay_payment_link_url,
                         status)
                    VALUES
                        (:id, :listing_id, :buyer_id, :seller_id, :amount_rupees,
                         0, :amount_rupees, :payment_link_id,
                         'https://rzp.io/l/test', :status)
                    """
                ),
                {
                    "id": txn_id,
                    "listing_id": listing_id,
                    "buyer_id": buyer_id,
                    "seller_id": SELLER_ID,
                    "amount_rupees": amount_rupees,
                    "payment_link_id": payment_link_id,
                    "status": status,
                },
            )
            await session.commit()

    asyncio.run(_run())
    return txn_id, payment_link_id


def _get_listing_row(listing_id: str) -> dict | None:
    async def _run():
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT * FROM public.listings WHERE id = :id"),
                {"id": listing_id},
            )
            row = result.mappings().first()
            return dict(row) if row else None

    return asyncio.run(_run())


def _get_message_row(msg_id: str) -> dict | None:
    async def _run():
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT * FROM public.messages WHERE id = :id"),
                {"id": msg_id},
            )
            row = result.mappings().first()
            return dict(row) if row else None

    return asyncio.run(_run())


def _build_webhook_payload(event: str, payment_link_id: str = "plink_fake", payment_id: str = "pay_fake"):
    return {
        "event": event,
        "payload": {
            "payment_link": {"entity": {"id": payment_link_id}},
            "payment": {"entity": {"id": payment_id}},
        },
    }


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def fake_redis():
    return FakeRedis()


@pytest.fixture
def client(fake_redis):
    async def _get_redis_override():
        yield fake_redis

    app.dependency_overrides[get_redis] = _get_redis_override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _seed_and_cleanup():
    _seed_users()
    yield
    _cleanup()


@pytest.fixture
def auth_as_seller():
    app.dependency_overrides[verify_token] = _override_verify_token(SELLER_ID)
    yield SELLER_ID
    app.dependency_overrides.pop(verify_token, None)


@pytest.fixture
def auth_as_buyer():
    app.dependency_overrides[verify_token] = _override_verify_token(BUYER_ID)
    yield BUYER_ID
    app.dependency_overrides.pop(verify_token, None)


@pytest.fixture
def auth_as_other():
    app.dependency_overrides[verify_token] = _override_verify_token(OTHER_USER_ID)
    yield OTHER_USER_ID
    app.dependency_overrides.pop(verify_token, None)


# ===========================================================================
# LISTINGS — GET /listings
# ===========================================================================


class TestGetListings:
    def test_get_listings_no_params_returns_200_and_list(self, client):
        """GET /listings with no query params must return 200 and a JSON array."""
        resp = client.get("/v1/listings")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_listings_no_params_returns_only_available_listings(self, client):
        """Spec: listings where is_available=FALSE are excluded from GET /listings."""
        available_id = _create_listing(is_available=True)
        unavailable_id = _create_listing(is_available=False)

        resp = client.get("/v1/listings")
        assert resp.status_code == 200
        returned_ids = {item["id"] for item in resp.json()}
        assert available_id in returned_ids
        assert unavailable_id not in returned_ids

    def test_get_listings_filter_by_exam_category_returns_matching_only(self, client):
        """GET /listings?exam_category=JEE_MAINS returns only JEE_MAINS listings."""
        jee_id = _create_listing(exam_category="JEE_MAINS")
        neet_id = _create_listing(exam_category="NEET_UG")

        resp = client.get("/v1/listings?exam_category=JEE_MAINS")
        assert resp.status_code == 200
        returned_ids = {item["id"] for item in resp.json()}
        assert jee_id in returned_ids
        assert neet_id not in returned_ids

    def test_get_listings_returns_200_even_when_empty(self, client):
        """Spec: GET /listings always returns 200, even if no listings match."""
        resp = client.get("/v1/listings?exam_category=GMAT&q=nonexistentquery12345xyz")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_listings_does_not_require_auth(self, client):
        """GET /listings is public — no Authorization header needed."""
        resp = client.get("/v1/listings")
        assert resp.status_code == 200

    def test_get_listings_response_items_never_contain_forbidden_fields(self, client):
        """Spec: passkey_hash, passkey_invalidated, passkey_invalidated_at,
        sold_at, deleted_at must never appear in GET /listings response items."""
        _create_listing()
        resp = client.get("/v1/listings")
        assert resp.status_code == 200
        for item in resp.json():
            for forbidden in FORBIDDEN_LISTING_FIELDS:
                assert forbidden not in item, (
                    f"Forbidden field '{forbidden}' found in GET /listings item"
                )

    def test_get_listings_response_items_have_integer_asking_price(self, client):
        """Spec: prices are whole rupees (integers). No paise, no floats."""
        _create_listing(asking_price=450)
        resp = client.get("/v1/listings")
        assert resp.status_code == 200
        for item in resp.json():
            assert isinstance(item["asking_price"], int), (
                f"asking_price must be an integer, got {type(item['asking_price'])}"
            )

    def test_get_listings_sql_injection_in_query_param_returns_200_safely(self, client):
        """Spec: parameterized queries only — ILIKE with injection attempt must
        not raise an error or leak data; the DB must handle it as a literal string."""
        resp = client.get("/v1/listings?q='; DROP TABLE listings; --")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_listings_deleted_listing_not_returned(self, client, auth_as_seller):
        """After DELETE /listings/{id}, the listing must no longer appear in GET /listings."""
        listing_id = _create_listing(seller_id=SELLER_ID)

        before = client.get("/v1/listings")
        assert any(item["id"] == listing_id for item in before.json())

        client.delete(f"/v1/listings/{listing_id}")

        after = client.get("/v1/listings")
        assert not any(item["id"] == listing_id for item in after.json())


# ===========================================================================
# LISTINGS — POST /listings
# ===========================================================================


VALID_LISTING_PAYLOAD = {
    "title": "HC Verma Part 1",
    "description": "Lightly used",
    "exam_category": "JEE_MAINS",
    "subject": "Physics",
    "listing_type": "BOOK",
    "condition": "A",
    "asking_price": 350,
    "original_price": 600,
    "city": "Delhi",
    "images": ["https://res.cloudinary.com/demo/image/upload/v1/sample.jpg"],
}


class TestCreateListing:
    def test_create_listing_without_auth_returns_401(self, client):
        """POST /listings without Authorization header must return 401."""
        resp = client.post("/v1/listings", json=VALID_LISTING_PAYLOAD)
        assert resp.status_code == 401

    def test_create_listing_without_razorpay_account_returns_403(self, client, auth_as_buyer):
        """Spec: seller without razorpay_account_id receives 403
        'Complete payment setup to start selling.'"""
        resp = client.post("/v1/listings", json=VALID_LISTING_PAYLOAD)
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Complete payment setup to start selling."

    def test_create_listing_with_razorpay_account_returns_201(self, client, auth_as_seller):
        """POST /listings by a seller with razorpay_account_id returns 201."""
        payload = dict(VALID_LISTING_PAYLOAD)
        payload["title"] = f"Unique listing {uuid.uuid4()}"
        resp = client.post("/v1/listings", json=payload)
        assert resp.status_code == 201

    def test_create_listing_response_contains_passkey_field(self, client, auth_as_seller):
        """Spec: POST /listings response must contain a 'passkey' field."""
        payload = dict(VALID_LISTING_PAYLOAD)
        payload["title"] = f"Passkey test listing {uuid.uuid4()}"
        resp = client.post("/v1/listings", json=payload)
        assert resp.status_code == 201
        assert "passkey" in resp.json()

    def test_create_listing_passkey_is_8_digit_numeric_string(self, client, auth_as_seller):
        """Spec: the passkey field must be an 8-digit numeric string (e.g. '03918472')."""
        payload = dict(VALID_LISTING_PAYLOAD)
        payload["title"] = f"8-digit passkey {uuid.uuid4()}"
        resp = client.post("/v1/listings", json=payload)
        assert resp.status_code == 201
        passkey = resp.json()["passkey"]
        assert isinstance(passkey, str)
        assert len(passkey) == 8
        assert passkey.isdigit(), f"Passkey '{passkey}' is not all digits"

    def test_create_listing_response_nested_listing_object_has_no_forbidden_fields(
        self, client, auth_as_seller
    ):
        """Spec: the nested listing in the response must not contain
        passkey_hash, passkey_invalidated, passkey_invalidated_at, sold_at, deleted_at."""
        payload = dict(VALID_LISTING_PAYLOAD)
        payload["title"] = f"Forbidden field check {uuid.uuid4()}"
        resp = client.post("/v1/listings", json=payload)
        assert resp.status_code == 201
        listing_body = resp.json().get("listing", resp.json())
        for forbidden in FORBIDDEN_LISTING_FIELDS:
            assert forbidden not in listing_body, (
                f"Forbidden field '{forbidden}' found in POST /listings response"
            )

    def test_create_listing_response_listing_passkey_never_exposed_again(
        self, client, auth_as_seller
    ):
        """GET /listings/{id} on a just-created listing must not return 'passkey'
        or 'passkey_hash' — the passkey is only returned once at creation time."""
        payload = dict(VALID_LISTING_PAYLOAD)
        payload["title"] = f"Passkey once {uuid.uuid4()}"
        create_resp = client.post("/v1/listings", json=payload)
        assert create_resp.status_code == 201
        listing_id = create_resp.json()["listing"]["id"]

        get_resp = client.get(f"/v1/listings/{listing_id}")
        assert get_resp.status_code == 200
        body = get_resp.json()
        assert "passkey" not in body
        assert "passkey_hash" not in body

    def test_create_listing_missing_required_field_returns_422(self, client, auth_as_seller):
        """POST /listings without 'title' (required) must return 422."""
        payload = dict(VALID_LISTING_PAYLOAD)
        del payload["title"]
        resp = client.post("/v1/listings", json=payload)
        assert resp.status_code == 422

    def test_create_listing_invalid_listing_type_returns_422(self, client, auth_as_seller):
        """listing_type must be BOOK, NOTES, MODULE, or BUNDLE — any other value is 422."""
        payload = dict(VALID_LISTING_PAYLOAD)
        payload["listing_type"] = "TEXTBOOK"
        resp = client.post("/v1/listings", json=payload)
        assert resp.status_code == 422

    def test_create_listing_invalid_condition_returns_422(self, client, auth_as_seller):
        """condition must be A, B, or C — any other value is 422."""
        payload = dict(VALID_LISTING_PAYLOAD)
        payload["condition"] = "D"
        resp = client.post("/v1/listings", json=payload)
        assert resp.status_code == 422

    def test_create_listing_asking_price_is_integer_not_paise(self, client, auth_as_seller):
        """Spec: prices stored in whole rupees — asking_price in the response
        must equal what was sent (350), never 35000 (paise)."""
        payload = dict(VALID_LISTING_PAYLOAD)
        payload["title"] = f"Price int check {uuid.uuid4()}"
        payload["asking_price"] = 350
        resp = client.post("/v1/listings", json=payload)
        assert resp.status_code == 201
        listing = resp.json()["listing"]
        assert listing["asking_price"] == 350
        assert listing["asking_price"] != 350 * 100


# ===========================================================================
# LISTINGS — GET /listings/{id}
# ===========================================================================


class TestGetListing:
    def test_get_listing_by_id_returns_200_and_correct_id(self, client):
        """GET /listings/{id} returns the listing with the matching id."""
        listing_id = _create_listing()
        resp = client.get(f"/v1/listings/{listing_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == listing_id

    def test_get_listing_nonexistent_returns_404(self, client):
        """GET /listings/{id} for a non-existent UUID returns 404."""
        resp = client.get(f"/v1/listings/{uuid.uuid4()}")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Listing not found."

    def test_get_listing_does_not_require_auth(self, client):
        """GET /listings/{id} is public — no Authorization header needed."""
        listing_id = _create_listing()
        resp = client.get(f"/v1/listings/{listing_id}")
        assert resp.status_code == 200

    def test_get_listing_response_never_contains_forbidden_fields(self, client):
        """Spec: passkey_hash, passkey_invalidated, passkey_invalidated_at,
        sold_at, deleted_at must never appear in GET /listings/{id} response."""
        listing_id = _create_listing()
        resp = client.get(f"/v1/listings/{listing_id}")
        assert resp.status_code == 200
        body = resp.json()
        for forbidden in FORBIDDEN_LISTING_FIELDS:
            assert forbidden not in body, (
                f"Forbidden field '{forbidden}' found in GET /listings/{{id}} response"
            )

    def test_get_listing_passkey_fields_never_in_response(self, client):
        """Neither 'passkey' nor 'passkey_hash' may appear in the GET response."""
        listing_id = _create_listing()
        resp = client.get(f"/v1/listings/{listing_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert "passkey" not in body
        assert "passkey_hash" not in body

    def test_get_listing_returns_unavailable_listing(self, client):
        """Spec: GET /listings/{id} returns the listing even if is_available=FALSE.
        The detail page must handle sold/paused state."""
        listing_id = _create_listing(is_available=False)
        resp = client.get(f"/v1/listings/{listing_id}")
        assert resp.status_code == 200
        assert resp.json()["is_available"] is False

    def test_get_listing_asking_price_is_whole_integer(self, client):
        """Prices must be whole rupees — never floats, never paise."""
        listing_id = _create_listing(asking_price=275)
        resp = client.get(f"/v1/listings/{listing_id}")
        assert resp.status_code == 200
        price = resp.json()["asking_price"]
        assert isinstance(price, int)
        assert price == 275


# ===========================================================================
# LISTINGS — PATCH /listings/{id}
# ===========================================================================


class TestUpdateListing:
    def test_update_listing_without_auth_returns_401(self, client):
        """PATCH /listings/{id} without Authorization header returns 401."""
        listing_id = _create_listing()
        resp = client.patch(f"/v1/listings/{listing_id}", json={"title": "New title"})
        assert resp.status_code == 401

    def test_update_listing_by_non_owner_returns_403(self, client, auth_as_buyer):
        """PATCH /listings/{id} by a user who is not the listing's seller returns 403."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        resp = client.patch(f"/v1/listings/{listing_id}", json={"title": "Unauthorized update"})
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Not authorised."

    def test_update_listing_by_owner_returns_200_with_updated_fields(
        self, client, auth_as_seller
    ):
        """PATCH /listings/{id} by the owner returns 200 with the updated fields reflected."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        resp = client.patch(
            f"/v1/listings/{listing_id}",
            json={"title": "Updated Title", "asking_price": 300},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "Updated Title"
        assert body["asking_price"] == 300

    def test_update_listing_nonexistent_returns_404(self, client, auth_as_seller):
        """PATCH /listings/{id} on a non-existent UUID returns 404."""
        resp = client.patch(
            f"/v1/listings/{uuid.uuid4()}", json={"title": "Ghost listing"}
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Listing not found."

    def test_update_listing_response_never_contains_forbidden_fields(
        self, client, auth_as_seller
    ):
        """PATCH /listings/{id} response must never contain passkey or internal fields."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        resp = client.patch(
            f"/v1/listings/{listing_id}", json={"city": "Bangalore"}
        )
        assert resp.status_code == 200
        body = resp.json()
        for forbidden in FORBIDDEN_LISTING_FIELDS:
            assert forbidden not in body

    def test_update_listing_owner_can_pause_listing(self, client, auth_as_seller):
        """Owner can set is_available=FALSE to pause listing (not a delete)."""
        listing_id = _create_listing(seller_id=SELLER_ID, is_available=True)
        resp = client.patch(
            f"/v1/listings/{listing_id}", json={"is_available": False}
        )
        assert resp.status_code == 200
        assert resp.json()["is_available"] is False

    def test_update_listing_invalid_condition_returns_422(self, client, auth_as_seller):
        """PATCH /listings/{id} with an invalid condition value returns 422."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        resp = client.patch(f"/v1/listings/{listing_id}", json={"condition": "Z"})
        assert resp.status_code == 422


# ===========================================================================
# LISTINGS — DELETE /listings/{id}
# ===========================================================================


class TestDeleteListing:
    def test_delete_listing_without_auth_returns_401(self, client):
        """DELETE /listings/{id} without Authorization header returns 401."""
        listing_id = _create_listing()
        resp = client.delete(f"/v1/listings/{listing_id}")
        assert resp.status_code == 401

    def test_delete_listing_by_non_owner_returns_403(self, client, auth_as_buyer):
        """DELETE /listings/{id} by a non-owner returns 403."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        resp = client.delete(f"/v1/listings/{listing_id}")
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Not authorised."

    def test_delete_listing_by_owner_returns_204(self, client, auth_as_seller):
        """DELETE /listings/{id} by the owner returns 204 No Content."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        resp = client.delete(f"/v1/listings/{listing_id}")
        assert resp.status_code == 204
        assert resp.content == b""

    def test_delete_listing_sets_is_available_false_in_db(self, client, auth_as_seller):
        """Spec: DELETE sets is_available=FALSE in the DB."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        client.delete(f"/v1/listings/{listing_id}")
        row = _get_listing_row(listing_id)
        assert row is not None
        assert row["is_available"] is False

    def test_delete_listing_sets_deleted_at_in_db(self, client, auth_as_seller):
        """Spec: DELETE sets deleted_at=now() in the DB."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        client.delete(f"/v1/listings/{listing_id}")
        row = _get_listing_row(listing_id)
        assert row is not None
        assert row["deleted_at"] is not None

    def test_delete_listing_does_not_set_sold_at_in_db(self, client, auth_as_seller):
        """Spec: DELETE sets deleted_at but NOT sold_at — sold_at is reserved for
        webhook-confirmed payments only."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        client.delete(f"/v1/listings/{listing_id}")
        row = _get_listing_row(listing_id)
        assert row is not None
        assert row["sold_at"] is None

    def test_delete_listing_not_returned_by_get_listings(self, client, auth_as_seller):
        """After DELETE, GET /listings must not include the deleted listing."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        client.delete(f"/v1/listings/{listing_id}")
        resp = client.get("/v1/listings")
        returned_ids = {item["id"] for item in resp.json()}
        assert listing_id not in returned_ids

    def test_delete_listing_nonexistent_returns_404(self, client, auth_as_seller):
        """DELETE /listings/{id} on a non-existent UUID returns 404."""
        resp = client.delete(f"/v1/listings/{uuid.uuid4()}")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Listing not found."


# ===========================================================================
# LISTINGS — PATCH /listings/{id}/passkey
# ===========================================================================


class TestRegeneratePasskey:
    def test_regenerate_passkey_without_auth_returns_401(self, client):
        """PATCH /listings/{id}/passkey without auth returns 401."""
        listing_id = _create_listing()
        resp = client.patch(f"/v1/listings/{listing_id}/passkey")
        assert resp.status_code == 401

    def test_regenerate_passkey_by_non_owner_returns_403(self, client, auth_as_buyer):
        """PATCH /listings/{id}/passkey by a non-owner returns 403."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        resp = client.patch(f"/v1/listings/{listing_id}/passkey")
        assert resp.status_code == 403

    def test_regenerate_passkey_by_owner_returns_200_with_passkey(
        self, client, auth_as_seller
    ):
        """PATCH /listings/{id}/passkey by owner returns 200 with a new passkey."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        resp = client.patch(f"/v1/listings/{listing_id}/passkey")
        assert resp.status_code == 200
        body = resp.json()
        assert "passkey" in body

    def test_regenerate_passkey_returns_8_digit_numeric_passkey(
        self, client, auth_as_seller
    ):
        """The regenerated passkey must be an 8-digit numeric string."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        resp = client.patch(f"/v1/listings/{listing_id}/passkey")
        assert resp.status_code == 200
        passkey = resp.json()["passkey"]
        assert isinstance(passkey, str)
        assert len(passkey) == 8
        assert passkey.isdigit()

    def test_regenerate_passkey_blocked_for_sold_listing(self, client, auth_as_seller):
        """Spec: passkey regeneration is blocked when passkey_invalidated=TRUE (sold).
        Must return 400 'Cannot regenerate passkey for a sold listing.'"""
        listing_id = _create_listing(seller_id=SELLER_ID)

        async def _mark_sold():
            async with AsyncSessionLocal() as session:
                await session.execute(
                    text(
                        "UPDATE public.listings SET passkey_invalidated = TRUE WHERE id = :id"
                    ),
                    {"id": listing_id},
                )
                await session.commit()

        asyncio.run(_mark_sold())

        resp = client.patch(f"/v1/listings/{listing_id}/passkey")
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Cannot regenerate passkey for a sold listing."

    def test_regenerate_passkey_nonexistent_listing_returns_404(
        self, client, auth_as_seller
    ):
        """PATCH /listings/{id}/passkey for a non-existent listing returns 404."""
        resp = client.patch(f"/v1/listings/{uuid.uuid4()}/passkey")
        assert resp.status_code == 404


# ===========================================================================
# LISTINGS — paused listing edge case
# ===========================================================================


class TestPausedListing:
    def test_paused_listing_with_no_sold_at_is_valid_state(self, client):
        """Spec: is_available=FALSE with sold_at=NULL is a valid paused/suspended
        state and must not be flagged as sold."""
        listing_id = _create_listing(is_available=False)
        row = _get_listing_row(listing_id)
        assert row is not None
        assert row["is_available"] is False
        assert row["sold_at"] is None

    def test_paused_listing_still_accessible_via_get_listing_by_id(self, client):
        """GET /listings/{id} returns a paused listing (is_available=FALSE) — not 404."""
        listing_id = _create_listing(is_available=False)
        resp = client.get(f"/v1/listings/{listing_id}")
        assert resp.status_code == 200
        assert resp.json()["is_available"] is False

    def test_paused_listing_excluded_from_get_listings_index(self, client):
        """Paused listings (is_available=FALSE, sold_at=NULL) are excluded from
        GET /listings just like sold listings — only available ones are returned."""
        paused_id = _create_listing(is_available=False)
        resp = client.get("/v1/listings")
        returned_ids = {item["id"] for item in resp.json()}
        assert paused_id not in returned_ids


# ===========================================================================
# USERS — GET /users/me
# ===========================================================================


class TestGetMe:
    def test_get_me_without_auth_returns_401(self, client):
        """GET /users/me without Authorization header returns 401."""
        resp = client.get("/v1/users/me")
        assert resp.status_code == 401

    def test_get_me_returns_200_and_profile(self, client, auth_as_seller):
        """GET /users/me returns 200 and the caller's profile."""
        resp = client.get("/v1/users/me")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == SELLER_ID

    def test_get_me_contains_razorpay_account_id(self, client, auth_as_seller):
        """Spec: GET /users/me must include razorpay_account_id (null until onboarding)."""
        resp = client.get("/v1/users/me")
        assert resp.status_code == 200
        body = resp.json()
        assert "razorpay_account_id" in body

    def test_get_me_razorpay_account_id_null_for_unboarded_user(self, client, auth_as_buyer):
        """For a user without Razorpay onboarding, razorpay_account_id is null."""
        resp = client.get("/v1/users/me")
        assert resp.status_code == 200
        assert resp.json()["razorpay_account_id"] is None

    def test_get_me_razorpay_account_id_populated_for_onboarded_seller(
        self, client, auth_as_seller
    ):
        """SELLER_ID is seeded with razorpay_account_id='acc_test_seller123'."""
        resp = client.get("/v1/users/me")
        assert resp.status_code == 200
        assert resp.json()["razorpay_account_id"] == "acc_test_seller123"

    def test_get_me_contains_expected_fields(self, client, auth_as_seller):
        """Spec: GET /users/me response must contain id, full_name, city,
        avatar_url, is_verified, seller_rating, total_sales, razorpay_account_id,
        created_at."""
        resp = client.get("/v1/users/me")
        assert resp.status_code == 200
        body = resp.json()
        for field in (
            "id", "full_name", "city", "avatar_url", "is_verified",
            "seller_rating", "total_sales", "razorpay_account_id", "created_at"
        ):
            assert field in body, f"Expected field '{field}' missing from GET /users/me"


# ===========================================================================
# USERS — PATCH /users/me
# ===========================================================================


class TestUpdateMe:
    def test_update_me_without_auth_returns_401(self, client):
        """PATCH /users/me without Authorization header returns 401."""
        resp = client.patch("/v1/users/me", json={"full_name": "New Name"})
        assert resp.status_code == 401

    def test_update_me_updates_full_name(self, client, auth_as_buyer):
        """PATCH /users/me with full_name updates and returns the updated profile."""
        new_name = f"Updated Name {uuid.uuid4().hex[:6]}"
        resp = client.patch("/v1/users/me", json={"full_name": new_name})
        assert resp.status_code == 200
        assert resp.json()["full_name"] == new_name

    def test_update_me_updates_city(self, client, auth_as_buyer):
        """PATCH /users/me with city updates and returns the updated profile."""
        resp = client.patch("/v1/users/me", json={"city": "Hyderabad"})
        assert resp.status_code == 200
        assert resp.json()["city"] == "Hyderabad"

    def test_update_me_updates_avatar_url(self, client, auth_as_buyer):
        """PATCH /users/me with avatar_url updates and returns the updated profile."""
        url = "https://res.cloudinary.com/demo/image/upload/v1/new_avatar.jpg"
        resp = client.patch("/v1/users/me", json={"avatar_url": url})
        assert resp.status_code == 200
        assert resp.json()["avatar_url"] == url

    def test_update_me_response_contains_razorpay_account_id(self, client, auth_as_seller):
        """PATCH /users/me response must also contain razorpay_account_id (same shape as GET)."""
        resp = client.patch("/v1/users/me", json={"city": "Chennai"})
        assert resp.status_code == 200
        assert "razorpay_account_id" in resp.json()

    def test_update_me_partial_update_leaves_other_fields_unchanged(
        self, client, auth_as_seller
    ):
        """PATCH /users/me is a partial update — only supplied fields change."""
        original_resp = client.get("/v1/users/me")
        original_name = original_resp.json()["full_name"]

        client.patch("/v1/users/me", json={"city": "Kolkata"})

        updated_resp = client.get("/v1/users/me")
        assert updated_resp.json()["full_name"] == original_name


# ===========================================================================
# USERS — GET /users/{id}
# ===========================================================================


class TestGetPublicUser:
    def test_get_public_user_returns_200(self, client):
        """GET /users/{id} is public and returns 200 for an existing user."""
        resp = client.get(f"/v1/users/{SELLER_ID}")
        assert resp.status_code == 200

    def test_get_public_user_does_not_require_auth(self, client):
        """GET /users/{id} is public — no Authorization header needed."""
        resp = client.get(f"/v1/users/{SELLER_ID}")
        assert resp.status_code == 200

    def test_get_public_user_does_not_contain_razorpay_account_id(self, client):
        """Spec: GET /users/{id} must NEVER include razorpay_account_id."""
        resp = client.get(f"/v1/users/{SELLER_ID}")
        assert resp.status_code == 200
        assert "razorpay_account_id" not in resp.json()

    def test_get_public_user_contains_expected_fields(self, client):
        """Spec: GET /users/{id} must contain id, full_name, city, avatar_url,
        is_verified, seller_rating, total_sales, created_at."""
        resp = client.get(f"/v1/users/{SELLER_ID}")
        assert resp.status_code == 200
        body = resp.json()
        for field in (
            "id", "full_name", "city", "avatar_url", "is_verified",
            "seller_rating", "total_sales", "created_at"
        ):
            assert field in body, f"Expected field '{field}' missing from GET /users/{{id}}"

    def test_get_public_user_nonexistent_returns_404(self, client):
        """GET /users/{id} for a non-existent UUID returns 404."""
        resp = client.get(f"/v1/users/{uuid.uuid4()}")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "User not found."

    def test_get_public_user_schema_never_has_email_or_phone(self, client):
        """GET /users/{id} response must never contain email or phone (PII)."""
        resp = client.get(f"/v1/users/{SELLER_ID}")
        assert resp.status_code == 200
        body = resp.json()
        assert "email" not in body
        assert "phone" not in body


# ===========================================================================
# USERS — schema-level checks
# ===========================================================================


class TestUserSchemas:
    def test_user_me_schema_has_razorpay_account_id(self):
        """UserMe Pydantic model must declare razorpay_account_id."""
        assert "razorpay_account_id" in UserMe.model_fields

    def test_user_public_schema_does_not_have_razorpay_account_id(self):
        """UserPublic Pydantic model must NOT declare razorpay_account_id."""
        assert "razorpay_account_id" not in UserPublic.model_fields

    def test_user_public_schema_does_not_have_email(self):
        """UserPublic must never expose email."""
        assert "email" not in UserPublic.model_fields

    def test_listing_out_schema_does_not_have_passkey_hash(self):
        """ListingOut Pydantic model must NOT declare passkey_hash."""
        assert "passkey_hash" not in ListingOut.model_fields

    def test_listing_out_schema_does_not_have_passkey_invalidated(self):
        """ListingOut Pydantic model must NOT declare passkey_invalidated."""
        assert "passkey_invalidated" not in ListingOut.model_fields

    def test_listing_out_schema_does_not_have_sold_at(self):
        """ListingOut Pydantic model must NOT declare sold_at directly."""
        assert "sold_at" not in ListingOut.model_fields

    def test_listing_out_schema_does_not_have_deleted_at(self):
        """ListingOut Pydantic model must NOT declare deleted_at."""
        assert "deleted_at" not in ListingOut.model_fields


# ===========================================================================
# CONVERSATIONS — GET /conversations
# ===========================================================================


class TestListConversations:
    def test_list_conversations_without_auth_returns_401(self, client):
        """GET /conversations without Authorization header returns 401."""
        resp = client.get("/v1/conversations")
        assert resp.status_code == 401

    def test_list_conversations_returns_only_callers_conversations(
        self, client, auth_as_other
    ):
        """Spec: GET /conversations only returns conversations where caller is
        buyer or seller — cannot see others' conversations."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        _create_conversation(listing_id, buyer_id=BUYER_ID, seller_id=SELLER_ID)

        resp = client.get("/v1/conversations")
        assert resp.status_code == 200
        for conv in resp.json():
            assert conv["buyer_id"] == OTHER_USER_ID or conv["seller_id"] == OTHER_USER_ID, (
                "GET /conversations returned a conversation the caller is not part of"
            )

    def test_list_conversations_returns_buyer_perspective_conversations(
        self, client, auth_as_buyer
    ):
        """GET /conversations returns conversations in which the caller is buyer."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id, buyer_id=BUYER_ID, seller_id=SELLER_ID)

        resp = client.get("/v1/conversations")
        assert resp.status_code == 200
        returned_ids = {c["id"] for c in resp.json()}
        assert conv_id in returned_ids

    def test_list_conversations_returns_seller_perspective_conversations(
        self, client, auth_as_seller
    ):
        """GET /conversations returns conversations in which the caller is seller."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id, buyer_id=BUYER_ID, seller_id=SELLER_ID)

        resp = client.get("/v1/conversations")
        assert resp.status_code == 200
        returned_ids = {c["id"] for c in resp.json()}
        assert conv_id in returned_ids

    def test_list_conversations_response_never_contains_first_message_notified(
        self, client, auth_as_buyer
    ):
        """Spec: first_message_notified must never appear in any API response."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        _create_conversation(listing_id)
        resp = client.get("/v1/conversations")
        assert resp.status_code == 200
        for conv in resp.json():
            assert "first_message_notified" not in conv


# ===========================================================================
# CONVERSATIONS — POST /conversations
# ===========================================================================


class TestCreateConversation:
    def test_create_conversation_without_auth_returns_401(self, client):
        """POST /conversations without Authorization header returns 401."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        resp = client.post("/v1/conversations", json={"listing_id": listing_id})
        assert resp.status_code == 401

    def test_create_conversation_by_seller_on_own_listing_returns_403(
        self, client, auth_as_seller
    ):
        """Spec: caller who is the listing's seller receives 403
        'You cannot message yourself about your own listing.'"""
        listing_id = _create_listing(seller_id=SELLER_ID)
        resp = client.post("/v1/conversations", json={"listing_id": listing_id})
        assert resp.status_code == 403
        assert resp.json()["detail"] == "You cannot message yourself about your own listing."

    def test_create_conversation_returns_200_and_id(self, client, auth_as_buyer):
        """POST /conversations with a valid listing returns 200 and a conversation object."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        resp = client.post("/v1/conversations", json={"listing_id": listing_id})
        assert resp.status_code == 200
        body = resp.json()
        assert "id" in body
        assert body["listing_id"] == listing_id

    def test_create_conversation_idempotent_same_listing_same_buyer(
        self, client, auth_as_buyer
    ):
        """Spec: calling POST /conversations twice with the same listing_id
        returns the same conversation id both times (idempotent)."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        first = client.post("/v1/conversations", json={"listing_id": listing_id})
        second = client.post("/v1/conversations", json={"listing_id": listing_id})
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["id"] == second.json()["id"]

    def test_create_conversation_nonexistent_listing_returns_404(
        self, client, auth_as_buyer
    ):
        """POST /conversations with a listing_id that does not exist returns 404."""
        resp = client.post(
            "/v1/conversations", json={"listing_id": str(uuid.uuid4())}
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Listing not found."

    def test_create_conversation_response_never_contains_first_message_notified(
        self, client, auth_as_buyer
    ):
        """first_message_notified must never appear in the POST /conversations response."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        resp = client.post("/v1/conversations", json={"listing_id": listing_id})
        assert resp.status_code == 200
        assert "first_message_notified" not in resp.json()


# ===========================================================================
# CONVERSATIONS — GET /conversations/{id}/messages
# ===========================================================================


class TestGetMessages:
    def test_get_messages_without_auth_returns_401(self, client):
        """GET /conversations/{id}/messages without auth returns 401."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)
        resp = client.get(f"/v1/conversations/{conv_id}/messages")
        assert resp.status_code == 401

    def test_get_messages_by_non_participant_returns_403(self, client, auth_as_other):
        """Spec: GET /conversations/{id}/messages by a non-participant returns 403
        'Not a participant in this conversation.'"""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id, buyer_id=BUYER_ID, seller_id=SELLER_ID)
        resp = client.get(f"/v1/conversations/{conv_id}/messages")
        assert resp.status_code == 403
        assert "participant" in resp.json()["detail"].lower()

    def test_get_messages_by_buyer_participant_returns_200(self, client, auth_as_buyer):
        """GET /conversations/{id}/messages by the buyer returns 200."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)
        resp = client.get(f"/v1/conversations/{conv_id}/messages")
        assert resp.status_code == 200

    def test_get_messages_response_never_contains_contact_fields(
        self, client, auth_as_buyer
    ):
        """Spec: MessageOut must never contain email, phone, full_name, avatar_url."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)
        _create_message(conv_id, sender_id=BUYER_ID)

        resp = client.get(f"/v1/conversations/{conv_id}/messages")
        assert resp.status_code == 200
        for msg in resp.json():
            for forbidden in ("email", "phone", "full_name", "avatar_url"):
                assert forbidden not in msg, (
                    f"Forbidden field '{forbidden}' found in MessageOut"
                )

    def test_get_messages_nonexistent_conversation_returns_404(self, client, auth_as_buyer):
        """GET /conversations/{id}/messages for a non-existent conversation returns 404."""
        resp = client.get(f"/v1/conversations/{uuid.uuid4()}/messages")
        assert resp.status_code == 404


# ===========================================================================
# CONVERSATIONS — POST /conversations/{id}/messages
# ===========================================================================


class TestSendMessage:
    def test_send_message_without_auth_returns_401(self, client):
        """POST /conversations/{id}/messages without auth returns 401."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)
        resp = client.post(
            f"/v1/conversations/{conv_id}/messages", json={"body": "Hello"}
        )
        assert resp.status_code == 401

    def test_send_message_empty_body_returns_422(self, client, auth_as_buyer):
        """Spec: POST /conversations/{id}/messages with empty body returns 422."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)
        resp = client.post(
            f"/v1/conversations/{conv_id}/messages", json={"body": ""}
        )
        assert resp.status_code == 422

    def test_send_message_body_over_2000_chars_returns_422(self, client, auth_as_buyer):
        """Spec: POST /conversations/{id}/messages with body > 2000 chars returns 422."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)
        resp = client.post(
            f"/v1/conversations/{conv_id}/messages", json={"body": "x" * 2001}
        )
        assert resp.status_code == 422

    def test_send_message_by_non_participant_returns_403(self, client, auth_as_other):
        """POST /conversations/{id}/messages by non-participant returns 403."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id, buyer_id=BUYER_ID, seller_id=SELLER_ID)
        resp = client.post(
            f"/v1/conversations/{conv_id}/messages",
            json={"body": "Intruder message"},
        )
        assert resp.status_code == 403

    def test_send_message_101st_in_one_hour_returns_429(
        self, client, auth_as_buyer, fake_redis
    ):
        """Spec: the 101st message in one hour must return 429.
        Redis key: chat_rate:{conv_id}:{sender_id}, TTL 1 hour, limit 100."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)
        rate_key = f"chat_rate:{conv_id}:{BUYER_ID}"
        # Pre-seed counter to 100 — next send is the 101st
        asyncio.run(fake_redis.set(rate_key, 100))

        resp = client.post(
            f"/v1/conversations/{conv_id}/messages",
            json={"body": "Over the limit"},
        )
        assert resp.status_code == 429

    def test_send_message_100th_message_succeeds(
        self, client, auth_as_buyer, fake_redis
    ):
        """The 100th message (counter at 99 before send) must succeed."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id, first_message_notified=True)
        rate_key = f"chat_rate:{conv_id}:{BUYER_ID}"
        asyncio.run(fake_redis.set(rate_key, 99))

        with patch("app.services.chat_service.supabase_admin.fetch_user_email", new_callable=AsyncMock), \
             patch("app.services.chat_service.notification_service.send_new_message_email", new_callable=AsyncMock):
            resp = client.post(
                f"/v1/conversations/{conv_id}/messages",
                json={"body": "100th message"},
            )
        assert resp.status_code == 201

    def test_send_message_rate_limit_key_format(
        self, client, auth_as_buyer, fake_redis
    ):
        """Rate-limit Redis key must be exactly `chat_rate:{conv_id}:{sender_id}`."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id, first_message_notified=True)
        expected_key = f"chat_rate:{conv_id}:{BUYER_ID}"

        with patch("app.services.chat_service.supabase_admin.fetch_user_email", new_callable=AsyncMock), \
             patch("app.services.chat_service.notification_service.send_new_message_email", new_callable=AsyncMock):
            resp = client.post(
                f"/v1/conversations/{conv_id}/messages",
                json={"body": "Rate key test"},
            )

        assert resp.status_code == 201
        for key in fake_redis._store:
            if key.startswith("chat_rate:"):
                assert key == expected_key, (
                    f"Unexpected rate-limit key: '{key}'; expected '{expected_key}'"
                )

    def test_send_message_rate_limit_counter_ttl_is_one_hour(
        self, client, auth_as_buyer, fake_redis
    ):
        """Rate-limit counter TTL must be 3600 seconds (1 hour)."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id, first_message_notified=True)

        captured_ttls = []
        real_expire = fake_redis.expire

        async def _spy_expire(key: str, ttl: int) -> bool:
            captured_ttls.append(ttl)
            return await real_expire(key, ttl)

        fake_redis.expire = _spy_expire

        with patch("app.services.chat_service.supabase_admin.fetch_user_email", new_callable=AsyncMock), \
             patch("app.services.chat_service.notification_service.send_new_message_email", new_callable=AsyncMock):
            resp = client.post(
                f"/v1/conversations/{conv_id}/messages",
                json={"body": "TTL check"},
            )

        assert resp.status_code == 201
        assert 3600 in captured_ttls, (
            f"Expected rate-limit TTL of 3600 seconds. Got: {captured_ttls}"
        )


# ===========================================================================
# CONVERSATIONS — PATCH /conversations/{id}/messages/read
# ===========================================================================


class TestMarkRead:
    def test_mark_read_without_auth_returns_401(self, client):
        """PATCH /conversations/{id}/messages/read without auth returns 401."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)
        resp = client.patch(f"/v1/conversations/{conv_id}/messages/read")
        assert resp.status_code == 401

    def test_mark_read_by_non_participant_returns_403(self, client, auth_as_other):
        """PATCH mark-read by a non-participant returns 403."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id, buyer_id=BUYER_ID, seller_id=SELLER_ID)
        resp = client.patch(f"/v1/conversations/{conv_id}/messages/read")
        assert resp.status_code == 403

    def test_mark_read_by_participant_returns_204(self, client, auth_as_buyer):
        """PATCH mark-read by the buyer participant returns 204 No Content."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)
        _create_message(conv_id, sender_id=SELLER_ID, is_read=False)
        resp = client.patch(f"/v1/conversations/{conv_id}/messages/read")
        assert resp.status_code == 204
        assert resp.content == b""

    def test_mark_read_marks_other_party_messages_as_read(self, client, auth_as_buyer):
        """Spec: PATCH mark-read marks the OTHER party's messages as is_read=TRUE."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)
        seller_msg_id = _create_message(conv_id, sender_id=SELLER_ID, is_read=False)

        client.patch(f"/v1/conversations/{conv_id}/messages/read")

        row = _get_message_row(seller_msg_id)
        assert row["is_read"] is True

    def test_mark_read_does_not_affect_callers_own_messages(self, client, auth_as_buyer):
        """Spec: PATCH mark-read must NOT affect the caller's own messages."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)
        buyer_msg_id = _create_message(conv_id, sender_id=BUYER_ID, is_read=False)
        _create_message(conv_id, sender_id=SELLER_ID, is_read=False)

        client.patch(f"/v1/conversations/{conv_id}/messages/read")

        row = _get_message_row(buyer_msg_id)
        assert row["is_read"] is False, "Caller's own message must NOT be marked read"

    def test_mark_read_nonexistent_conversation_returns_404(self, client, auth_as_buyer):
        """PATCH mark-read on a non-existent conversation returns 404."""
        resp = client.patch(f"/v1/conversations/{uuid.uuid4()}/messages/read")
        assert resp.status_code == 404


# ===========================================================================
# PAYMENTS — POST /payments/verify-passkey
# ===========================================================================


class TestVerifyPasskey:
    def test_verify_passkey_without_auth_returns_401(self, client):
        """POST /payments/verify-passkey without auth returns 401."""
        resp = client.post(
            "/v1/payments/verify-passkey",
            json={"listing_id": str(uuid.uuid4()), "passkey": "12345678"},
        )
        assert resp.status_code == 401

    def test_verify_passkey_nonexistent_listing_returns_404(self, client, auth_as_buyer):
        """Spec: non-existent listing_id returns 404 'Listing not found.'"""
        resp = client.post(
            "/v1/payments/verify-passkey",
            json={"listing_id": str(uuid.uuid4()), "passkey": "12345678"},
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Listing not found."

    def test_verify_passkey_3_wrong_attempts_returns_403_on_third(
        self, client, auth_as_buyer
    ):
        """Spec DoD: 3 wrong passkeys — the third attempt itself returns 403
        ('blocked' message). Subsequent calls with correct passkey also return 403."""
        listing_id = _create_listing(seller_id=SELLER_ID, passkey="99887766")

        first = client.post(
            "/v1/payments/verify-passkey",
            json={"listing_id": listing_id, "passkey": "00000001"},
        )
        second = client.post(
            "/v1/payments/verify-passkey",
            json={"listing_id": listing_id, "passkey": "00000002"},
        )
        third = client.post(
            "/v1/payments/verify-passkey",
            json={"listing_id": listing_id, "passkey": "00000003"},
        )

        assert first.status_code == 400
        assert second.status_code == 400
        assert third.status_code == 403
        assert third.json()["detail"] == "You have been blocked from purchasing this listing."

    def test_verify_passkey_blocked_buyer_correct_passkey_still_returns_403(
        self, client, auth_as_buyer, fake_redis
    ):
        """Spec DoD: after 3 wrong attempts, even the correct passkey returns 403 —
        the Redis block check runs before hash comparison."""
        listing_id = _create_listing(seller_id=SELLER_ID, passkey="55443322")
        attempts_key = f"passkey_attempts:{listing_id}:{BUYER_ID}"
        asyncio.run(fake_redis.set(attempts_key, 3))

        resp = client.post(
            "/v1/payments/verify-passkey",
            json={"listing_id": listing_id, "passkey": "55443322"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "You have been blocked from purchasing this listing."

    def test_verify_passkey_wrong_passkey_increments_redis_attempt_counter(
        self, client, auth_as_buyer, fake_redis
    ):
        """A wrong passkey must increment the passkey_attempts Redis counter."""
        listing_id = _create_listing(seller_id=SELLER_ID, passkey="12345678")
        attempts_key = f"passkey_attempts:{listing_id}:{BUYER_ID}"

        client.post(
            "/v1/payments/verify-passkey",
            json={"listing_id": listing_id, "passkey": "00000000"},
        )

        count = asyncio.run(fake_redis.get(attempts_key))
        assert count is not None
        assert int(count) == 1

    def test_verify_passkey_attempts_key_format(self, client, auth_as_buyer, fake_redis):
        """Redis key for attempt tracking must be exactly
        `passkey_attempts:{listing_id}:{buyer_id}`."""
        listing_id = _create_listing(seller_id=SELLER_ID, passkey="12345678")
        expected_key = f"passkey_attempts:{listing_id}:{BUYER_ID}"

        client.post(
            "/v1/payments/verify-passkey",
            json={"listing_id": listing_id, "passkey": "00000000"},
        )

        for key in fake_redis._store:
            if key.startswith("passkey_attempts:"):
                assert key == expected_key, (
                    f"Unexpected attempt key: '{key}'; expected '{expected_key}'"
                )

    def test_verify_passkey_attempts_ttl_is_7_days(
        self, client, auth_as_buyer, fake_redis
    ):
        """Spec: passkey_attempts key TTL must be 7 days (604800 seconds)."""
        listing_id = _create_listing(seller_id=SELLER_ID, passkey="12345678")

        captured = {}
        real_pipeline = fake_redis.pipeline

        def _spy_pipeline():
            pipe = real_pipeline()
            real_expire = pipe.expire

            def _expire(key, ttl):
                captured["key"] = key
                captured["ttl"] = ttl
                return real_expire(key, ttl)

            pipe.expire = _expire
            return pipe

        fake_redis.pipeline = _spy_pipeline

        client.post(
            "/v1/payments/verify-passkey",
            json={"listing_id": listing_id, "passkey": "00000000"},
        )

        assert captured.get("ttl") == 604800, (
            f"Expected 7-day TTL (604800s), got {captured.get('ttl')}"
        )

    def test_verify_passkey_uses_hmac_compare_digest_not_equality(
        self, client, auth_as_buyer
    ):
        """Security rule 11: hmac.compare_digest must be used, never ==.
        Spy wraps the real function (behavior unchanged) to confirm it is called.
        A wrong passkey is submitted so no Razorpay call is made."""
        listing_id = _create_listing(seller_id=SELLER_ID, passkey="12345678")

        with mock.patch(
            "app.core.security.hmac.compare_digest", wraps=hmac.compare_digest
        ) as mock_cd:
            resp = client.post(
                "/v1/payments/verify-passkey",
                json={"listing_id": listing_id, "passkey": "00000000"},
            )

        assert resp.status_code == 400
        mock_cd.assert_called_once()

    def test_verify_passkey_response_never_contains_forbidden_transaction_fields(
        self, client, auth_as_buyer, monkeypatch
    ):
        """POST /payments/verify-passkey success response must only contain
        payment_link_url — no internal transaction fields."""
        listing_id = _create_listing(seller_id=SELLER_ID, passkey="12345678")

        fake_link = MagicMock()
        fake_link.create = mock.Mock(
            return_value={"id": "plink_fg1", "short_url": "https://rzp.io/l/fg1"}
        )
        monkeypatch.setattr(payment_service.razorpay_client, "payment_link", fake_link)

        resp = client.post(
            "/v1/payments/verify-passkey",
            json={"listing_id": listing_id, "passkey": "12345678"},
        )
        assert resp.status_code == 200
        body = resp.json()
        for forbidden in FORBIDDEN_TRANSACTION_FIELDS:
            assert forbidden not in body


# ===========================================================================
# PAYMENTS — POST /payments/webhook
# ===========================================================================


class TestWebhook:
    def test_webhook_wrong_hmac_signature_returns_400(self, client, monkeypatch):
        """Spec: invalid HMAC signature returns 400 — no processing occurs."""
        def _raise(*a, **kw):
            raise Exception("Invalid signature")

        monkeypatch.setattr(
            payment_service.razorpay_client.utility,
            "verify_webhook_signature",
            _raise,
        )

        body = json.dumps(_build_webhook_payload("payment_link.paid")).encode()
        resp = client.post(
            "/v1/payments/webhook",
            content=body,
            headers={"X-Razorpay-Signature": "bad-signature"},
        )
        assert resp.status_code == 400

    def test_webhook_unknown_event_returns_200(self, client, monkeypatch):
        """Spec Rule 3: unrecognised webhook events must return 200, never 4xx
        (prevents Razorpay retry storms)."""
        monkeypatch.setattr(
            payment_service.razorpay_client.utility,
            "verify_webhook_signature",
            lambda *a, **kw: None,
        )

        body = json.dumps(_build_webhook_payload("payment.failed")).encode()
        resp = client.post(
            "/v1/payments/webhook",
            content=body,
            headers={"X-Razorpay-Signature": "ok"},
        )
        assert resp.status_code == 200

    def test_webhook_does_not_require_bearer_token(self, client, monkeypatch):
        """Spec: POST /payments/webhook is 'no auth' — no Authorization header.
        A request without a token must reach signature verification (not 401)."""
        def _raise(*a, **kw):
            raise Exception("bad sig")

        monkeypatch.setattr(
            payment_service.razorpay_client.utility,
            "verify_webhook_signature",
            _raise,
        )

        body = json.dumps(_build_webhook_payload("payment_link.paid")).encode()
        resp = client.post(
            "/v1/payments/webhook",
            content=body,
            headers={"X-Razorpay-Signature": "bogus"},
        )
        assert resp.status_code != 401

    def test_webhook_unknown_payment_link_id_returns_200(self, client, monkeypatch):
        """Spec: an unknown payment_link_id must return 200 — not 404."""
        monkeypatch.setattr(
            payment_service.razorpay_client.utility,
            "verify_webhook_signature",
            lambda *a, **kw: None,
        )

        body = json.dumps(
            _build_webhook_payload(
                "payment_link.paid",
                payment_link_id="plink_does_not_exist_abc",
            )
        ).encode()
        resp = client.post(
            "/v1/payments/webhook",
            content=body,
            headers={"X-Razorpay-Signature": "ok"},
        )
        assert resp.status_code == 200


# ===========================================================================
# TRANSACTIONS — GET /transactions/{id}/status
# ===========================================================================


class TestTransactionStatus:
    def test_get_status_without_auth_returns_401(self, client):
        """GET /transactions/{id}/status without auth returns 401."""
        resp = client.get(f"/v1/transactions/{uuid.uuid4()}/status")
        assert resp.status_code == 401

    def test_get_status_by_non_buyer_returns_404(self, client, auth_as_other):
        """Spec: a user who is not the buyer receives 404 (not 403) — avoids
        confirming the transaction's existence to non-owners."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        txn_id, _ = _seed_transaction(listing_id, BUYER_ID, status="initiated")

        resp = client.get(f"/v1/transactions/{txn_id}/status")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Transaction not found."

    def test_get_status_nonexistent_transaction_returns_404(self, client, auth_as_buyer):
        """GET /transactions/{id}/status for a non-existent UUID returns 404."""
        resp = client.get(f"/v1/transactions/{uuid.uuid4()}/status")
        assert resp.status_code == 404

    def test_get_status_by_owning_buyer_returns_200_with_status_and_amount(
        self, client, auth_as_buyer
    ):
        """GET /transactions/{id}/status by the owning buyer returns 200
        with status and amount_rupees."""
        listing_id = _create_listing(seller_id=SELLER_ID, asking_price=420)
        txn_id, _ = _seed_transaction(listing_id, BUYER_ID, status="initiated", amount_rupees=420)

        resp = client.get(f"/v1/transactions/{txn_id}/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "initiated"
        assert body["amount_rupees"] == 420
        assert isinstance(body["amount_rupees"], int)

    def test_get_status_amount_rupees_is_whole_integer_not_paise(
        self, client, auth_as_buyer
    ):
        """amount_rupees in the status response must be whole rupees, not paise."""
        listing_id = _create_listing(seller_id=SELLER_ID, asking_price=250)
        txn_id, _ = _seed_transaction(listing_id, BUYER_ID, status="initiated", amount_rupees=250)

        resp = client.get(f"/v1/transactions/{txn_id}/status")
        assert resp.status_code == 200
        assert resp.json()["amount_rupees"] == 250
        assert resp.json()["amount_rupees"] != 250 * 100

    def test_get_status_response_only_contains_status_and_amount(
        self, client, auth_as_buyer
    ):
        """The status endpoint response must contain ONLY status and amount_rupees —
        no internal transaction fields exposed."""
        listing_id = _create_listing(seller_id=SELLER_ID, asking_price=199)
        txn_id, _ = _seed_transaction(listing_id, BUYER_ID, status="initiated", amount_rupees=199)

        resp = client.get(f"/v1/transactions/{txn_id}/status")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"status", "amount_rupees"}

        for forbidden in FORBIDDEN_TRANSACTION_FIELDS:
            assert forbidden not in body

    def test_get_status_never_returns_invalid_status_value(
        self, client, auth_as_buyer
    ):
        """Transaction status must only ever be 'initiated', 'released', or 'cancelled'."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        for status in ("initiated", "released", "cancelled"):
            txn_id, _ = _seed_transaction(
                listing_id,
                BUYER_ID,
                status=status,
                payment_link_id=f"plink_{status}_{uuid.uuid4().hex[:6]}",
            )
            resp = client.get(f"/v1/transactions/{txn_id}/status")
            assert resp.status_code == 200
            returned_status = resp.json()["status"]
            assert returned_status in ("initiated", "released", "cancelled"), (
                f"Unexpected status: '{returned_status}'"
            )
            assert returned_status not in ("disputed", "confirmed", "paid", "pending"), (
                f"Invalid status '{returned_status}' returned"
            )


# ===========================================================================
# FIELDS NEVER RETURNED — cross-cutting response body checks
# ===========================================================================


class TestFieldsNeverReturned:
    """Spec section 'Fields never returned in any response'.
    These fields exist in the DB but must never appear in any API response."""

    def test_listing_index_response_never_contains_passkey_hash(self, client):
        _create_listing()
        resp = client.get("/v1/listings")
        assert resp.status_code == 200
        for item in resp.json():
            assert "passkey_hash" not in item

    def test_listing_detail_response_never_contains_passkey_hash(self, client):
        listing_id = _create_listing()
        resp = client.get(f"/v1/listings/{listing_id}")
        assert resp.status_code == 200
        assert "passkey_hash" not in resp.json()

    def test_listing_detail_response_never_contains_passkey_invalidated(self, client):
        listing_id = _create_listing()
        resp = client.get(f"/v1/listings/{listing_id}")
        assert "passkey_invalidated" not in resp.json()

    def test_listing_detail_response_never_contains_passkey_invalidated_at(self, client):
        listing_id = _create_listing()
        resp = client.get(f"/v1/listings/{listing_id}")
        assert "passkey_invalidated_at" not in resp.json()

    def test_listing_detail_response_never_contains_sold_at(self, client):
        listing_id = _create_listing()
        resp = client.get(f"/v1/listings/{listing_id}")
        assert "sold_at" not in resp.json()

    def test_listing_detail_response_never_contains_deleted_at(self, client):
        listing_id = _create_listing()
        resp = client.get(f"/v1/listings/{listing_id}")
        assert "deleted_at" not in resp.json()

    def test_public_user_response_never_contains_razorpay_account_id(self, client):
        resp = client.get(f"/v1/users/{SELLER_ID}")
        assert resp.status_code == 200
        assert "razorpay_account_id" not in resp.json()

    def test_transaction_status_response_never_contains_razorpay_payment_link_id(
        self, client, auth_as_buyer
    ):
        listing_id = _create_listing(seller_id=SELLER_ID)
        txn_id, _ = _seed_transaction(listing_id, BUYER_ID, status="initiated")
        resp = client.get(f"/v1/transactions/{txn_id}/status")
        assert resp.status_code == 200
        assert "razorpay_payment_link_id" not in resp.json()

    def test_transaction_status_response_never_contains_razorpay_payment_id(
        self, client, auth_as_buyer
    ):
        listing_id = _create_listing(seller_id=SELLER_ID)
        txn_id, _ = _seed_transaction(listing_id, BUYER_ID, status="initiated")
        resp = client.get(f"/v1/transactions/{txn_id}/status")
        assert resp.status_code == 200
        assert "razorpay_payment_id" not in resp.json()

    def test_transaction_status_response_never_contains_platform_fee_rupees(
        self, client, auth_as_buyer
    ):
        listing_id = _create_listing(seller_id=SELLER_ID)
        txn_id, _ = _seed_transaction(listing_id, BUYER_ID, status="initiated")
        resp = client.get(f"/v1/transactions/{txn_id}/status")
        assert resp.status_code == 200
        assert "platform_fee_rupees" not in resp.json()

    def test_transaction_status_response_never_contains_seller_payout_rupees(
        self, client, auth_as_buyer
    ):
        listing_id = _create_listing(seller_id=SELLER_ID)
        txn_id, _ = _seed_transaction(listing_id, BUYER_ID, status="initiated")
        resp = client.get(f"/v1/transactions/{txn_id}/status")
        assert resp.status_code == 200
        assert "seller_payout_rupees" not in resp.json()

    def test_transaction_status_response_never_contains_refunded_at(
        self, client, auth_as_buyer
    ):
        listing_id = _create_listing(seller_id=SELLER_ID)
        txn_id, _ = _seed_transaction(listing_id, BUYER_ID, status="initiated")
        resp = client.get(f"/v1/transactions/{txn_id}/status")
        assert resp.status_code == 200
        assert "refunded_at" not in resp.json()

    def test_transaction_status_response_never_contains_released_at(
        self, client, auth_as_buyer
    ):
        listing_id = _create_listing(seller_id=SELLER_ID)
        txn_id, _ = _seed_transaction(listing_id, BUYER_ID, status="initiated")
        resp = client.get(f"/v1/transactions/{txn_id}/status")
        assert resp.status_code == 200
        assert "released_at" not in resp.json()

    def test_conversations_response_never_contains_first_message_notified(
        self, client, auth_as_buyer
    ):
        listing_id = _create_listing(seller_id=SELLER_ID)
        _create_conversation(listing_id)
        resp = client.get("/v1/conversations")
        assert resp.status_code == 200
        for conv in resp.json():
            assert "first_message_notified" not in conv

    def test_create_listing_response_never_contains_passkey_hash(
        self, client, auth_as_seller
    ):
        """The nested listing object in the 201 response must not contain passkey_hash."""
        payload = dict(VALID_LISTING_PAYLOAD)
        payload["title"] = f"No hash test {uuid.uuid4()}"
        resp = client.post("/v1/listings", json=payload)
        assert resp.status_code == 201
        listing_part = resp.json().get("listing", {})
        assert "passkey_hash" not in listing_part


# ===========================================================================
# CORS
# ===========================================================================


class TestCors:
    def test_options_request_to_listings_includes_frontend_url_in_origin(self, client):
        """Spec: CORS must only allow FRONTEND_URL, never *.
        An OPTIONS preflight from the declared FRONTEND_URL must return
        the same origin in Access-Control-Allow-Origin, not '*'."""
        resp = client.options(
            "/v1/listings",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        allow_origin = resp.headers.get("access-control-allow-origin", "")
        assert allow_origin != "*", (
            "CORS must not allow wildcard '*' — must be restricted to FRONTEND_URL"
        )
        assert allow_origin == "http://localhost:3000", (
            f"Expected 'http://localhost:3000' in Access-Control-Allow-Origin, got '{allow_origin}'"
        )

    def test_options_request_from_unknown_origin_does_not_reflect_origin(self, client):
        """Spec: CORS must not reflect arbitrary origins.
        A preflight from an unknown origin must not receive a permissive Allow-Origin."""
        resp = client.options(
            "/v1/listings",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        allow_origin = resp.headers.get("access-control-allow-origin", "")
        assert allow_origin != "https://evil.example.com", (
            "CORS must not reflect unknown origins"
        )
        assert allow_origin != "*", (
            "CORS must not use wildcard '*'"
        )

    def test_cors_middleware_configured_with_frontend_url_not_wildcard(self):
        """Inspect the CORSMiddleware configuration attached to the FastAPI app
        to confirm allow_origins does not contain '*'."""
        from starlette.middleware.cors import CORSMiddleware as StarletteCORS

        cors_middleware = None
        for middleware in app.user_middleware:
            if middleware.cls is StarletteCORS:
                cors_middleware = middleware
                break

        assert cors_middleware is not None, "CORSMiddleware must be registered"
        origins = cors_middleware.kwargs.get("allow_origins", [])
        assert "*" not in origins, (
            "CORS allow_origins must not contain '*' — use FRONTEND_URL only"
        )
        assert "http://localhost:3000" in origins, (
            "CORS allow_origins must include FRONTEND_URL (http://localhost:3000)"
        )


# ===========================================================================
# AUTH — user identity is payload["sub"] (UUID), not email
# ===========================================================================


class TestAuthIdentity:
    def test_missing_authorization_header_returns_401_on_protected_route(self, client):
        """Any protected route called without Authorization header returns 401."""
        resp = client.post("/v1/listings", json=VALID_LISTING_PAYLOAD)
        assert resp.status_code == 401

    def test_invalid_bearer_token_returns_401(self, client):
        """A malformed Bearer token value returns 401."""
        resp = client.get(
            "/v1/users/me",
            headers={"Authorization": "Bearer not-a-real-jwt"},
        )
        assert resp.status_code == 401

    def test_user_sub_is_used_as_identity_not_email(self, client, auth_as_seller):
        """GET /users/me with a token whose sub=SELLER_ID must return the correct
        user — identity is payload['sub'] (UUID), never email."""
        resp = client.get("/v1/users/me")
        assert resp.status_code == 200
        assert resp.json()["id"] == SELLER_ID

    def test_patch_listing_uses_sub_for_ownership_check(self, client, auth_as_buyer):
        """PATCH /listings/{id} ownership check must use payload['sub'],
        so auth_as_buyer (different sub) correctly receives 403 on seller's listing."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        resp = client.patch(f"/v1/listings/{listing_id}", json={"city": "Pune"})
        assert resp.status_code == 403


# ===========================================================================
# PRICE RULES — paise conversion only at Razorpay boundary
# ===========================================================================


class TestPriceRules:
    def test_listing_asking_price_in_response_is_never_paise(self, client, auth_as_seller):
        """POST /listings returns asking_price in whole rupees — never paise (never * 100)."""
        payload = dict(VALID_LISTING_PAYLOAD)
        payload["title"] = f"Price paise check {uuid.uuid4()}"
        payload["asking_price"] = 350
        resp = client.post("/v1/listings", json=payload)
        assert resp.status_code == 201
        assert resp.json()["listing"]["asking_price"] == 350

    def test_transaction_status_amount_rupees_is_never_paise(
        self, client, auth_as_buyer
    ):
        """GET /transactions/{id}/status returns amount_rupees in whole rupees."""
        listing_id = _create_listing(seller_id=SELLER_ID, asking_price=500)
        txn_id, _ = _seed_transaction(listing_id, BUYER_ID, status="initiated", amount_rupees=500)
        resp = client.get(f"/v1/transactions/{txn_id}/status")
        assert resp.status_code == 200
        assert resp.json()["amount_rupees"] == 500
        # Confirm the value is not mistakenly stored in paise
        assert resp.json()["amount_rupees"] != 500 * 100

    def test_verify_passkey_payment_link_amount_is_rupees_times_100(
        self, client, auth_as_buyer, monkeypatch
    ):
        """Spec: paise conversion happens only at razorpay_client.payment_link.create().
        The 'amount' field passed to Razorpay must be asking_price * 100."""
        listing_id = _create_listing(seller_id=SELLER_ID, asking_price=350, passkey="12345678")

        fake_link = MagicMock()
        create_calls = []

        def _capture_create(payload):
            create_calls.append(payload)
            return {"id": "plink_paise_test", "short_url": "https://rzp.io/l/paisetest"}

        fake_link.create = _capture_create
        monkeypatch.setattr(payment_service.razorpay_client, "payment_link", fake_link)

        resp = client.post(
            "/v1/payments/verify-passkey",
            json={"listing_id": listing_id, "passkey": "12345678"},
        )
        assert resp.status_code == 200
        assert len(create_calls) == 1
        assert create_calls[0]["amount"] == 350 * 100
        assert create_calls[0]["currency"] == "INR"

    def test_verify_passkey_response_does_not_contain_amount_field(
        self, client, auth_as_buyer, monkeypatch
    ):
        """POST /payments/verify-passkey response is only payment_link_url —
        no amount field is ever returned to the buyer."""
        listing_id = _create_listing(seller_id=SELLER_ID, asking_price=350, passkey="12345678")

        fake_link = MagicMock()
        fake_link.create = mock.Mock(
            return_value={"id": "plink_noamt", "short_url": "https://rzp.io/l/noamt"}
        )
        monkeypatch.setattr(payment_service.razorpay_client, "payment_link", fake_link)

        resp = client.post(
            "/v1/payments/verify-passkey",
            json={"listing_id": listing_id, "passkey": "12345678"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "amount" not in body
        assert "amount_paise" not in body


# ===========================================================================
# ROUTE REGISTRATION — confirm all spec-documented endpoints exist on app
# ===========================================================================


class TestRouteRegistration:
    @staticmethod
    def _registered_paths():
        return {route.path for route in app.routes}

    def test_listings_get_route_registered(self):
        assert "/v1/listings" in self._registered_paths()

    def test_listings_post_route_registered(self):
        assert "/v1/listings" in self._registered_paths()

    def test_listing_detail_route_registered(self):
        assert "/v1/listings/{listing_id}" in self._registered_paths()

    def test_listing_passkey_route_registered(self):
        assert "/v1/listings/{listing_id}/passkey" in self._registered_paths()

    def test_users_me_route_registered(self):
        assert "/v1/users/me" in self._registered_paths()

    def test_users_public_route_registered(self):
        assert "/v1/users/{user_id}" in self._registered_paths()

    def test_conversations_route_registered(self):
        assert "/v1/conversations" in self._registered_paths()

    def test_conversations_messages_route_registered(self):
        assert "/v1/conversations/{conversation_id}/messages" in self._registered_paths()

    def test_conversations_messages_read_route_registered(self):
        assert "/v1/conversations/{conversation_id}/messages/read" in self._registered_paths()

    def test_payments_verify_passkey_route_registered(self):
        assert "/v1/payments/verify-passkey" in self._registered_paths()

    def test_payments_webhook_route_registered(self):
        assert "/v1/payments/webhook" in self._registered_paths()

    def test_transactions_status_route_registered(self):
        assert "/v1/transactions/{transaction_id}/status" in self._registered_paths()

    def test_payments_onboard_route_registered(self):
        assert "/v1/payments/onboard" in self._registered_paths()

    def test_payments_onboard_complete_route_registered(self):
        assert "/v1/payments/onboard/complete" in self._registered_paths()

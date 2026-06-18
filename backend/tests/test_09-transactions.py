"""
Tests for the passkey-verified transaction flow (replaces the removed payment flow).

Endpoints under test:
  POST   /v1/transactions/verify-passkey   — buyer enters 8-digit code; marks listing SOLD
  GET    /v1/transactions                   — caller's transactions (buyer + seller)
  POST   /v1/transactions/{id}/rating       — buyer rates the seller, once

Derived from .claude/docs/TRANSACTIONS.md, .claude/docs/SCHEMA.md and CLAUDE.md —
not from reading the implementation. Auth is mocked via FastAPI dependency overrides
on `verify_token`; Redis is an in-memory fake; Resend/Supabase-admin are mocked. The
DB is real (AsyncSessionLocal) — run after `alembic upgrade head`.

Run from project root:
    cd backend && ..\\.venv\\Scripts\\python.exe -m pytest tests/test_09-transactions.py -v
"""
import asyncio
import hmac
import uuid
from unittest import mock

import pytest
from sqlalchemy import text
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import verify_token, hash_passkey
from app.core.redis import get_redis
from app.core.database import AsyncSessionLocal


SELLER_ID = str(uuid.uuid4())
BUYER_ID = str(uuid.uuid4())
OTHER_BUYER_ID = str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _override_verify_token(user_id: str, email: str | None = None):
    def _inner():
        return {"sub": user_id, "email": email or f"{user_id}@example.com"}
    return _inner


class FakeRedis:
    """Minimal in-memory async Redis stand-in: get/set/incr/expire via pipeline."""

    def __init__(self):
        self._store = {}

    async def get(self, key):
        return self._store.get(key)

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self._store:
            return None
        self._store[key] = str(value)
        return True

    def pipeline(self):
        outer = self

        class _Pipe:
            def __init__(self):
                self._ops = []

            def incr(self, key):
                self._ops.append(("incr", key))
                return self

            def expire(self, key, ttl):
                self._ops.append(("expire", key, ttl))
                return self

            async def execute(self):
                results = []
                for op in self._ops:
                    if op[0] == "incr":
                        current = int(outer._store.get(op[1], "0")) + 1
                        outer._store[op[1]] = str(current)
                        results.append(current)
                    else:
                        results.append(True)
                self._ops = []
                return results

        return _Pipe()


@pytest.fixture
def fake_redis():
    return FakeRedis()


@pytest.fixture
def client(fake_redis):
    async def _get_redis_override():
        yield fake_redis

    app.dependency_overrides[get_redis] = _get_redis_override
    # The sale-complete email runs as a BackgroundTask; stub the email resolution
    # so no Supabase Admin / Resend network call happens during tests.
    with mock.patch("app.routers.transactions.fetch_user_email", new=mock.AsyncMock(return_value=None)):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.clear()


async def _seed_users_async():
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(
                """
                INSERT INTO public.users (id, full_name, books_sold, books_bought, is_verified)
                VALUES (:seller_id, 'Test Seller', 0, 0, FALSE),
                       (:buyer_id, 'Test Buyer', 0, 0, FALSE),
                       (:other_buyer_id, 'Test Other Buyer', 0, 0, FALSE)
                ON CONFLICT (id) DO UPDATE
                  SET books_sold = 0, books_bought = 0, is_verified = FALSE, seller_rating = NULL
                """
            ),
            {"seller_id": SELLER_ID, "buyer_id": BUYER_ID, "other_buyer_id": OTHER_BUYER_ID},
        )
        await session.commit()


async def _cleanup_async():
    async with AsyncSessionLocal() as session:
        ids = [SELLER_ID, BUYER_ID, OTHER_BUYER_ID]
        await session.execute(
            text("DELETE FROM public.seller_ratings WHERE seller_id = ANY(:ids) OR rated_by = ANY(:ids)"),
            {"ids": ids},
        )
        await session.execute(
            text("DELETE FROM public.transactions WHERE seller_id = ANY(:ids) OR buyer_id = ANY(:ids)"),
            {"ids": ids},
        )
        await session.execute(text("DELETE FROM public.listings WHERE seller_id = ANY(:ids)"), {"ids": ids})
        await session.execute(text("DELETE FROM public.users WHERE id = ANY(:ids)"), {"ids": ids})
        await session.commit()


@pytest.fixture(autouse=True)
def _seed_test_data():
    asyncio.run(_seed_users_async())
    yield
    asyncio.run(_cleanup_async())


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
def auth_as_other_buyer():
    app.dependency_overrides[verify_token] = _override_verify_token(OTHER_BUYER_ID)
    yield OTHER_BUYER_ID
    app.dependency_overrides.pop(verify_token, None)


def _create_listing_direct(passkey="12345678", asking_price=350, seller_id=SELLER_ID, title="Listing under test"):
    listing_id = str(uuid.uuid4())
    passkey_hash = hash_passkey(passkey, listing_id)

    async def _insert():
        async with AsyncSessionLocal() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO public.listings
                        (id, seller_id, title, description, exam_category, subject,
                         listing_type, condition, asking_price, original_price, city,
                         images, is_available, passkey_hash)
                    VALUES
                        (:id, :seller_id, :title, 'desc', 'JEE_MAINS', 'Physics',
                         'BOOK', 'A', :asking_price, 600, 'Delhi',
                         ARRAY['https://res.cloudinary.com/demo/image/upload/v1/x.jpg'],
                         TRUE, :passkey_hash)
                    """
                ),
                {"id": listing_id, "seller_id": seller_id, "title": title,
                 "asking_price": asking_price, "passkey_hash": passkey_hash},
            )
            await session.commit()

    asyncio.run(_insert())
    return listing_id, passkey


def _set_listing_state(listing_id, *, is_available=None, passkey_invalidated=None, sold_at=None):
    async def _update():
        async with AsyncSessionLocal() as session:
            sets, params = [], {"id": listing_id}
            if is_available is not None:
                sets.append("is_available = :is_available"); params["is_available"] = is_available
            if passkey_invalidated is not None:
                sets.append("passkey_invalidated = :pi"); params["pi"] = passkey_invalidated
            if sold_at is not None:
                sets.append("sold_at = :sold_at"); params["sold_at"] = sold_at
            if sets:
                await session.execute(text(f"UPDATE public.listings SET {', '.join(sets)} WHERE id = :id"), params)
                await session.commit()

    asyncio.run(_update())


def _set_user(user_id, **fields):
    async def _update():
        async with AsyncSessionLocal() as session:
            sets = ", ".join(f"{k} = :{k}" for k in fields)
            await session.execute(
                text(f"UPDATE public.users SET {sets} WHERE id = :id"), {**fields, "id": user_id}
            )
            await session.commit()

    asyncio.run(_update())


def _get_user_row(user_id):
    async def _fetch():
        async with AsyncSessionLocal() as session:
            r = await session.execute(text("SELECT * FROM public.users WHERE id = :id"), {"id": user_id})
            row = r.mappings().first()
            return dict(row) if row else None

    return asyncio.run(_fetch())


def _get_listing_row(listing_id):
    async def _fetch():
        async with AsyncSessionLocal() as session:
            r = await session.execute(text("SELECT * FROM public.listings WHERE id = :id"), {"id": listing_id})
            row = r.mappings().first()
            return dict(row) if row else None

    return asyncio.run(_fetch())


# ===========================================================================
# Auth guards
# ===========================================================================

def test_verify_passkey_without_auth_returns_401(client):
    resp = client.post("/v1/transactions/verify-passkey", json={"listing_id": str(uuid.uuid4()), "passkey": "12345678"})
    assert resp.status_code == 401


def test_list_transactions_without_auth_returns_401(client):
    assert client.get("/v1/transactions").status_code == 401


def test_rating_without_auth_returns_401(client):
    resp = client.post(f"/v1/transactions/{uuid.uuid4()}/rating", json={"rating": 5})
    assert resp.status_code == 401


# ===========================================================================
# verify-passkey — happy path completion
# ===========================================================================

def test_verify_passkey_correct_marks_listing_sold_and_returns_transaction(client, auth_as_buyer):
    listing_id, passkey = _create_listing_direct()

    resp = client.post("/v1/transactions/verify-passkey", json={"listing_id": listing_id, "passkey": passkey})
    assert resp.status_code == 200
    body = resp.json()
    assert uuid.UUID(body["transaction_id"])
    assert body["seller_id"] == SELLER_ID
    assert body["seller_name"] == "Test Seller"
    assert body["listing_title"] == "Listing under test"

    listing = _get_listing_row(listing_id)
    assert listing["is_available"] is False
    assert listing["passkey_invalidated"] is True
    assert listing["sold_at"] is not None


def test_verify_passkey_increments_books_sold_and_books_bought(client, auth_as_buyer):
    listing_id, passkey = _create_listing_direct()
    client.post("/v1/transactions/verify-passkey", json={"listing_id": listing_id, "passkey": passkey})

    assert _get_user_row(SELLER_ID)["books_sold"] == 1
    assert _get_user_row(BUYER_ID)["books_bought"] == 1


def test_verify_passkey_creates_one_transaction_row(client, auth_as_buyer):
    listing_id, passkey = _create_listing_direct()
    client.post("/v1/transactions/verify-passkey", json={"listing_id": listing_id, "passkey": passkey})

    async def _count():
        async with AsyncSessionLocal() as session:
            r = await session.execute(
                text("SELECT COUNT(*) FROM public.transactions WHERE listing_id = :lid"), {"lid": listing_id}
            )
            return r.scalar_one()

    assert asyncio.run(_count()) == 1


# ===========================================================================
# verify-passkey — check ordering / failures
# ===========================================================================

def test_verify_passkey_already_sold_returns_400(client, auth_as_buyer):
    listing_id, passkey = _create_listing_direct()
    _set_listing_state(listing_id, is_available=False, passkey_invalidated=True)

    resp = client.post("/v1/transactions/verify-passkey", json={"listing_id": listing_id, "passkey": passkey})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "This listing has already been sold."


def test_verify_passkey_paused_returns_400(client, auth_as_buyer):
    listing_id, passkey = _create_listing_direct()
    _set_listing_state(listing_id, is_available=False)

    resp = client.post("/v1/transactions/verify-passkey", json={"listing_id": listing_id, "passkey": passkey})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "This listing is temporarily unavailable."


def test_verify_passkey_self_purchase_returns_403(client, auth_as_seller):
    listing_id, passkey = _create_listing_direct(seller_id=SELLER_ID)
    resp = client.post("/v1/transactions/verify-passkey", json={"listing_id": listing_id, "passkey": passkey})
    assert resp.status_code == 403
    assert resp.json()["detail"] == "You cannot purchase your own listing."


def test_verify_passkey_wrong_value_increments_attempts_and_reports_remaining(client, auth_as_buyer, fake_redis):
    listing_id, _ = _create_listing_direct()
    attempts_key = f"passkey_attempts:{listing_id}:{BUYER_ID}"

    resp = client.post("/v1/transactions/verify-passkey", json={"listing_id": listing_id, "passkey": "00000000"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Incorrect passkey. 2 attempts remaining."
    assert int(asyncio.run(fake_redis.get(attempts_key))) == 1


def test_verify_passkey_third_wrong_attempt_blocks(client, auth_as_buyer):
    listing_id, correct = _create_listing_direct()
    client.post("/v1/transactions/verify-passkey", json={"listing_id": listing_id, "passkey": "00000000"})
    client.post("/v1/transactions/verify-passkey", json={"listing_id": listing_id, "passkey": "00000001"})
    third = client.post("/v1/transactions/verify-passkey", json={"listing_id": listing_id, "passkey": "00000002"})
    assert third.status_code == 403
    assert third.json()["detail"] == "You have been blocked from this listing."

    # Even the correct passkey is now rejected (block check precedes hash check)
    after = client.post("/v1/transactions/verify-passkey", json={"listing_id": listing_id, "passkey": correct})
    assert after.status_code == 403


def test_verify_passkey_uses_compare_digest(client, auth_as_buyer):
    listing_id, _ = _create_listing_direct()
    with mock.patch("app.core.security.hmac.compare_digest", wraps=hmac.compare_digest) as cd:
        resp = client.post("/v1/transactions/verify-passkey", json={"listing_id": listing_id, "passkey": "00000000"})
    assert resp.status_code == 400
    cd.assert_called_once()


def test_verify_passkey_attempt_counter_has_seven_day_ttl(client, auth_as_buyer, fake_redis):
    listing_id, _ = _create_listing_direct()
    captured = {}
    real_pipeline = fake_redis.pipeline

    def _spy():
        pipe = real_pipeline()
        real_expire = pipe.expire

        def _expire(key, ttl):
            captured["ttl"] = ttl
            return real_expire(key, ttl)

        pipe.expire = _expire
        return pipe

    fake_redis.pipeline = _spy
    client.post("/v1/transactions/verify-passkey", json={"listing_id": listing_id, "passkey": "00000000"})
    assert captured.get("ttl") == 604800


def test_verify_passkey_response_has_no_contact_fields(client, auth_as_buyer):
    listing_id, passkey = _create_listing_direct()
    resp = client.post("/v1/transactions/verify-passkey", json={"listing_id": listing_id, "passkey": passkey})
    raw = resp.text.lower()
    for forbidden in ("email", "phone", "contact", "passkey", "passkey_hash"):
        assert forbidden not in raw


# ===========================================================================
# Verification badge — auto at 10 verified sales
# ===========================================================================

def test_badge_awarded_when_books_sold_reaches_ten(client, auth_as_buyer):
    _set_user(SELLER_ID, books_sold=9, is_verified=False)
    listing_id, passkey = _create_listing_direct()

    client.post("/v1/transactions/verify-passkey", json={"listing_id": listing_id, "passkey": passkey})

    seller = _get_user_row(SELLER_ID)
    assert seller["books_sold"] == 10
    assert seller["is_verified"] is True


def test_badge_not_awarded_below_threshold(client, auth_as_buyer):
    _set_user(SELLER_ID, books_sold=3, is_verified=False)
    listing_id, passkey = _create_listing_direct()

    client.post("/v1/transactions/verify-passkey", json={"listing_id": listing_id, "passkey": passkey})

    seller = _get_user_row(SELLER_ID)
    assert seller["books_sold"] == 4
    assert seller["is_verified"] is False


# ===========================================================================
# Ratings — buyer only, once, recompute average
# ===========================================================================

def _complete(client, listing_id, passkey):
    resp = client.post("/v1/transactions/verify-passkey", json={"listing_id": listing_id, "passkey": passkey})
    assert resp.status_code == 200
    return resp.json()["transaction_id"]


def test_buyer_can_rate_and_average_is_recomputed(client, auth_as_buyer):
    listing_id, passkey = _create_listing_direct()
    txn_id = _complete(client, listing_id, passkey)

    resp = client.post(f"/v1/transactions/{txn_id}/rating", json={"rating": 4, "review": "Smooth meetup"})
    assert resp.status_code == 200
    assert resp.json()["rating"] == 4
    assert resp.json()["seller_rating"] == 4.0
    assert float(_get_user_row(SELLER_ID)["seller_rating"]) == 4.0


def test_rating_twice_returns_409(client, auth_as_buyer):
    listing_id, passkey = _create_listing_direct()
    txn_id = _complete(client, listing_id, passkey)

    assert client.post(f"/v1/transactions/{txn_id}/rating", json={"rating": 5}).status_code == 200
    second = client.post(f"/v1/transactions/{txn_id}/rating", json={"rating": 3})
    assert second.status_code == 409


def test_only_buyer_can_rate(client, auth_as_buyer, auth_as_seller):
    # complete as buyer first
    app.dependency_overrides[verify_token] = _override_verify_token(BUYER_ID)
    listing_id, passkey = _create_listing_direct()
    txn_id = _complete(client, listing_id, passkey)

    # now act as the seller — must be rejected
    app.dependency_overrides[verify_token] = _override_verify_token(SELLER_ID)
    resp = client.post(f"/v1/transactions/{txn_id}/rating", json={"rating": 5})
    assert resp.status_code == 403


def test_rating_out_of_range_returns_422(client, auth_as_buyer):
    listing_id, passkey = _create_listing_direct()
    txn_id = _complete(client, listing_id, passkey)
    assert client.post(f"/v1/transactions/{txn_id}/rating", json={"rating": 6}).status_code == 422
    assert client.post(f"/v1/transactions/{txn_id}/rating", json={"rating": 0}).status_code == 422


# ===========================================================================
# GET /transactions — listing + can_rate flag
# ===========================================================================

def test_list_transactions_flags_can_rate_for_unrated_buyer(client, auth_as_buyer):
    listing_id, passkey = _create_listing_direct()
    txn_id = _complete(client, listing_id, passkey)

    rows = client.get("/v1/transactions").json()
    mine = next(r for r in rows if r["id"] == txn_id)
    assert mine["role"] == "buyer"
    assert mine["can_rate"] is True
    assert mine["listing_title"] == "Listing under test"

    client.post(f"/v1/transactions/{txn_id}/rating", json={"rating": 5})
    rows_after = client.get("/v1/transactions").json()
    assert next(r for r in rows_after if r["id"] == txn_id)["can_rate"] is False


def test_list_transactions_seller_side_cannot_rate(client, auth_as_buyer, auth_as_seller):
    app.dependency_overrides[verify_token] = _override_verify_token(BUYER_ID)
    listing_id, passkey = _create_listing_direct()
    _complete(client, listing_id, passkey)

    app.dependency_overrides[verify_token] = _override_verify_token(SELLER_ID)
    rows = client.get("/v1/transactions").json()
    assert rows, "seller should see the sale"
    assert all(r["role"] == "seller" and r["can_rate"] is False for r in rows)

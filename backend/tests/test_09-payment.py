"""
Tests for Spec 09 — Payment.

Endpoints under test:
  POST   /v1/payments/verify-passkey
  POST   /v1/payments/onboard
  POST   /v1/payments/onboard/complete
  POST   /v1/payments/webhook
  GET    /v1/transactions/{id}/status

These tests are derived from .claude/specs/technical/09-payment.md,
.claude/docs/PAYMENT.md, .claude/docs/AUTH.md, .claude/docs/SCHEMA.md, and
.claude/CLAUDE.md — NOT from reading the implementation. Auth is mocked via
FastAPI dependency overrides on `verify_token` (matching test_14-listings-crud.py
conventions); Razorpay/Redis/Resend/Supabase-admin calls are mocked — no live
network calls are made.

Run from project root:
    cd backend && ..\\.venv\\Scripts\\python.exe -m pytest tests/test_09-payment.py -v
"""
import asyncio
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta
from unittest import mock

import pytest
from sqlalchemy import text
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import verify_token, hash_passkey
from app.core.database import get_db, AsyncSessionLocal
from app.core.redis import get_redis
from app.services import payment_service


SELLER_ID = str(uuid.uuid4())
BUYER_ID = str(uuid.uuid4())
OTHER_BUYER_ID = str(uuid.uuid4())

VALID_LISTING_PAYLOAD = {
    "title": "HC Verma Part 1",
    "description": "Lightly used physics book",
    "exam_category": "JEE_MAINS",
    "subject": "Physics",
    "listing_type": "BOOK",
    "condition": "A",
    "asking_price": 350,
    "original_price": 600,
    "city": "Delhi",
    "images": ["https://res.cloudinary.com/demo/image/upload/v1/sample.jpg"],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _override_verify_token(user_id: str, email: str | None = None):
    def _inner():
        return {"sub": user_id, "email": email or f"{user_id}@example.com"}
    return _inner


class FakeRedis:
    """Minimal in-memory async Redis stand-in supporting get/incr/expire/pipeline/set."""

    def __init__(self):
        self._store = {}

    async def get(self, key):
        return self._store.get(key)

    async def set(self, key, value, ex=None):
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
                        key = op[1]
                        current = int(outer._store.get(key, "0")) + 1
                        outer._store[key] = str(current)
                        results.append(current)
                    elif op[0] == "expire":
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
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# DB seeding — users + listings + transactions
# ---------------------------------------------------------------------------

async def _seed_users_async():
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(
                """
                INSERT INTO public.users (id, full_name, razorpay_account_id)
                VALUES (:seller_id, :seller_name, :seller_account),
                       (:buyer_id, :buyer_name, NULL),
                       (:other_buyer_id, :other_buyer_name, NULL)
                ON CONFLICT (id) DO UPDATE SET razorpay_account_id = EXCLUDED.razorpay_account_id
                """
            ),
            {
                "seller_id": SELLER_ID,
                "seller_name": "Test Seller",
                "seller_account": "acc_seller_test123",
                "buyer_id": BUYER_ID,
                "buyer_name": "Test Buyer",
                "other_buyer_id": OTHER_BUYER_ID,
                "other_buyer_name": "Test Other Buyer",
            },
        )
        await session.commit()


async def _cleanup_async():
    async with AsyncSessionLocal() as session:
        ids = (SELLER_ID, BUYER_ID, OTHER_BUYER_ID)
        await session.execute(
            text("DELETE FROM public.transactions WHERE seller_id = ANY(:ids) OR buyer_id = ANY(:ids)"),
            {"ids": list(ids)},
        )
        await session.execute(
            text("DELETE FROM public.listings WHERE seller_id = ANY(:ids)"),
            {"ids": list(ids)},
        )
        await session.execute(
            text("DELETE FROM public.users WHERE id = ANY(:ids)"),
            {"ids": list(ids)},
        )
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
    """Insert a listing row directly (bypasses the API) with a known plaintext
    passkey so tests can exercise verify-passkey deterministically."""
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
                {
                    "id": listing_id,
                    "seller_id": seller_id,
                    "title": title,
                    "asking_price": asking_price,
                    "passkey_hash": passkey_hash,
                },
            )
            await session.commit()

    asyncio.run(_insert())
    return listing_id, passkey


def _set_listing_state(listing_id, *, is_available=None, passkey_invalidated=None, sold_at=None):
    async def _update():
        async with AsyncSessionLocal() as session:
            sets = []
            params = {"id": listing_id}
            if is_available is not None:
                sets.append("is_available = :is_available")
                params["is_available"] = is_available
            if passkey_invalidated is not None:
                sets.append("passkey_invalidated = :passkey_invalidated")
                params["passkey_invalidated"] = passkey_invalidated
            if sold_at is not None:
                sets.append("sold_at = :sold_at")
                params["sold_at"] = sold_at
            if not sets:
                return
            await session.execute(
                text(f"UPDATE public.listings SET {', '.join(sets)} WHERE id = :id"),
                params,
            )
            await session.commit()

    asyncio.run(_update())


def _seed_transaction(listing_id, buyer_id, status="initiated", payment_link_id=None,
                       amount_rupees=350, created_at=None, payment_link_url="https://rzp.io/l/test123"):
    txn_id = str(uuid.uuid4())
    payment_link_id = payment_link_id or f"plink_{uuid.uuid4().hex[:12]}"
    created_at = created_at or datetime.utcnow()

    async def _insert():
        async with AsyncSessionLocal() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO public.transactions
                        (id, listing_id, buyer_id, seller_id, amount_rupees,
                         platform_fee_rupees, seller_payout_rupees,
                         razorpay_payment_link_id, razorpay_payment_link_url,
                         status, created_at)
                    VALUES
                        (:id, :listing_id, :buyer_id, :seller_id, :amount_rupees,
                         0, :amount_rupees, :payment_link_id, :payment_link_url,
                         :status, :created_at)
                    """
                ),
                {
                    "id": txn_id,
                    "listing_id": listing_id,
                    "buyer_id": buyer_id,
                    "seller_id": SELLER_ID,
                    "amount_rupees": amount_rupees,
                    "payment_link_id": payment_link_id,
                    "payment_link_url": payment_link_url,
                    "status": status,
                    "created_at": created_at,
                },
            )
            await session.commit()

    asyncio.run(_insert())
    return txn_id, payment_link_id


def _get_transaction_row(txn_id):
    async def _fetch():
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT * FROM public.transactions WHERE id = :id"), {"id": txn_id}
            )
            row = result.mappings().first()
            return dict(row) if row else None

    return asyncio.run(_fetch())


def _get_listing_row(listing_id):
    async def _fetch():
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT * FROM public.listings WHERE id = :id"), {"id": listing_id}
            )
            row = result.mappings().first()
            return dict(row) if row else None

    return asyncio.run(_fetch())


# A fake razorpay_client substitute — created lazily per test via monkeypatch
class FakePaymentLink:
    def __init__(self, link_id="plink_fake123", short_url="https://rzp.io/l/fake123"):
        self.link_id = link_id
        self.short_url = short_url
        self.create_calls = []

    def create(self, payload):
        self.create_calls.append(payload)
        return {"id": self.link_id, "short_url": self.short_url}


class FakeRefund:
    def __init__(self):
        self.calls = []

    def refund(self, payment_id, payload):
        self.calls.append((payment_id, payload))
        return {"id": "rfnd_fake", "status": "processed"}


def _build_webhook_payload(event, payment_link_id="plink_fake123", payment_id="pay_fake123"):
    return {
        "event": event,
        "payload": {
            "payment_link": {"entity": {"id": payment_link_id}},
            "payment": {"entity": {"id": payment_id}},
        },
    }


# ===========================================================================
# Auth guards — every protected payments/transactions route requires a token
# ===========================================================================

def test_verify_passkey_without_auth_returns_401(client):
    resp = client.post("/v1/payments/verify-passkey", json={"listing_id": str(uuid.uuid4()), "passkey": "12345678"})
    assert resp.status_code == 401


def test_onboard_without_auth_returns_401(client):
    resp = client.post("/v1/payments/onboard")
    assert resp.status_code == 401


def test_onboard_complete_without_auth_returns_401(client):
    resp = client.post("/v1/payments/onboard/complete", json={"razorpay_account_id": "acc_x"})
    assert resp.status_code == 401


def test_transaction_status_without_auth_returns_401(client):
    resp = client.get(f"/v1/transactions/{uuid.uuid4()}/status")
    assert resp.status_code == 401


def test_webhook_does_not_require_auth_token(client):
    """Spec: POST /payments/webhook is 'no auth — Razorpay, verify signature'.
    A request with no Authorization header must not be rejected with 401 —
    it should reach signature verification (and fail there, returning 400)."""
    resp = client.post(
        "/v1/payments/webhook",
        content=b'{"event": "payment_link.paid"}',
        headers={"X-Razorpay-Signature": "bogus"},
    )
    assert resp.status_code != 401


# ===========================================================================
# POST /payments/verify-passkey — check ordering and happy path
# ===========================================================================

def test_verify_passkey_with_correct_value_returns_payment_link_url(client, auth_as_buyer, monkeypatch):
    listing_id, passkey = _create_listing_direct()

    fake_link = FakePaymentLink(link_id="plink_correct", short_url="https://rzp.io/l/correct")
    monkeypatch.setattr(payment_service.razorpay_client, "payment_link", fake_link)

    resp = client.post("/v1/payments/verify-passkey", json={"listing_id": listing_id, "passkey": passkey})
    assert resp.status_code == 200
    body = resp.json()
    assert "payment_link_url" in body
    assert body["payment_link_url"] == "https://rzp.io/l/correct"


def test_verify_passkey_correct_value_creates_initiated_transaction_in_db(client, auth_as_buyer, monkeypatch):
    listing_id, passkey = _create_listing_direct()
    fake_link = FakePaymentLink(link_id="plink_db_check", short_url="https://rzp.io/l/dbcheck")
    monkeypatch.setattr(payment_service.razorpay_client, "payment_link", fake_link)

    resp = client.post("/v1/payments/verify-passkey", json={"listing_id": listing_id, "passkey": passkey})
    assert resp.status_code == 200

    async def _fetch():
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT status, amount_rupees, razorpay_payment_link_id FROM public.transactions WHERE listing_id = :lid"),
                {"lid": listing_id},
            )
            return result.mappings().first()

    row = asyncio.run(_fetch())
    assert row is not None
    assert row["status"] == "initiated"
    assert row["razorpay_payment_link_id"] == "plink_db_check"


def test_verify_passkey_already_sold_listing_returns_400(client, auth_as_buyer):
    """Spec check 1: passkey_invalidated=TRUE -> 400 'This listing has already been sold.'"""
    listing_id, passkey = _create_listing_direct()
    _set_listing_state(listing_id, is_available=False, passkey_invalidated=True, sold_at=datetime.utcnow())

    resp = client.post("/v1/payments/verify-passkey", json={"listing_id": listing_id, "passkey": passkey})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "This listing has already been sold."


def test_verify_passkey_paused_listing_returns_400_temporarily_unavailable(client, auth_as_buyer):
    """Spec check 2: is_available=FALSE (but not sold) -> 400 'This listing is temporarily unavailable.'"""
    listing_id, passkey = _create_listing_direct()
    _set_listing_state(listing_id, is_available=False)

    resp = client.post("/v1/payments/verify-passkey", json={"listing_id": listing_id, "passkey": passkey})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "This listing is temporarily unavailable."


def test_verify_passkey_self_purchase_returns_403(client, auth_as_seller):
    """Spec check 3: seller submitting a passkey against their own listing -> 403."""
    listing_id, passkey = _create_listing_direct(seller_id=SELLER_ID)

    resp = client.post("/v1/payments/verify-passkey", json={"listing_id": listing_id, "passkey": passkey})
    assert resp.status_code == 403
    assert resp.json()["detail"] == "You cannot purchase your own listing."


def test_verify_passkey_blocked_buyer_returns_403_without_running_hash_check(client, auth_as_buyer, fake_redis, monkeypatch):
    """Spec check 4: attempts >= 3 -> 403 immediately; hash comparison must not run."""
    listing_id, passkey = _create_listing_direct()
    attempts_key = f"passkey_attempts:{listing_id}:{BUYER_ID}"
    asyncio.run(fake_redis.set(attempts_key, 3))

    with mock.patch("app.routers.payments.verify_passkey") as mock_verify:
        resp = client.post("/v1/payments/verify-passkey", json={"listing_id": listing_id, "passkey": passkey})

    assert resp.status_code == 403
    assert resp.json()["detail"] == "You have been blocked from purchasing this listing."
    mock_verify.assert_not_called()


def test_verify_passkey_wrong_value_increments_redis_attempt_counter(client, auth_as_buyer, fake_redis):
    """Spec check 5: wrong passkey increments passkey_attempts:{listing_id}:{buyer_id}."""
    listing_id, correct_passkey = _create_listing_direct()
    attempts_key = f"passkey_attempts:{listing_id}:{BUYER_ID}"

    assert asyncio.run(fake_redis.get(attempts_key)) is None

    resp = client.post("/v1/payments/verify-passkey", json={"listing_id": listing_id, "passkey": "00000000"})
    assert resp.status_code == 400
    assert "Incorrect passkey" in resp.json()["detail"]
    assert int(asyncio.run(fake_redis.get(attempts_key))) == 1


def test_verify_passkey_wrong_value_response_reports_remaining_attempts(client, auth_as_buyer):
    listing_id, _ = _create_listing_direct()

    resp = client.post("/v1/payments/verify-passkey", json={"listing_id": listing_id, "passkey": "00000000"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Incorrect passkey. 2 attempts remaining."


def test_verify_passkey_third_wrong_attempt_returns_429_blocked_status(client, auth_as_buyer, fake_redis):
    """DoD: 'POST /payments/verify-passkey returns 403 on the third wrong attempt
    (count=3); hash check does not run when count>=3.'

    Note: the spec text in the prompt says '429' colloquially but PAYMENT.md and
    the DoD both define the third-failure response as HTTP 403 with the
    'blocked' message — we assert against the documented contract (403)."""
    listing_id, _ = _create_listing_direct()

    first = client.post("/v1/payments/verify-passkey", json={"listing_id": listing_id, "passkey": "00000000"})
    second = client.post("/v1/payments/verify-passkey", json={"listing_id": listing_id, "passkey": "00000001"})
    third = client.post("/v1/payments/verify-passkey", json={"listing_id": listing_id, "passkey": "00000002"})

    assert first.status_code == 400
    assert second.status_code == 400
    assert third.status_code == 403
    assert third.json()["detail"] == "You have been blocked from purchasing this listing."


def test_verify_passkey_blocked_after_three_failures_rejects_even_correct_passkey(client, auth_as_buyer):
    """Once attempts >= 3, even the correct passkey must be rejected with 403 —
    Redis block check runs before hash comparison (Spec 08 check ordering)."""
    listing_id, correct_passkey = _create_listing_direct()

    client.post("/v1/payments/verify-passkey", json={"listing_id": listing_id, "passkey": "00000000"})
    client.post("/v1/payments/verify-passkey", json={"listing_id": listing_id, "passkey": "00000001"})
    client.post("/v1/payments/verify-passkey", json={"listing_id": listing_id, "passkey": "00000002"})

    resp = client.post("/v1/payments/verify-passkey", json={"listing_id": listing_id, "passkey": correct_passkey})
    assert resp.status_code == 403
    assert resp.json()["detail"] == "You have been blocked from purchasing this listing."


def test_verify_passkey_uses_hmac_compare_digest_not_equality(client, auth_as_buyer):
    """Rule 11 — hmac.compare_digest must be used for passkey comparison, never `==`.

    Spies on the real `hmac.compare_digest` (wraps it, so behavior is unchanged —
    never replaced with a function that always returns True) to confirm the
    passkey check routes through it. Uses a wrong passkey so the request never
    reaches `initiate_payment` / the Razorpay API."""
    listing_id, _ = _create_listing_direct()

    with mock.patch("app.core.security.hmac.compare_digest", wraps=hmac.compare_digest) as mock_cd:
        resp = client.post("/v1/payments/verify-passkey", json={"listing_id": listing_id, "passkey": "00000000"})

    assert resp.status_code == 400
    mock_cd.assert_called_once()


def test_verify_passkey_redis_attempt_counter_has_seven_day_ttl(client, auth_as_buyer, fake_redis):
    """Spec: passkey_attempts key TTL is 7 days (604800 seconds)."""
    listing_id, _ = _create_listing_direct()
    attempts_key = f"passkey_attempts:{listing_id}:{BUYER_ID}"

    real_pipeline = fake_redis.pipeline
    captured = {}

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

    client.post("/v1/payments/verify-passkey", json={"listing_id": listing_id, "passkey": "00000000"})

    assert captured.get("key") == attempts_key
    assert captured.get("ttl") == 604800


# ===========================================================================
# Idempotency — submitting the correct passkey twice returns the same link
# ===========================================================================

def test_verify_passkey_correct_value_twice_returns_same_payment_link_idempotently(client, auth_as_buyer, monkeypatch):
    listing_id, passkey = _create_listing_direct()

    fake_link = FakePaymentLink(link_id="plink_idem", short_url="https://rzp.io/l/idem")
    monkeypatch.setattr(payment_service.razorpay_client, "payment_link", fake_link)

    first = client.post("/v1/payments/verify-passkey", json={"listing_id": listing_id, "passkey": passkey})
    second = client.post("/v1/payments/verify-passkey", json={"listing_id": listing_id, "passkey": passkey})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["payment_link_url"] == second.json()["payment_link_url"]
    # Razorpay payment_link.create must be called exactly once — second call is idempotent
    assert len(fake_link.create_calls) == 1


# ===========================================================================
# Payment boundary conditions — paise conversion, expiry
# ===========================================================================

def test_verify_passkey_payment_link_amount_is_rupees_times_100_paise(client, auth_as_buyer, monkeypatch):
    """Spec: paise conversion (`amount_rupees * 100`) happens only at the
    Razorpay payment_link.create() boundary."""
    listing_id, passkey = _create_listing_direct(asking_price=350)

    fake_link = FakePaymentLink(link_id="plink_paise", short_url="https://rzp.io/l/paise")
    monkeypatch.setattr(payment_service.razorpay_client, "payment_link", fake_link)

    resp = client.post("/v1/payments/verify-passkey", json={"listing_id": listing_id, "passkey": passkey})
    assert resp.status_code == 200

    assert len(fake_link.create_calls) == 1
    payload = fake_link.create_calls[0]
    assert payload["amount"] == 350 * 100
    assert payload["currency"] == "INR"


def test_verify_passkey_payment_link_has_fifteen_minute_expiry(client, auth_as_buyer, monkeypatch):
    listing_id, passkey = _create_listing_direct()

    fake_link = FakePaymentLink(link_id="plink_expiry", short_url="https://rzp.io/l/expiry")
    monkeypatch.setattr(payment_service.razorpay_client, "payment_link", fake_link)

    before = datetime.utcnow()
    resp = client.post("/v1/payments/verify-passkey", json={"listing_id": listing_id, "passkey": passkey})
    after = datetime.utcnow()
    assert resp.status_code == 200

    payload = fake_link.create_calls[0]
    expire_by = payload["expire_by"]
    assert isinstance(expire_by, int)

    expected_min = int((before + timedelta(minutes=15)).timestamp())
    expected_max = int((after + timedelta(minutes=15)).timestamp()) + 1
    assert expected_min <= expire_by <= expected_max


def test_verify_passkey_response_never_contains_paise_amount(client, auth_as_buyer, monkeypatch):
    listing_id, passkey = _create_listing_direct(asking_price=500)
    fake_link = FakePaymentLink(link_id="plink_norup", short_url="https://rzp.io/l/norup")
    monkeypatch.setattr(payment_service.razorpay_client, "payment_link", fake_link)

    resp = client.post("/v1/payments/verify-passkey", json={"listing_id": listing_id, "passkey": passkey})
    assert resp.status_code == 200
    body = resp.json()
    # The response is just {"payment_link_url": ...} — no amount field, never paise
    assert "amount" not in body
    assert "amount_paise" not in body


def test_initiated_transaction_amount_rupees_stored_as_whole_integer(client, auth_as_buyer, monkeypatch):
    listing_id, passkey = _create_listing_direct(asking_price=275)
    fake_link = FakePaymentLink(link_id="plink_whole", short_url="https://rzp.io/l/whole")
    monkeypatch.setattr(payment_service.razorpay_client, "payment_link", fake_link)

    client.post("/v1/payments/verify-passkey", json={"listing_id": listing_id, "passkey": passkey})

    async def _fetch():
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT amount_rupees, seller_payout_rupees, platform_fee_rupees FROM public.transactions WHERE listing_id = :lid"),
                {"lid": listing_id},
            )
            return result.mappings().first()

    row = asyncio.run(_fetch())
    assert row["amount_rupees"] == 275
    assert isinstance(row["amount_rupees"], int)
    # Must never be the paise-converted value
    assert row["amount_rupees"] != 275 * 100
    # Platform fee is 0% in v1
    assert row["platform_fee_rupees"] == 0
    assert row["seller_payout_rupees"] == 275


# ===========================================================================
# POST /payments/onboard — seller onboarding (create)
# ===========================================================================

def test_onboard_seller_without_existing_account_returns_onboarding_url(client, auth_as_buyer, monkeypatch):
    """Use auth_as_buyer (no razorpay_account_id) to exercise the create branch."""
    fake_account = mock.Mock()
    fake_account.create = mock.Mock(return_value={"id": "acc_new123"})

    fake_stakeholder = mock.Mock()
    fake_stakeholder.create = mock.Mock(return_value={"url": "https://rzp.io/kyc/acc_new123"})

    monkeypatch.setattr(payment_service.razorpay_client, "account", fake_account)
    monkeypatch.setattr(payment_service.razorpay_client, "stakeholder", fake_stakeholder)

    resp = client.post("/v1/payments/onboard")
    assert resp.status_code == 200
    body = resp.json()
    assert body["onboarding_url"] == "https://rzp.io/kyc/acc_new123"
    assert body["razorpay_account_id"] == "acc_new123"


def test_onboard_seller_does_not_persist_razorpay_account_id_immediately(client, auth_as_buyer, monkeypatch):
    """Spec: razorpay_account_id is NOT saved at account-creation time —
    only the account.activated / onboard-complete flow saves it."""
    fake_account = mock.Mock()
    fake_account.create = mock.Mock(return_value={"id": "acc_not_saved"})
    fake_stakeholder = mock.Mock()
    fake_stakeholder.create = mock.Mock(return_value={"url": "https://rzp.io/kyc/acc_not_saved"})
    monkeypatch.setattr(payment_service.razorpay_client, "account", fake_account)
    monkeypatch.setattr(payment_service.razorpay_client, "stakeholder", fake_stakeholder)

    client.post("/v1/payments/onboard")

    async def _fetch():
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT razorpay_account_id FROM public.users WHERE id = :id"), {"id": BUYER_ID}
            )
            return result.scalar_one_or_none()

    assert asyncio.run(_fetch()) is None


def test_onboard_seller_with_existing_account_returns_already_onboarded(client, auth_as_seller):
    """SELLER_ID is seeded with a razorpay_account_id — onboarding is a no-op."""
    resp = client.post("/v1/payments/onboard")
    assert resp.status_code == 200
    assert resp.json()["message"] == "Already onboarded"


# ===========================================================================
# POST /payments/onboard/complete
# ===========================================================================

def test_onboard_complete_with_non_activated_account_returns_400(client, auth_as_buyer, monkeypatch):
    fake_account = mock.Mock()
    fake_account.fetch = mock.Mock(return_value={"profile": {"status": "created"}})
    monkeypatch.setattr(payment_service.razorpay_client, "account", fake_account)

    resp = client.post("/v1/payments/onboard/complete", json={"razorpay_account_id": "acc_pending"})
    assert resp.status_code == 400
    assert "KYC" in resp.json()["detail"]


def test_onboard_complete_with_activated_account_persists_razorpay_account_id(client, auth_as_buyer, monkeypatch):
    fake_account = mock.Mock()
    fake_account.fetch = mock.Mock(return_value={"profile": {"status": "activated"}})
    monkeypatch.setattr(payment_service.razorpay_client, "account", fake_account)

    resp = client.post("/v1/payments/onboard/complete", json={"razorpay_account_id": "acc_activated_999"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "complete"

    async def _fetch():
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT razorpay_account_id FROM public.users WHERE id = :id"), {"id": BUYER_ID}
            )
            return result.scalar_one_or_none()

    assert asyncio.run(_fetch()) == "acc_activated_999"


def test_onboard_complete_when_already_onboarded_returns_already_complete(client, auth_as_seller, monkeypatch):
    fake_account = mock.Mock()
    fake_account.fetch = mock.Mock(return_value={"profile": {"status": "activated"}})
    monkeypatch.setattr(payment_service.razorpay_client, "account", fake_account)

    resp = client.post("/v1/payments/onboard/complete", json={"razorpay_account_id": "acc_irrelevant"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "already_complete"
    # Must not call Razorpay to verify a status it doesn't need
    fake_account.fetch.assert_not_called()


# ===========================================================================
# Seller onboarding gate — POST /listings blocked without razorpay_account_id
# ===========================================================================

def test_create_listing_without_razorpay_account_returns_403(client, auth_as_buyer):
    """Spec: seller without razorpay_account_id receives 403 'Complete payment
    setup to start selling.' on POST /listings. BUYER_ID is seeded with
    razorpay_account_id = NULL."""
    resp = client.post("/v1/listings", json=VALID_LISTING_PAYLOAD)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Complete payment setup to start selling."


def test_create_listing_with_razorpay_account_succeeds(client, auth_as_seller):
    """SELLER_ID is seeded with a razorpay_account_id — listing creation is allowed."""
    payload = dict(VALID_LISTING_PAYLOAD)
    payload["title"] = f"Onboarded seller listing {uuid.uuid4()}"
    resp = client.post("/v1/listings", json=payload)
    assert resp.status_code == 201


# ===========================================================================
# POST /payments/webhook — security: HMAC signature verification
# ===========================================================================

def test_webhook_with_invalid_signature_returns_400(client, monkeypatch):
    """Rule 2 — webhook HMAC signature must be verified before any processing.
    Invalid signature -> 400, no DB lookups performed."""
    body = json.dumps(_build_webhook_payload("payment_link.paid")).encode()

    def _raise(*a, **kw):
        raise Exception("Invalid signature")

    monkeypatch.setattr(
        payment_service.razorpay_client.utility, "verify_webhook_signature", _raise
    )

    resp = client.post("/v1/payments/webhook", content=body, headers={"X-Razorpay-Signature": "bad-sig"})
    assert resp.status_code == 400


def test_webhook_signature_verified_before_payload_is_parsed(client, monkeypatch):
    """Even malformed JSON should fail at signature verification, not JSON parsing —
    confirms Step 1 runs first."""
    raw_body = b"not-valid-json{{{"

    def _raise(*a, **kw):
        raise Exception("bad sig")

    monkeypatch.setattr(payment_service.razorpay_client.utility, "verify_webhook_signature", _raise)

    resp = client.post("/v1/payments/webhook", content=raw_body, headers={"X-Razorpay-Signature": "x"})
    assert resp.status_code == 400


# ===========================================================================
# POST /payments/webhook — unrecognised events always return 200
# ===========================================================================

def test_webhook_with_unrecognised_event_type_returns_200(client, monkeypatch):
    """Rule 3 — unrecognised webhook events must return 200, never 4xx
    (prevents Razorpay retry storms)."""
    body = json.dumps(_build_webhook_payload("payment.failed")).encode()
    monkeypatch.setattr(
        payment_service.razorpay_client.utility, "verify_webhook_signature", lambda *a, **kw: None
    )

    resp = client.post("/v1/payments/webhook", content=body, headers={"X-Razorpay-Signature": "ok"})
    assert resp.status_code == 200


def test_webhook_with_unrecognised_payment_link_id_returns_200(client, monkeypatch):
    """Spec DoD: an unknown payment_link_id must return 200 — not 404 — to
    avoid Razorpay retries on a transaction the system never created."""
    body = json.dumps(_build_webhook_payload("payment_link.paid", payment_link_id="plink_does_not_exist")).encode()
    monkeypatch.setattr(
        payment_service.razorpay_client.utility, "verify_webhook_signature", lambda *a, **kw: None
    )

    resp = client.post("/v1/payments/webhook", content=body, headers={"X-Razorpay-Signature": "ok"})
    assert resp.status_code == 200


# ===========================================================================
# POST /payments/webhook — happy path: payment_link.paid -> released
# ===========================================================================

def test_webhook_payment_link_paid_releases_transaction_and_closes_listing(client, monkeypatch):
    """DoD: successful webhook sets transaction.status='released',
    listing.is_available=FALSE, listing.passkey_invalidated=TRUE,
    listing.sold_at not null — all in the same commit."""
    listing_id, _ = _create_listing_direct()
    txn_id, link_id = _seed_transaction(listing_id, BUYER_ID, status="initiated")

    monkeypatch.setattr(
        payment_service.razorpay_client.utility, "verify_webhook_signature", lambda *a, **kw: None
    )
    fake_email = mock.AsyncMock(return_value="seller@example.com")
    monkeypatch.setattr("app.routers.payments.fetch_user_email", fake_email)
    fake_send = mock.AsyncMock()
    monkeypatch.setattr("app.routers.payments.notification_service.send_sale_complete", fake_send)

    body = json.dumps(_build_webhook_payload("payment_link.paid", payment_link_id=link_id, payment_id="pay_release_1")).encode()
    resp = client.post("/v1/payments/webhook", content=body, headers={"X-Razorpay-Signature": "ok"})
    assert resp.status_code == 200

    txn_row = _get_transaction_row(txn_id)
    listing_row = _get_listing_row(listing_id)

    assert txn_row["status"] == "released"
    assert txn_row["released_at"] is not None
    assert txn_row["razorpay_payment_id"] == "pay_release_1"

    assert listing_row["is_available"] is False
    assert listing_row["passkey_invalidated"] is True
    assert listing_row["sold_at"] is not None


def test_webhook_payment_link_paid_sends_seller_email_resolved_via_service_role(client, monkeypatch):
    """DoD: seller email resolved from auth.users via fetch_user_email — never
    accessed as transaction.seller_email (that field doesn't exist)."""
    listing_id, _ = _create_listing_direct()
    txn_id, link_id = _seed_transaction(listing_id, BUYER_ID, status="initiated")

    monkeypatch.setattr(
        payment_service.razorpay_client.utility, "verify_webhook_signature", lambda *a, **kw: None
    )
    fake_email = mock.AsyncMock(return_value="seller-resolved@example.com")
    monkeypatch.setattr("app.routers.payments.fetch_user_email", fake_email)
    fake_send = mock.AsyncMock()
    monkeypatch.setattr("app.routers.payments.notification_service.send_sale_complete", fake_send)

    body = json.dumps(_build_webhook_payload("payment_link.paid", payment_link_id=link_id, payment_id="pay_email_1")).encode()
    client.post("/v1/payments/webhook", content=body, headers={"X-Razorpay-Signature": "ok"})

    fake_email.assert_awaited()
    fake_send.assert_awaited()
    call_args = fake_send.await_args
    assert "seller-resolved@example.com" in call_args.args


# ===========================================================================
# POST /payments/webhook — idempotency on already-released transactions
# ===========================================================================

def test_webhook_duplicate_for_already_released_transaction_returns_200_no_change(client, monkeypatch):
    """Spec Step 5 — idempotency: duplicate webhook on a released transaction
    returns 200 and makes no further DB changes."""
    listing_id, _ = _create_listing_direct()
    txn_id, link_id = _seed_transaction(listing_id, BUYER_ID, status="released")
    _set_listing_state(listing_id, is_available=False, passkey_invalidated=True, sold_at=datetime.utcnow())

    monkeypatch.setattr(
        payment_service.razorpay_client.utility, "verify_webhook_signature", lambda *a, **kw: None
    )
    fake_refund = mock.Mock()
    monkeypatch.setattr(payment_service.razorpay_client, "payment", mock.Mock(refund=fake_refund))

    before = _get_transaction_row(txn_id)
    body = json.dumps(_build_webhook_payload("payment_link.paid", payment_link_id=link_id, payment_id="pay_dup_1")).encode()
    resp = client.post("/v1/payments/webhook", content=body, headers={"X-Razorpay-Signature": "ok"})
    after = _get_transaction_row(txn_id)

    assert resp.status_code == 200
    assert after["status"] == "released"
    assert before["status"] == after["status"]
    assert before["razorpay_payment_id"] == after["razorpay_payment_id"]
    fake_refund.assert_not_called()


# ===========================================================================
# POST /payments/webhook — late webhook always refunds, never reopens
# ===========================================================================

def test_webhook_late_arrival_on_cancelled_transaction_triggers_refund_and_stays_cancelled(client, monkeypatch):
    """Rule 12 / Spec Step 6 — late webhook on a cancelled transaction always
    refunds and never reopens (status must remain 'cancelled')."""
    listing_id, _ = _create_listing_direct()
    txn_id, link_id = _seed_transaction(listing_id, BUYER_ID, status="cancelled")

    monkeypatch.setattr(
        payment_service.razorpay_client.utility, "verify_webhook_signature", lambda *a, **kw: None
    )
    fake_refund = mock.Mock(return_value={"id": "rfnd_late", "status": "processed"})
    monkeypatch.setattr(payment_service.razorpay_client, "payment", mock.Mock(refund=fake_refund))

    body = json.dumps(_build_webhook_payload("payment_link.paid", payment_link_id=link_id, payment_id="pay_late_1")).encode()
    resp = client.post("/v1/payments/webhook", content=body, headers={"X-Razorpay-Signature": "ok"})
    assert resp.status_code == 200

    fake_refund.assert_called_once()
    refund_payment_id, refund_payload = fake_refund.call_args[0]
    assert refund_payment_id == "pay_late_1"
    # Refund amount uses paise — the only other lawful place for `* 100`
    assert refund_payload["amount"] == 350 * 100

    txn_row = _get_transaction_row(txn_id)
    assert txn_row["status"] == "cancelled"
    assert txn_row["refunded_at"] is not None


def test_webhook_late_arrival_never_sets_status_to_released(client, monkeypatch):
    """A cancelled transaction's status must never become 'released' due to a
    late webhook — only `initiated -> released | cancelled` transitions exist."""
    listing_id, _ = _create_listing_direct()
    txn_id, link_id = _seed_transaction(listing_id, BUYER_ID, status="cancelled")

    monkeypatch.setattr(
        payment_service.razorpay_client.utility, "verify_webhook_signature", lambda *a, **kw: None
    )
    monkeypatch.setattr(
        payment_service.razorpay_client, "payment",
        mock.Mock(refund=mock.Mock(return_value={"id": "rfnd_x"}))
    )

    body = json.dumps(_build_webhook_payload("payment_link.paid", payment_link_id=link_id, payment_id="pay_never_release")).encode()
    client.post("/v1/payments/webhook", content=body, headers={"X-Razorpay-Signature": "ok"})

    txn_row = _get_transaction_row(txn_id)
    assert txn_row["status"] in ("initiated", "released", "cancelled")
    assert txn_row["status"] == "cancelled"


# ===========================================================================
# POST /payments/webhook — concurrent payment race: loser gets refunded
# ===========================================================================

def test_webhook_concurrent_payment_refunds_the_losing_transaction(client, monkeypatch):
    """Spec Step 8 — when a second buyer's webhook arrives after the listing
    is already closed (is_available=FALSE), it must be refunded and the
    transaction marked 'cancelled'; the listing remains unavailable (one winner)."""
    listing_id, _ = _create_listing_direct()
    winner_txn, winner_link = _seed_transaction(listing_id, BUYER_ID, status="initiated", payment_link_id="plink_winner")
    loser_txn, loser_link = _seed_transaction(listing_id, OTHER_BUYER_ID, status="initiated", payment_link_id="plink_loser")

    monkeypatch.setattr(
        payment_service.razorpay_client.utility, "verify_webhook_signature", lambda *a, **kw: None
    )
    fake_email = mock.AsyncMock(return_value="seller@example.com")
    monkeypatch.setattr("app.routers.payments.fetch_user_email", fake_email)
    fake_send = mock.AsyncMock()
    monkeypatch.setattr("app.routers.payments.notification_service.send_sale_complete", fake_send)
    fake_refund = mock.Mock(return_value={"id": "rfnd_loser", "status": "processed"})
    monkeypatch.setattr(payment_service.razorpay_client, "payment", mock.Mock(refund=fake_refund))

    # Winner's webhook arrives first — closes the listing
    winner_body = json.dumps(_build_webhook_payload("payment_link.paid", payment_link_id=winner_link, payment_id="pay_winner")).encode()
    winner_resp = client.post("/v1/payments/webhook", content=winner_body, headers={"X-Razorpay-Signature": "ok"})
    assert winner_resp.status_code == 200
    assert _get_transaction_row(winner_txn)["status"] == "released"
    assert _get_listing_row(listing_id)["is_available"] is False

    # Loser's webhook arrives second — must be refunded, marked cancelled
    loser_body = json.dumps(_build_webhook_payload("payment_link.paid", payment_link_id=loser_link, payment_id="pay_loser")).encode()
    loser_resp = client.post("/v1/payments/webhook", content=loser_body, headers={"X-Razorpay-Signature": "ok"})
    assert loser_resp.status_code == 200

    loser_row = _get_transaction_row(loser_txn)
    assert loser_row["status"] == "cancelled"
    assert loser_row["refunded_at"] is not None
    fake_refund.assert_called_once()
    refund_payment_id, _ = fake_refund.call_args[0]
    assert refund_payment_id == "pay_loser"

    # Listing remains is_available=FALSE — only one winner
    listing_row = _get_listing_row(listing_id)
    assert listing_row["is_available"] is False


# ===========================================================================
# Transaction status integrity — only initiated | released | cancelled
# ===========================================================================

def test_webhook_released_transaction_status_is_one_of_documented_values(client, monkeypatch):
    listing_id, _ = _create_listing_direct()
    txn_id, link_id = _seed_transaction(listing_id, BUYER_ID, status="initiated")

    monkeypatch.setattr(
        payment_service.razorpay_client.utility, "verify_webhook_signature", lambda *a, **kw: None
    )
    fake_email = mock.AsyncMock(return_value="seller@example.com")
    monkeypatch.setattr("app.routers.payments.fetch_user_email", fake_email)
    monkeypatch.setattr("app.routers.payments.notification_service.send_sale_complete", mock.AsyncMock())

    body = json.dumps(_build_webhook_payload("payment_link.paid", payment_link_id=link_id, payment_id="pay_status_check")).encode()
    client.post("/v1/payments/webhook", content=body, headers={"X-Razorpay-Signature": "ok"})

    status = _get_transaction_row(txn_id)["status"]
    assert status in ("initiated", "released", "cancelled")
    assert status not in ("disputed", "confirmed", "paid", "pending")


# ===========================================================================
# GET /transactions/{id}/status — buyer-scoped polling
# ===========================================================================

def test_get_transaction_status_returns_status_and_amount_for_owning_buyer(client, auth_as_buyer):
    listing_id, _ = _create_listing_direct(asking_price=420)
    txn_id, _ = _seed_transaction(listing_id, BUYER_ID, status="initiated", amount_rupees=420)

    resp = client.get(f"/v1/transactions/{txn_id}/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "initiated"
    assert body["amount_rupees"] == 420
    assert isinstance(body["amount_rupees"], int)


def test_get_transaction_status_for_non_owning_buyer_returns_404(client, auth_as_other_buyer):
    """Spec: GET /transactions/{id}/status is buyer-scoped — a different buyer
    querying someone else's transaction must receive 404, not 403 (avoids
    confirming the transaction's existence to non-owners)."""
    listing_id, _ = _create_listing_direct()
    txn_id, _ = _seed_transaction(listing_id, BUYER_ID, status="initiated")

    resp = client.get(f"/v1/transactions/{txn_id}/status")
    assert resp.status_code == 404


def test_get_transaction_status_for_nonexistent_transaction_returns_404(client, auth_as_buyer):
    resp = client.get(f"/v1/transactions/{uuid.uuid4()}/status")
    assert resp.status_code == 404


def test_get_transaction_status_response_only_contains_status_and_amount(client, auth_as_buyer):
    """Rule 1 — never expose seller contact info or any PII; the polling
    endpoint must only return status + amount_rupees."""
    listing_id, _ = _create_listing_direct(asking_price=199)
    txn_id, _ = _seed_transaction(listing_id, BUYER_ID, status="initiated", amount_rupees=199)

    resp = client.get(f"/v1/transactions/{txn_id}/status")
    body = resp.json()
    assert set(body.keys()) == {"status", "amount_rupees"}
    for forbidden in ("seller_id", "seller_email", "buyer_id", "razorpay_payment_link_url",
                      "razorpay_payment_id", "listing_id"):
        assert forbidden not in body


def test_get_transaction_status_value_is_never_outside_documented_set(client, auth_as_buyer):
    listing_id, _ = _create_listing_direct()
    for status in ("initiated", "released", "cancelled"):
        txn_id, _ = _seed_transaction(listing_id, BUYER_ID, status=status, payment_link_id=f"plink_{status}_{uuid.uuid4().hex[:6]}")
        resp = client.get(f"/v1/transactions/{txn_id}/status")
        assert resp.status_code == 200
        assert resp.json()["status"] in ("initiated", "released", "cancelled")


# ===========================================================================
# Buy Now is UI-only — no API call, no DB rows
# ===========================================================================

def test_buy_now_creates_zero_transaction_rows(client, auth_as_buyer):
    """Spec: 'Buyer clicks Buy Now. No API call is made. No DB row is created.'
    We assert the documented contract by confirming no transaction exists for
    a fresh listing the buyer has merely viewed (no verify-passkey call made)."""
    listing_id, _ = _create_listing_direct()
    # Buyer views the listing (the only network activity Buy Now triggers per spec
    # is opening a passkey input — no backend call)
    client.get(f"/v1/listings/{listing_id}")

    async def _count():
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM public.transactions WHERE listing_id = :lid"),
                {"lid": listing_id},
            )
            return result.scalar_one()

    assert asyncio.run(_count()) == 0


# ===========================================================================
# Never expose seller contact info — cross-cutting check on payment responses
# ===========================================================================

def test_verify_passkey_response_never_contains_seller_contact_fields(client, auth_as_buyer, monkeypatch):
    listing_id, passkey = _create_listing_direct()
    fake_link = FakePaymentLink(link_id="plink_pii_check", short_url="https://rzp.io/l/abc123xy")
    monkeypatch.setattr(payment_service.razorpay_client, "payment_link", fake_link)

    resp = client.post("/v1/payments/verify-passkey", json={"listing_id": listing_id, "passkey": passkey})
    raw = resp.text.lower()
    for forbidden in ("email", "phone", "contact", "seller_id"):
        assert forbidden not in raw


def test_webhook_response_body_never_contains_seller_contact_info(client, monkeypatch):
    listing_id, _ = _create_listing_direct()
    txn_id, link_id = _seed_transaction(listing_id, BUYER_ID, status="initiated")

    monkeypatch.setattr(
        payment_service.razorpay_client.utility, "verify_webhook_signature", lambda *a, **kw: None
    )
    monkeypatch.setattr("app.routers.payments.fetch_user_email", mock.AsyncMock(return_value="seller@example.com"))
    monkeypatch.setattr("app.routers.payments.notification_service.send_sale_complete", mock.AsyncMock())

    body = json.dumps(_build_webhook_payload("payment_link.paid", payment_link_id=link_id, payment_id="pay_contact_check")).encode()
    resp = client.post("/v1/payments/webhook", content=body, headers={"X-Razorpay-Signature": "ok"})

    # Webhook returns an empty 200 Response — body must never carry PII
    assert resp.status_code == 200
    assert resp.text == "" or "seller@example.com" not in resp.text

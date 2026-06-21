"""
Tests for Spec 03 — Content Policy / Reporting.

Endpoint under test:
  POST   /v1/reports

These tests are derived from .claude/specs/product/03-content-policy.md and
CLAUDE.md — NOT from reading the implementation. Auth is mocked via FastAPI
dependency overrides on `verify_token`; Redis is replaced with FakeRedis
(identical to the pattern in test_10_chat.py); DB seeding follows the pattern
established by test_14-listings-crud.py and test_10_chat.py.

Run from project root:
    cd backend && ..\\.venv\\Scripts\\python.exe -m pytest tests/test_03-content-policy.py -v
"""

import asyncio
import sys
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

# ---------------------------------------------------------------------------
# Windows asyncio policy — must be set before app imports
# ---------------------------------------------------------------------------
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ---------------------------------------------------------------------------
# Env stubs — set before any app module is imported
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
from app.core.security import verify_token
from app.core.database import get_db, AsyncSessionLocal
from app.core.redis import get_redis
from app.schemas.report import ReportAck, ReportCreate
from app.models.report import Report

# ---------------------------------------------------------------------------
# Stable test identity UUIDs
# ---------------------------------------------------------------------------
REPORTER_ID = str(uuid.uuid4())
SELLER_ID   = str(uuid.uuid4())
OTHER_USER_ID = str(uuid.uuid4())


# ===========================================================================
# FakeRedis — mirrors test_10_chat.py exactly
# ===========================================================================

class FakeRedis:
    """Minimal in-memory async Redis substitute.

    Supports: get, set, incr, expire, delete.
    Enough for the report-rate-limit path.
    """

    def __init__(self):
        self._store: dict = {}
        self._ttl: dict = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value, ex=None):
        self._store[key] = str(value)
        return True

    async def incr(self, key: str) -> int:
        current = int(self._store.get(key, "0")) + 1
        self._store[key] = str(current)
        return current

    async def expire(self, key: str, ttl: int, nx: bool = False) -> bool:
        # nx=True: only set a TTL when the key has none yet (mirrors redis-py).
        if nx and key in self._ttl:
            return False
        self._ttl[key] = ttl
        return True

    async def delete(self, key: str) -> int:
        if key in self._store:
            del self._store[key]
            return 1
        return 0


# ===========================================================================
# Helpers — DB seeding (sync wrappers over async, matching test_10_chat.py)
# ===========================================================================

def _seed_users():
    async def _run():
        async with AsyncSessionLocal() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO public.users (id, full_name)
                    VALUES
                        (:reporter_id, 'Test Reporter'),
                        (:seller_id,   'Test Seller'),
                        (:other_id,    'Other User')
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {
                    "reporter_id": REPORTER_ID,
                    "seller_id":   SELLER_ID,
                    "other_id":    OTHER_USER_ID,
                },
            )
            await session.commit()

    asyncio.run(_run())


def _cleanup():
    async def _run():
        ids = [REPORTER_ID, SELLER_ID, OTHER_USER_ID]
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("DELETE FROM public.reports WHERE reporter_id = ANY(:ids)"),
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
    seller_id: str = SELLER_ID,
    is_available: bool = True,
    deleted_at_set: bool = False,
) -> str:
    """Seed a listing row directly — skips API-layer Razorpay-account guard."""
    listing_id = str(uuid.uuid4())

    async def _run():
        async with AsyncSessionLocal() as session:
            # No f-string SQL (CLAUDE.md rule): the deleted_at literal is chosen by
            # a bound boolean inside a CASE expression, not string interpolation.
            await session.execute(
                text(
                    """
                    INSERT INTO public.listings
                        (id, seller_id, title, description, exam_category, subject,
                         listing_type, condition, asking_price, original_price, city,
                         images, is_available, passkey_hash, deleted_at)
                    VALUES
                        (:id, :seller_id, 'HC Verma Part 1', 'Physics book', 'JEE_MAINS',
                         'Physics', 'BOOK', 'A', 350, 600, 'Delhi',
                         ARRAY['https://res.cloudinary.com/demo/image/upload/v1/x.jpg'],
                         :is_available,
                         'dummyhash0123456789abcdef0123456789abcdef0123456789abcdef01234567',
                         CASE WHEN :set_deleted THEN now() ELSE NULL END)
                    """
                ),
                {
                    "id":           listing_id,
                    "seller_id":    seller_id,
                    "is_available": is_available,
                    "set_deleted":  deleted_at_set,
                },
            )
            await session.commit()

    asyncio.run(_run())
    return listing_id


def _count_reports_for_listing(listing_id: str) -> int:
    """Return the number of rows in public.reports for a given listing_id."""
    async def _run() -> int:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text(
                    "SELECT COUNT(*) FROM public.reports WHERE listing_id = :lid"
                ),
                {"lid": listing_id},
            )
            return result.scalar_one()

    return asyncio.run(_run())


def _get_report_row(listing_id: str, reporter_id: str) -> dict | None:
    """Fetch a single report row by (listing_id, reporter_id)."""
    async def _run():
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text(
                    "SELECT * FROM public.reports "
                    "WHERE listing_id = :lid AND reporter_id = :rid"
                ),
                {"lid": listing_id, "rid": reporter_id},
            )
            row = result.mappings().first()
            return dict(row) if row else None

    return asyncio.run(_run())


def _get_listing_row(listing_id: str) -> dict | None:
    async def _run():
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT * FROM public.listings WHERE id = :lid"),
                {"lid": listing_id},
            )
            row = result.mappings().first()
            return dict(row) if row else None

    return asyncio.run(_run())


# ===========================================================================
# Auth helpers — mirrors test_14-listings-crud.py and test_10_chat.py
# ===========================================================================

def _override_verify_token(user_id: str):
    # No `email` key — identity must come from payload["sub"] only, so an
    # accidental switch to email-as-identity would fail these tests.
    def _inner():
        return {"sub": user_id}
    return _inner


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
def auth_as_reporter():
    app.dependency_overrides[verify_token] = _override_verify_token(REPORTER_ID)
    yield REPORTER_ID
    app.dependency_overrides.pop(verify_token, None)


@pytest.fixture
def auth_as_seller():
    app.dependency_overrides[verify_token] = _override_verify_token(SELLER_ID)
    yield SELLER_ID
    app.dependency_overrides.pop(verify_token, None)


# ===========================================================================
# TestAuthGuard — unauthenticated requests must be rejected
# ===========================================================================

class TestAuthGuard:
    def test_post_reports_without_auth_returns_401(self, client):
        """Spec: POST /v1/reports is a protected route — no token → 401."""
        listing_id = _create_listing()
        resp = client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "PIRACY"},
        )
        assert resp.status_code == 401

    def test_post_reports_with_malformed_bearer_token_returns_401(self, client):
        """Spec: an invalid/malformed Authorization header → 401."""
        listing_id = _create_listing()
        resp = client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "SPAM"},
            headers={"Authorization": "Bearer not.a.real.jwt"},
        )
        assert resp.status_code == 401


# ===========================================================================
# TestHappyPath — POST /v1/reports succeeds
# ===========================================================================

class TestHappyPath:
    def test_create_report_returns_201(self, client, auth_as_reporter):
        """Spec DoD: valid {listing_id, reason} → 201."""
        listing_id = _create_listing()
        resp = client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "PIRACY"},
        )
        assert resp.status_code == 201

    def test_create_report_response_body_is_minimal_ack(self, client, auth_as_reporter):
        """Spec: response body is exactly {"received": true} — nothing else."""
        listing_id = _create_listing()
        resp = client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "CONTACT_INFO"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body == {"received": True}

    def test_create_report_response_never_contains_report_count(
        self, client, auth_as_reporter
    ):
        """Spec: ack must never expose report counts, status, or other reporters."""
        listing_id = _create_listing()
        resp = client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "SPAM"},
        )
        assert resp.status_code == 201
        body = resp.json()
        for forbidden in ("count", "status", "reporter", "reporters", "report_id", "id"):
            assert forbidden not in body, (
                f"Response must not contain '{forbidden}'; got: {body}"
            )

    def test_create_report_persists_row_with_status_open(
        self, client, auth_as_reporter
    ):
        """Spec DoD: a row appears in `reports` with status='open' after a valid report."""
        listing_id = _create_listing()
        resp = client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "NOT_STUDY_MATERIAL"},
        )
        assert resp.status_code == 201

        row = _get_report_row(listing_id, REPORTER_ID)
        assert row is not None, "Expected a report row in the DB"
        assert row["status"] == "open"

    def test_create_report_persists_correct_reason(self, client, auth_as_reporter):
        """Spec: the reason stored in the DB matches the submitted reason value."""
        listing_id = _create_listing()
        client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "ABUSIVE"},
        )
        row = _get_report_row(listing_id, REPORTER_ID)
        assert row is not None
        assert row["reason"] == "ABUSIVE"

    def test_create_report_persists_correct_reporter_id(
        self, client, auth_as_reporter
    ):
        """Spec: reporter_id in the DB row must equal user['sub'] from the JWT."""
        listing_id = _create_listing()
        client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "PROHIBITED"},
        )
        row = _get_report_row(listing_id, REPORTER_ID)
        assert row is not None
        assert str(row["reporter_id"]) == REPORTER_ID

    def test_create_report_accepts_optional_note_within_limit(
        self, client, auth_as_reporter
    ):
        """Spec: optional note <= 1000 chars is accepted (201)."""
        listing_id = _create_listing()
        note = "x" * 500  # well within the 1000-char limit
        resp = client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "OTHER", "note": note},
        )
        assert resp.status_code == 201

    def test_create_report_persists_note_in_db(self, client, auth_as_reporter):
        """Spec: the submitted note is stored in the report row."""
        listing_id = _create_listing()
        note = "This listing contains copyrighted material."
        client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "PIRACY", "note": note},
        )
        row = _get_report_row(listing_id, REPORTER_ID)
        assert row is not None
        assert row["note"] == note

    def test_create_report_without_note_is_accepted(self, client, auth_as_reporter):
        """Spec: note is optional — omitting it must not cause a validation error."""
        listing_id = _create_listing()
        resp = client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "SPAM"},
        )
        assert resp.status_code == 201

    def test_reporter_may_report_any_listing_not_just_their_own_purchase(
        self, client, auth_as_reporter
    ):
        """Spec: any signed-in user may report any listing. Ownership check does
        NOT apply to reporting — only to listing mutations."""
        # The listing was created by SELLER_ID; REPORTER_ID is a different user
        listing_id = _create_listing(seller_id=SELLER_ID)
        resp = client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "CONTACT_INFO"},
        )
        assert resp.status_code == 201

    def test_all_valid_reason_values_are_accepted(self, client, auth_as_reporter, fake_redis):
        """Spec: all seven reason constants from the canonical set must be accepted."""
        valid_reasons = [
            "PIRACY",
            "CONTACT_INFO",
            "SPAM",
            "NOT_STUDY_MATERIAL",
            "PROHIBITED",
            "ABUSIVE",
            "OTHER",
        ]
        rate_key = f"report_rate:{REPORTER_ID}"
        for reason in valid_reasons:
            # Isolate from the 5/hour limit — this test is about reason acceptance.
            asyncio.run(fake_redis.delete(rate_key))
            listing_id = _create_listing()
            resp = client.post(
                "/v1/reports",
                json={"listing_id": listing_id, "reason": reason},
            )
            assert resp.status_code == 201, (
                f"Expected 201 for reason '{reason}', got {resp.status_code}"
            )


# ===========================================================================
# TestValidation — input validation rejections
# ===========================================================================

class TestValidation:
    def test_invalid_reason_returns_422(self, client, auth_as_reporter):
        """Spec: an invalid reason value (not in the Literal set) → 422 (Pydantic)."""
        listing_id = _create_listing()
        resp = client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "FAKE_REASON"},
        )
        assert resp.status_code == 422

    def test_lowercase_reason_returns_422(self, client, auth_as_reporter):
        """Spec: reason values are uppercase constants. 'piracy' (lowercase) → 422."""
        listing_id = _create_listing()
        resp = client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "piracy"},
        )
        assert resp.status_code == 422

    def test_empty_string_reason_returns_422(self, client, auth_as_reporter):
        """Spec: empty string is not in the Literal set → 422."""
        listing_id = _create_listing()
        resp = client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": ""},
        )
        assert resp.status_code == 422

    def test_missing_reason_returns_422(self, client, auth_as_reporter):
        """Spec: reason is a required field — omitting it → 422."""
        listing_id = _create_listing()
        resp = client.post(
            "/v1/reports",
            json={"listing_id": listing_id},
        )
        assert resp.status_code == 422

    def test_missing_listing_id_returns_422(self, client, auth_as_reporter):
        """Spec: listing_id is a required field — omitting it → 422."""
        resp = client.post(
            "/v1/reports",
            json={"reason": "PIRACY"},
        )
        assert resp.status_code == 422

    def test_note_exceeding_1000_chars_returns_422(self, client, auth_as_reporter):
        """Spec: note has max_length=1000. A 1001-char note → 422."""
        listing_id = _create_listing()
        long_note = "x" * 1001
        resp = client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "OTHER", "note": long_note},
        )
        assert resp.status_code == 422

    def test_note_exactly_1000_chars_is_accepted(self, client, auth_as_reporter):
        """Spec: max_length=1000 is inclusive — exactly 1000 chars is valid (201)."""
        listing_id = _create_listing()
        exact_note = "a" * 1000
        resp = client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "OTHER", "note": exact_note},
        )
        assert resp.status_code == 201

    def test_invalid_uuid_for_listing_id_returns_422(self, client, auth_as_reporter):
        """Spec: listing_id is uuid.UUID type — a non-UUID string → 422."""
        resp = client.post(
            "/v1/reports",
            json={"listing_id": "not-a-valid-uuid", "reason": "SPAM"},
        )
        assert resp.status_code == 422


# ===========================================================================
# TestListingLookup — 404 scenarios
# ===========================================================================

class TestListingLookup:
    def test_unknown_listing_id_returns_404(self, client, auth_as_reporter):
        """Spec DoD: a listing_id that does not exist → 404."""
        nonexistent_id = str(uuid.uuid4())
        resp = client.post(
            "/v1/reports",
            json={"listing_id": nonexistent_id, "reason": "PIRACY"},
        )
        assert resp.status_code == 404

    def test_soft_deleted_listing_returns_404(self, client, auth_as_reporter):
        """Spec DoD: a listing with deleted_at set (soft-deleted) → 404.
        Moderation removal sets deleted_at; the report endpoint must treat these
        as non-existent so reporters cannot confirm a listing was already removed."""
        deleted_listing_id = _create_listing(is_available=False, deleted_at_set=True)
        resp = client.post(
            "/v1/reports",
            json={"listing_id": deleted_listing_id, "reason": "PIRACY"},
        )
        assert resp.status_code == 404

    def test_paused_listing_is_reportable(self, client, auth_as_reporter):
        """Spec: a listing with is_available=FALSE and deleted_at=NULL is paused —
        NOT removed. It must still be reportable (200 series).
        CLAUDE.md: 'is_available=FALSE, sold_at=NULL is valid — test it doesn't get
        incorrectly flagged.' The report service filters only on deleted_at IS NULL."""
        paused_listing_id = _create_listing(is_available=False, deleted_at_set=False)
        resp = client.post(
            "/v1/reports",
            json={"listing_id": paused_listing_id, "reason": "SPAM"},
        )
        assert resp.status_code == 201


# ===========================================================================
# TestIdempotency — duplicate (listing_id, reporter_id) handling
# ===========================================================================

class TestIdempotency:
    def test_second_report_same_listing_same_reporter_returns_201(
        self, client, auth_as_reporter
    ):
        """Spec DoD: submitting the same (listing_id, reporter_id) twice returns
        the same minimal ack (201) — no 500 from the unique constraint."""
        listing_id = _create_listing()

        first_resp = client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "PIRACY"},
        )
        second_resp = client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "PIRACY"},
        )

        assert first_resp.status_code == 201
        assert second_resp.status_code == 201

    def test_second_report_same_listing_same_reporter_creates_only_one_row(
        self, client, auth_as_reporter
    ):
        """Spec DoD: a duplicate report must NOT create a second DB row.
        The uq_report_once constraint (listing_id, reporter_id) must be the backstop,
        but the service layer must prevent the constraint from being hit at all."""
        listing_id = _create_listing()

        client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "SPAM"},
        )
        client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "SPAM"},
        )

        count = _count_reports_for_listing(listing_id)
        assert count == 1, (
            f"Expected exactly 1 report row for duplicate submission, found {count}"
        )

    def test_duplicate_report_response_body_is_identical_minimal_ack(
        self, client, auth_as_reporter
    ):
        """Spec: the duplicate ack must be identical to the first — no hint that
        a prior report exists (never reveal prior report state)."""
        listing_id = _create_listing()

        first = client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "ABUSIVE"},
        )
        second = client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "ABUSIVE"},
        )

        assert first.json() == second.json()
        assert second.json() == {"received": True}

    def test_different_reporters_same_listing_each_get_201_and_own_row(
        self, client
    ):
        """Spec: uq_report_once is per (listing, reporter) — two different reporters
        reporting the same listing must each succeed and produce their own row."""
        listing_id = _create_listing()

        # First reporter
        app.dependency_overrides[verify_token] = _override_verify_token(REPORTER_ID)
        resp1 = client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "PIRACY"},
        )

        # Second reporter (OTHER_USER_ID)
        app.dependency_overrides[verify_token] = _override_verify_token(OTHER_USER_ID)
        resp2 = client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "PIRACY"},
        )

        app.dependency_overrides.pop(verify_token, None)

        assert resp1.status_code == 201
        assert resp2.status_code == 201

        count = _count_reports_for_listing(listing_id)
        assert count == 2, (
            f"Expected 2 rows (one per distinct reporter), found {count}"
        )


# ===========================================================================
# TestRateLimit — Redis report_rate:{reporter_id} (5 reports/hour)
# ===========================================================================

class TestRateLimit:
    def test_report_rate_limit_counter_key_uses_correct_format(
        self, client, auth_as_reporter, fake_redis
    ):
        """Spec CLAUDE.md: Redis key is `report_rate:{reporter_id}` with TTL 1 hour.
        After a successful report, the key must exist in Redis."""
        listing_id = _create_listing()
        expected_key = f"report_rate:{REPORTER_ID}"

        # Key must not pre-exist
        assert asyncio.run(fake_redis.get(expected_key)) is None

        client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "SPAM"},
        )

        counter = asyncio.run(fake_redis.get(expected_key))
        assert counter is not None, "Rate-limit key must be created on first report"

    def test_report_rate_limit_counter_increments_per_report(
        self, client, auth_as_reporter, fake_redis
    ):
        """Spec: each distinct report increments the counter by 1."""
        rate_key = f"report_rate:{REPORTER_ID}"

        for _ in range(3):
            listing_id = _create_listing()
            client.post(
                "/v1/reports",
                json={"listing_id": listing_id, "reason": "SPAM"},
            )

        counter = int(asyncio.run(fake_redis.get(rate_key)))
        assert counter == 3

    def test_5th_report_succeeds(self, client, auth_as_reporter, fake_redis):
        """Spec: 5 reports/hour is the limit. The 5th report (counter at 4
        before send) must still return 201."""
        rate_key = f"report_rate:{REPORTER_ID}"
        # Pre-seed to 4 (one below the limit)
        asyncio.run(fake_redis.set(rate_key, 4))

        listing_id = _create_listing()
        resp = client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "SPAM"},
        )
        assert resp.status_code == 201

    def test_6th_report_returns_429(self, client, auth_as_reporter, fake_redis):
        """Spec DoD: exceeding 5 reports/hour for one reporter → 429.
        Counter pre-seeded to 5 (all slots exhausted); next request must be blocked."""
        rate_key = f"report_rate:{REPORTER_ID}"
        # Pre-seed to 5 (limit already reached)
        asyncio.run(fake_redis.set(rate_key, 5))

        listing_id = _create_listing()
        resp = client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "PIRACY"},
        )
        assert resp.status_code == 429

    def test_rate_limit_is_per_reporter_not_global(
        self, client, fake_redis
    ):
        """Spec: rate limit is scoped to the reporter. Exhausting one reporter's
        quota must not affect a second reporter."""
        listing_id_1 = _create_listing()
        listing_id_2 = _create_listing()

        # Exhaust REPORTER_ID's quota
        asyncio.run(fake_redis.set(f"report_rate:{REPORTER_ID}", 20))

        # REPORTER_ID is blocked
        app.dependency_overrides[verify_token] = _override_verify_token(REPORTER_ID)
        blocked_resp = client.post(
            "/v1/reports",
            json={"listing_id": listing_id_1, "reason": "SPAM"},
        )
        assert blocked_resp.status_code == 429

        # OTHER_USER_ID still has capacity (counter absent = 0)
        app.dependency_overrides[verify_token] = _override_verify_token(OTHER_USER_ID)
        allowed_resp = client.post(
            "/v1/reports",
            json={"listing_id": listing_id_2, "reason": "SPAM"},
        )
        assert allowed_resp.status_code == 201

        app.dependency_overrides.pop(verify_token, None)

    def test_rate_limit_counter_ttl_is_one_hour(
        self, client, auth_as_reporter, fake_redis
    ):
        """Spec CLAUDE.md: report_rate TTL is 1 hour (3600 seconds).
        Intercept the expire call to confirm the TTL value."""
        rate_key = f"report_rate:{REPORTER_ID}"
        captured_ttls: list = []
        real_expire = fake_redis.expire

        async def _spy_expire(key: str, ttl: int, nx: bool = False) -> bool:
            if key == rate_key:
                captured_ttls.append(ttl)
            return await real_expire(key, ttl, nx=nx)

        fake_redis.expire = _spy_expire

        listing_id = _create_listing()
        resp = client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "SPAM"},
        )
        assert resp.status_code == 201
        assert 3600 in captured_ttls, (
            f"Expected rate-limit TTL of 3600s to be set; captured: {captured_ttls}"
        )

    def test_rate_limit_counter_ttl_set_only_once_within_window(
        self, client, auth_as_reporter, fake_redis
    ):
        """Spec: the 1-hour window is set once and a second report from the same
        reporter within it must NOT reset the TTL. The service uses expire(nx=True),
        so even though expire is called per request, the TTL is *written* only once."""
        rate_key = f"report_rate:{REPORTER_ID}"
        ttl_writes = [0]
        real_expire = fake_redis.expire

        async def _spy_expire(key: str, ttl: int, nx: bool = False) -> bool:
            result = await real_expire(key, ttl, nx=nx)
            # result is True only when a TTL was actually written (nx semantics).
            if key == rate_key and result:
                ttl_writes[0] += 1
            return result

        fake_redis.expire = _spy_expire

        listing_id_1 = _create_listing()
        listing_id_2 = _create_listing()

        client.post("/v1/reports", json={"listing_id": listing_id_1, "reason": "SPAM"})
        client.post("/v1/reports", json={"listing_id": listing_id_2, "reason": "SPAM"})

        # The TTL must have been written exactly once for the rate-limit key.
        assert ttl_writes[0] == 1, (
            f"TTL must be written once (window not reset on later reports), "
            f"got {ttl_writes[0]} writes"
        )

    def test_rate_limited_request_does_not_persist_a_report_row(
        self, client, auth_as_reporter, fake_redis
    ):
        """Spec: a 429 response must not write a report row — the rate-limit
        check happens before the DB write."""
        rate_key = f"report_rate:{REPORTER_ID}"
        asyncio.run(fake_redis.set(rate_key, 20))

        listing_id = _create_listing()
        resp = client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "PIRACY"},
        )
        assert resp.status_code == 429
        count = _count_reports_for_listing(listing_id)
        assert count == 0, "No report row must be written when rate-limited"


# ===========================================================================
# TestNoAutoModeration — reporting must never auto-hide listings
# ===========================================================================

class TestNoAutoModeration:
    def test_report_does_not_change_listing_is_available(
        self, client, auth_as_reporter
    ):
        """Spec: reporting is never automated — the listing's is_available field
        must remain TRUE after a successful report. Moderation is manual-only."""
        listing_id = _create_listing(is_available=True)

        resp = client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "PIRACY"},
        )
        assert resp.status_code == 201

        row = _get_listing_row(listing_id)
        assert row is not None
        assert row["is_available"] is True, (
            "Reporting must never auto-set is_available=FALSE (no automated moderation)"
        )

    def test_report_does_not_set_listing_deleted_at(
        self, client, auth_as_reporter
    ):
        """Spec: reporting must not set deleted_at on the listing.
        Only a human moderator can set deleted_at via the Supabase dashboard."""
        listing_id = _create_listing()

        client.post(
            "/v1/reports",
            json={"listing_id": listing_id, "reason": "CONTACT_INFO"},
        )

        row = _get_listing_row(listing_id)
        assert row is not None
        assert row["deleted_at"] is None, (
            "Reporting must never set deleted_at — no automated moderation in v1"
        )

    def test_multiple_reports_from_different_users_do_not_auto_hide_listing(
        self, client, fake_redis
    ):
        """Spec: 'What NOT to build in v1 — automated moderation'. Even multiple
        distinct reports must not trigger automatic listing removal."""
        listing_id = _create_listing()

        for user_id in [REPORTER_ID, OTHER_USER_ID]:
            app.dependency_overrides[verify_token] = _override_verify_token(user_id)
            client.post(
                "/v1/reports",
                json={"listing_id": listing_id, "reason": "SPAM"},
            )

        app.dependency_overrides.pop(verify_token, None)

        row = _get_listing_row(listing_id)
        assert row["is_available"] is True
        assert row["deleted_at"] is None


# ===========================================================================
# TestResponseShape — verify the response schema contract
# ===========================================================================

class TestResponseShape:
    def test_report_ack_schema_has_exactly_received_field(self):
        """Spec: ReportAck is deliberately minimal. Its Pydantic model must declare
        only 'received'. Any extra field is a spec violation."""
        fields = set(ReportAck.model_fields.keys())
        assert fields == {"received"}, (
            f"ReportAck must declare only 'received'; found: {fields}"
        )

    def test_report_ack_received_defaults_to_true(self):
        """Spec: received: bool = True — the default value must be True."""
        ack = ReportAck()
        assert ack.received is True

    def test_report_create_schema_listing_id_is_uuid(self):
        """Spec: listing_id is uuid.UUID — Pydantic must reject non-UUID strings."""
        import pydantic

        with pytest.raises((pydantic.ValidationError, Exception)):
            ReportCreate(listing_id="not-a-uuid", reason="SPAM")

    def test_report_create_schema_rejects_invalid_reason(self):
        """Spec: reason is Literal[...] — an out-of-range value must raise
        Pydantic ValidationError at the schema level."""
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            ReportCreate(
                listing_id=uuid.uuid4(),
                reason="COMPLETELY_INVALID",
            )


# ===========================================================================
# TestDbConstraints — model-level constraint declarations (no DB connection)
# ===========================================================================

class TestDbConstraints:
    """Pure metadata tests — mirrors test_06_schema.py style. No DB connection."""

    def _constraint_names(self, model):
        from sqlalchemy import CheckConstraint, UniqueConstraint
        args = getattr(model, "__table_args__", ())
        if isinstance(args, dict):
            return set()
        names = set()
        for item in args:
            if isinstance(item, (CheckConstraint, UniqueConstraint)):
                if item.name:
                    names.add(item.name)
        return names

    def test_report_model_has_reason_check_constraint(self):
        """Spec: reports.reason must have a CHECK constraint covering the 7 values."""
        names = self._constraint_names(Report)
        assert "ck_report_reason" in names, (
            "Report model must declare 'ck_report_reason' CHECK constraint"
        )

    def test_report_model_has_status_check_constraint(self):
        """Spec: reports.status must have a CHECK constraint for open/actioned/dismissed."""
        names = self._constraint_names(Report)
        assert "ck_report_status" in names, (
            "Report model must declare 'ck_report_status' CHECK constraint"
        )

    def test_report_model_has_uq_report_once_unique_constraint(self):
        """Spec: CONSTRAINT uq_report_once UNIQUE (listing_id, reporter_id)."""
        names = self._constraint_names(Report)
        assert "uq_report_once" in names, (
            "Report model must declare 'uq_report_once' UNIQUE constraint"
        )

    def test_report_model_tablename_is_reports(self):
        """Spec: the SQLAlchemy model's __tablename__ must be 'reports'."""
        assert Report.__tablename__ == "reports"

    def test_report_model_has_required_columns(self):
        """Spec: reports table columns: id, listing_id, reporter_id, reason, note,
        status, created_at."""
        columns = {c.key for c in Report.__table__.columns}
        required = {"id", "listing_id", "reporter_id", "reason", "note", "status", "created_at"}
        for col in required:
            assert col in columns, f"Report model missing column '{col}'"

    def test_report_model_status_column_is_not_nullable(self):
        """Spec: status is NOT NULL (server_default='open')."""
        status_col = Report.__table__.columns["status"]
        assert not status_col.nullable, "reports.status must be NOT NULL"

    def test_report_model_reason_column_is_not_nullable(self):
        """Spec: reason is NOT NULL."""
        reason_col = Report.__table__.columns["reason"]
        assert not reason_col.nullable, "reports.reason must be NOT NULL"

    def test_report_model_note_column_is_nullable(self):
        """Spec: note is optional (nullable)."""
        note_col = Report.__table__.columns["note"]
        assert note_col.nullable, "reports.note must be nullable (optional)"


# ===========================================================================
# TestRouteRegistration — confirm /v1/reports is mounted on the FastAPI app
# ===========================================================================

class TestRouteRegistration:
    def test_reports_post_route_exists_under_v1(self):
        """Spec: POST /v1/reports is the canonical endpoint path (CLAUDE.md)."""
        paths = {route.path for route in app.routes}
        assert "/v1/reports" in paths, (
            "POST /v1/reports must be registered on the FastAPI app"
        )

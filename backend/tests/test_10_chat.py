"""
Tests for Spec 10 — Chat.

Endpoints under test:
  GET    /v1/conversations
  POST   /v1/conversations
  GET    /v1/conversations/{id}/messages
  POST   /v1/conversations/{id}/messages
  PATCH  /v1/conversations/{id}/messages/read

These tests are derived from .claude/specs/technical/chat.md and CLAUDE.md —
NOT from reading the implementation. Auth is mocked via FastAPI dependency
overrides on `verify_token`; Redis is replaced with FakeRedis; external
Resend/supabase_admin calls are mocked via unittest.mock.

Run from project root:
    cd backend && ..\\.venv\\Scripts\\python.exe -m pytest tests/test_10_chat.py -v
"""

import asyncio
import json
import sys
import uuid
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
from app.core.security import verify_token
from app.core.database import get_db, AsyncSessionLocal
from app.core.redis import get_redis
from app.schemas.chat import ConversationOut, MessageOut

# ---------------------------------------------------------------------------
# Stable test identity UUIDs
# ---------------------------------------------------------------------------
BUYER_ID = str(uuid.uuid4())
SELLER_ID = str(uuid.uuid4())
OTHER_USER_ID = str(uuid.uuid4())


# ===========================================================================
# FakeRedis — in-memory async Redis substitute
# ===========================================================================

class FakeRedis:
    """Minimal in-memory async Redis substitute.

    Supports: get, set, incr, expire, delete, pipeline().
    The pipeline supports incr and expire, and returns results via execute().
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

def _override_verify_token(user_id: str, email: str | None = None):
    """Return a no-arg callable that yields a fake JWT payload."""
    def _inner():
        return {"sub": user_id, "email": email or f"{user_id}@example.com"}
    return _inner


def _seed_users():
    async def _run():
        async with AsyncSessionLocal() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO public.users (id, full_name)
                    VALUES
                        (:buyer_id,  'Test Buyer'),
                        (:seller_id, 'Test Seller'),
                        (:other_id,  'Test Other User')
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {
                    "buyer_id": BUYER_ID,
                    "seller_id": SELLER_ID,
                    "other_id": OTHER_USER_ID,
                },
            )
            await session.commit()

    asyncio.run(_run())


def _cleanup():
    async def _run():
        ids = [BUYER_ID, SELLER_ID, OTHER_USER_ID]
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("DELETE FROM public.messages WHERE sender_id = ANY(:ids)"),
                {"ids": ids},
            )
            await session.execute(
                text(
                    "DELETE FROM public.conversations WHERE buyer_id = ANY(:ids) OR seller_id = ANY(:ids)"
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


def _create_listing(seller_id: str = SELLER_ID, is_available: bool = True) -> str:
    listing_id = str(uuid.uuid4())

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
                        (:id, :seller_id, 'Test Listing', 'desc', 'JEE_MAINS', 'Physics',
                         'BOOK', 'A', 300, 500, 'Delhi',
                         ARRAY['https://res.cloudinary.com/demo/image/upload/v1/x.jpg'],
                         :is_available, 'dummyhash0123456789abcdef0123456789abcdef0123456789abcdef01234567')
                    """
                ),
                {
                    "id": listing_id,
                    "seller_id": seller_id,
                    "is_available": is_available,
                },
            )
            await session.commit()

    asyncio.run(_run())
    return listing_id


def _create_conversation(
    listing_id: str,
    buyer_id: str = BUYER_ID,
    seller_id: str = SELLER_ID,
    first_message_notified: bool = False,
) -> str:
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
    sender_id: str = BUYER_ID,
    body: str = "Hello, is this still available?",
    is_read: bool = False,
) -> str:
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


def _get_conversation_row(conv_id: str) -> dict | None:
    async def _run():
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT * FROM public.conversations WHERE id = :id"),
                {"id": conv_id},
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


def _get_messages_for_conversation(conv_id: str) -> list[dict]:
    async def _run():
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text(
                    "SELECT * FROM public.messages WHERE conversation_id = :id ORDER BY created_at ASC"
                ),
                {"id": conv_id},
            )
            return [dict(row) for row in result.mappings().all()]

    return asyncio.run(_run())


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
def auth_as_buyer():
    app.dependency_overrides[verify_token] = _override_verify_token(BUYER_ID)
    yield BUYER_ID
    app.dependency_overrides.pop(verify_token, None)


@pytest.fixture
def auth_as_seller():
    app.dependency_overrides[verify_token] = _override_verify_token(SELLER_ID)
    yield SELLER_ID
    app.dependency_overrides.pop(verify_token, None)


@pytest.fixture
def auth_as_other():
    app.dependency_overrides[verify_token] = _override_verify_token(OTHER_USER_ID)
    yield OTHER_USER_ID
    app.dependency_overrides.pop(verify_token, None)


# ===========================================================================
# TestConversationCreate
# ===========================================================================

class TestConversationCreate:
    def test_create_conversation_returns_200_and_conversation_id(
        self, client, auth_as_buyer
    ):
        """POST /conversations with a valid available listing creates a conversation
        and returns the conversation object including its id."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        resp = client.post("/v1/conversations", json={"listing_id": listing_id})
        assert resp.status_code == 200
        body = resp.json()
        assert "id" in body
        assert body["listing_id"] == listing_id

    def test_create_conversation_idempotent_same_buyer_same_listing(
        self, client, auth_as_buyer
    ):
        """A second POST with the same listing_id and caller returns the same
        conversation id (UNIQUE(listing_id, buyer_id) constraint — get-or-create)."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        first = client.post("/v1/conversations", json={"listing_id": listing_id})
        second = client.post("/v1/conversations", json={"listing_id": listing_id})
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["id"] == second.json()["id"]

    def test_create_conversation_seller_cannot_message_own_listing_returns_403(
        self, client, auth_as_seller
    ):
        """A seller who owns the listing must receive 403 when trying to start
        a conversation about their own listing."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        resp = client.post("/v1/conversations", json={"listing_id": listing_id})
        assert resp.status_code == 403

    def test_create_conversation_listing_not_found_returns_404(
        self, client, auth_as_buyer
    ):
        """A listing_id that does not exist in the DB must return 404."""
        nonexistent_id = str(uuid.uuid4())
        resp = client.post("/v1/conversations", json={"listing_id": nonexistent_id})
        assert resp.status_code == 404

    def test_create_conversation_unavailable_listing_returns_404(
        self, client, auth_as_buyer
    ):
        """A listing with is_available=FALSE must return 404 — cannot start a
        conversation on an unavailable (paused/sold) listing."""
        listing_id = _create_listing(seller_id=SELLER_ID, is_available=False)
        resp = client.post("/v1/conversations", json={"listing_id": listing_id})
        assert resp.status_code == 404

    def test_create_conversation_requires_auth_returns_401(self, client):
        """POST /conversations with no Authorization header must return 401."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        resp = client.post("/v1/conversations", json={"listing_id": listing_id})
        assert resp.status_code == 401

    def test_create_conversation_response_contains_buyer_and_seller_ids(
        self, client, auth_as_buyer
    ):
        """Conversation response must expose buyer_id and seller_id fields."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        resp = client.post("/v1/conversations", json={"listing_id": listing_id})
        assert resp.status_code == 200
        body = resp.json()
        assert "buyer_id" in body
        assert "seller_id" in body

    def test_create_conversation_response_has_no_email_or_phone(
        self, client, auth_as_buyer
    ):
        """ConversationOut must NEVER contain email or phone fields."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        resp = client.post("/v1/conversations", json={"listing_id": listing_id})
        assert resp.status_code == 200
        body = resp.json()
        assert "email" not in body
        assert "phone" not in body


# ===========================================================================
# TestListConversations
# ===========================================================================

class TestListConversations:
    def test_list_conversations_returns_buyer_conversations(
        self, client, auth_as_buyer
    ):
        """GET /conversations returns conversations in which the caller is the buyer."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        _create_conversation(listing_id, buyer_id=BUYER_ID, seller_id=SELLER_ID)
        resp = client.get("/v1/conversations")
        assert resp.status_code == 200
        ids = [c["buyer_id"] for c in resp.json()]
        assert any(bid == BUYER_ID for bid in ids)

    def test_list_conversations_returns_seller_conversations(
        self, client, auth_as_seller
    ):
        """GET /conversations returns conversations in which the caller is the seller."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        _create_conversation(listing_id, buyer_id=BUYER_ID, seller_id=SELLER_ID)
        resp = client.get("/v1/conversations")
        assert resp.status_code == 200
        ids = [c["seller_id"] for c in resp.json()]
        assert any(sid == SELLER_ID for sid in ids)

    def test_list_conversations_excludes_other_users_conversations(
        self, client, auth_as_other
    ):
        """GET /conversations for a user with no conversations returns an empty list."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        # Create a conversation between buyer and seller — other user is not a participant
        _create_conversation(listing_id, buyer_id=BUYER_ID, seller_id=SELLER_ID)
        resp = client.get("/v1/conversations")
        assert resp.status_code == 200
        body = resp.json()
        # OTHER_USER_ID is not buyer or seller in any created conversation
        for conv in body:
            assert conv["buyer_id"] != OTHER_USER_ID
            assert conv["seller_id"] != OTHER_USER_ID

    def test_list_conversations_requires_auth_returns_401(self, client):
        """GET /conversations with no Authorization header must return 401."""
        resp = client.get("/v1/conversations")
        assert resp.status_code == 401

    def test_list_conversations_returns_list_type(self, client, auth_as_buyer):
        """Response body must be a JSON array."""
        resp = client.get("/v1/conversations")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ===========================================================================
# TestGetMessages
# ===========================================================================

class TestGetMessages:
    def test_get_messages_returns_messages_for_participant(
        self, client, auth_as_buyer
    ):
        """GET /conversations/{id}/messages for a participant returns a list of
        messages ordered by created_at asc."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)
        _create_message(conv_id, sender_id=BUYER_ID, body="First message")
        _create_message(conv_id, sender_id=SELLER_ID, body="Second message")
        resp = client.get(f"/v1/conversations/{conv_id}/messages")
        assert resp.status_code == 200
        messages = resp.json()
        assert isinstance(messages, list)
        assert len(messages) >= 2

    def test_get_messages_non_participant_returns_403(self, client, auth_as_other):
        """GET /conversations/{id}/messages for a non-participant must return 403."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id, buyer_id=BUYER_ID, seller_id=SELLER_ID)
        resp = client.get(f"/v1/conversations/{conv_id}/messages")
        assert resp.status_code == 403

    def test_get_messages_requires_auth_returns_401(self, client):
        """GET /conversations/{id}/messages with no Authorization header must return 401."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)
        resp = client.get(f"/v1/conversations/{conv_id}/messages")
        assert resp.status_code == 401

    def test_get_messages_uses_redis_cache_on_second_call(
        self, client, auth_as_buyer, fake_redis
    ):
        """First call populates Redis cache (key chat:{conv_id}, TTL 30s).
        Second call must hit the cache (Redis get returns a value, DB is not
        queried again). We verify the cache key is populated after the first call."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)
        _create_message(conv_id, sender_id=BUYER_ID)

        cache_key = f"chat:{conv_id}"
        # Confirm cache is empty before first call
        assert asyncio.run(fake_redis.get(cache_key)) is None

        # First call — should populate cache
        first_resp = client.get(f"/v1/conversations/{conv_id}/messages")
        assert first_resp.status_code == 200
        cached_value = asyncio.run(fake_redis.get(cache_key))
        assert cached_value is not None

        # Second call — cache should be served (value is still present)
        second_resp = client.get(f"/v1/conversations/{conv_id}/messages")
        assert second_resp.status_code == 200
        # Both calls return the same message data
        assert first_resp.json() == second_resp.json()

    def test_get_messages_cache_key_uses_correct_format(
        self, client, auth_as_buyer, fake_redis
    ):
        """The Redis cache key must be exactly `chat:{conversation_id}` (CLAUDE.md)."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)
        _create_message(conv_id, sender_id=BUYER_ID)

        client.get(f"/v1/conversations/{conv_id}/messages")

        expected_key = f"chat:{conv_id}"
        assert asyncio.run(fake_redis.get(expected_key)) is not None

    def test_get_messages_response_has_no_contact_fields(
        self, client, auth_as_buyer
    ):
        """MessageOut must NEVER contain email, phone, avatar_url, or full_name."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)
        _create_message(conv_id, sender_id=BUYER_ID)

        resp = client.get(f"/v1/conversations/{conv_id}/messages")
        assert resp.status_code == 200
        for msg in resp.json():
            assert "email" not in msg
            assert "phone" not in msg
            assert "avatar_url" not in msg
            assert "full_name" not in msg

    def test_get_messages_response_fields_match_message_schema(
        self, client, auth_as_buyer
    ):
        """Each message in the response must contain id, conversation_id, sender_id,
        body, is_read, created_at — the documented MessageOut fields."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)
        _create_message(conv_id, sender_id=BUYER_ID, body="Schema check")

        resp = client.get(f"/v1/conversations/{conv_id}/messages")
        assert resp.status_code == 200
        messages = resp.json()
        assert len(messages) >= 1
        msg = messages[0]
        for field in ("id", "conversation_id", "sender_id", "body", "is_read", "created_at"):
            assert field in msg, f"Expected field '{field}' missing from MessageOut"

    def test_get_messages_nonexistent_conversation_returns_404(
        self, client, auth_as_buyer
    ):
        """GET /conversations/{id}/messages for a conversation that does not exist
        returns 404 — the conversation cannot be found."""
        nonexistent_id = str(uuid.uuid4())
        resp = client.get(f"/v1/conversations/{nonexistent_id}/messages")
        assert resp.status_code == 404


# ===========================================================================
# TestSendMessage
# ===========================================================================

class TestSendMessage:
    def test_send_message_returns_201_with_message_object(
        self, client, auth_as_buyer
    ):
        """POST /conversations/{id}/messages with valid body returns 201 and
        a MessageOut object."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)

        with patch("app.services.chat_service.supabase_admin.fetch_user_email", new_callable=AsyncMock) as mock_email, \
             patch("app.services.chat_service.notification_service.send_new_message_email", new_callable=AsyncMock):
            mock_email.return_value = "seller@example.com"
            resp = client.post(
                f"/v1/conversations/{conv_id}/messages",
                json={"body": "Is this still available?"},
            )

        assert resp.status_code == 201
        body = resp.json()
        assert "id" in body
        assert body["body"] == "Is this still available?"
        assert body["sender_id"] == BUYER_ID

    def test_send_message_empty_body_returns_422(self, client, auth_as_buyer):
        """POST /conversations/{id}/messages with empty string body must return 422."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)
        resp = client.post(
            f"/v1/conversations/{conv_id}/messages",
            json={"body": ""},
        )
        assert resp.status_code == 422

    def test_send_message_whitespace_only_body_returns_422(
        self, client, auth_as_buyer
    ):
        """POST /conversations/{id}/messages with a whitespace-only body must
        return 422 — Pydantic validator strips and checks emptiness."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)
        resp = client.post(
            f"/v1/conversations/{conv_id}/messages",
            json={"body": "     "},
        )
        assert resp.status_code == 422

    def test_send_message_body_over_2000_chars_returns_422(
        self, client, auth_as_buyer
    ):
        """POST /conversations/{id}/messages with a body > 2000 characters must
        return 422."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)
        long_body = "x" * 2001
        resp = client.post(
            f"/v1/conversations/{conv_id}/messages",
            json={"body": long_body},
        )
        assert resp.status_code == 422

    def test_send_message_body_exactly_2000_chars_succeeds(
        self, client, auth_as_buyer
    ):
        """POST /conversations/{id}/messages with exactly 2000 characters must
        succeed — boundary inclusive."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)
        exact_body = "a" * 2000

        with patch("app.services.chat_service.supabase_admin.fetch_user_email", new_callable=AsyncMock) as mock_email, \
             patch("app.services.chat_service.notification_service.send_new_message_email", new_callable=AsyncMock):
            mock_email.return_value = "seller@example.com"
            resp = client.post(
                f"/v1/conversations/{conv_id}/messages",
                json={"body": exact_body},
            )

        assert resp.status_code == 201

    def test_send_message_non_participant_returns_403(self, client, auth_as_other):
        """POST /conversations/{id}/messages by a non-participant must return 403."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id, buyer_id=BUYER_ID, seller_id=SELLER_ID)
        resp = client.post(
            f"/v1/conversations/{conv_id}/messages",
            json={"body": "Intruder message"},
        )
        assert resp.status_code == 403

    def test_send_message_requires_auth_returns_401(self, client):
        """POST /conversations/{id}/messages with no Authorization header must return 401."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)
        resp = client.post(
            f"/v1/conversations/{conv_id}/messages",
            json={"body": "Hello"},
        )
        assert resp.status_code == 401

    def test_send_message_rate_limit_429_on_101st_message(
        self, client, auth_as_buyer, fake_redis
    ):
        """When the rate-limit counter for this user/conversation is already at
        100 (RATE_LIMIT), the next send must return 429 — no message is stored.
        Redis key: chat_rate:{conv_id}:{sender_id}, limit 100 msgs/user/conv/hour."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)

        # Pre-seed the counter at exactly 100 (at the limit)
        rate_key = f"chat_rate:{conv_id}:{BUYER_ID}"
        asyncio.run(fake_redis.set(rate_key, 100))

        resp = client.post(
            f"/v1/conversations/{conv_id}/messages",
            json={"body": "Over the limit"},
        )
        assert resp.status_code == 429

    def test_send_message_rate_limit_100th_message_succeeds(
        self, client, auth_as_buyer, fake_redis
    ):
        """The 100th message (counter at 99 before send) must still succeed.
        The limit kicks in when the stored counter is already >= 100."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id, first_message_notified=True)

        # Pre-seed counter at 99 — one below limit
        rate_key = f"chat_rate:{conv_id}:{BUYER_ID}"
        asyncio.run(fake_redis.set(rate_key, 99))

        with patch("app.services.chat_service.supabase_admin.fetch_user_email", new_callable=AsyncMock), \
             patch("app.services.chat_service.notification_service.send_new_message_email", new_callable=AsyncMock):
            resp = client.post(
                f"/v1/conversations/{conv_id}/messages",
                json={"body": "100th message"},
            )

        assert resp.status_code == 201

    def test_send_message_rate_limit_counter_uses_correct_redis_key(
        self, client, auth_as_buyer, fake_redis
    ):
        """After a successful send, the Redis counter key must be exactly
        `chat_rate:{conversation_id}:{sender_id}` (CLAUDE.md)."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id, first_message_notified=True)
        expected_key = f"chat_rate:{conv_id}:{BUYER_ID}"

        # Ensure key does not pre-exist
        assert asyncio.run(fake_redis.get(expected_key)) is None

        with patch("app.services.chat_service.supabase_admin.fetch_user_email", new_callable=AsyncMock), \
             patch("app.services.chat_service.notification_service.send_new_message_email", new_callable=AsyncMock):
            resp = client.post(
                f"/v1/conversations/{conv_id}/messages",
                json={"body": "Rate key test"},
            )

        assert resp.status_code == 201
        counter = asyncio.run(fake_redis.get(expected_key))
        assert counter is not None
        assert int(counter) == 1

    def test_send_message_clears_message_cache(
        self, client, auth_as_buyer, fake_redis
    ):
        """After a successful send, the Redis message cache key `chat:{conv_id}`
        must be deleted so subsequent GET calls see fresh data."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id, first_message_notified=True)

        # Pre-seed a cache entry
        cache_key = f"chat:{conv_id}"
        asyncio.run(fake_redis.set(cache_key, json.dumps([])))
        assert asyncio.run(fake_redis.get(cache_key)) is not None

        with patch("app.services.chat_service.supabase_admin.fetch_user_email", new_callable=AsyncMock), \
             patch("app.services.chat_service.notification_service.send_new_message_email", new_callable=AsyncMock):
            resp = client.post(
                f"/v1/conversations/{conv_id}/messages",
                json={"body": "Cache clear test"},
            )

        assert resp.status_code == 201
        # Cache must have been deleted after the send
        assert asyncio.run(fake_redis.get(cache_key)) is None

    def test_send_message_triggers_first_message_email_once(
        self, client, auth_as_buyer
    ):
        """When first_message_notified=False, sending the first message must
        call supabase_admin.fetch_user_email to resolve the seller email and
        then send a notification email."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        # first_message_notified defaults to False
        conv_id = _create_conversation(listing_id, first_message_notified=False)

        with patch(
            "app.services.chat_service.supabase_admin.fetch_user_email",
            new_callable=AsyncMock,
        ) as mock_email, patch(
            "app.services.chat_service.notification_service.send_new_message_email",
            new_callable=AsyncMock,
        ) as mock_notify:
            mock_email.return_value = "seller@example.com"
            resp = client.post(
                f"/v1/conversations/{conv_id}/messages",
                json={"body": "First ever message"},
            )

        assert resp.status_code == 201
        mock_email.assert_awaited_once()
        mock_notify.assert_awaited_once()

    def test_send_message_does_not_trigger_email_on_second_message(
        self, client, auth_as_buyer
    ):
        """When first_message_notified=True, sending a subsequent message must
        NOT call fetch_user_email or send a notification email."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id, first_message_notified=True)

        with patch(
            "app.services.chat_service.supabase_admin.fetch_user_email",
            new_callable=AsyncMock,
        ) as mock_email, patch(
            "app.services.chat_service.notification_service.send_new_message_email",
            new_callable=AsyncMock,
        ) as mock_notify:
            resp = client.post(
                f"/v1/conversations/{conv_id}/messages",
                json={"body": "Second message — no email"},
            )

        assert resp.status_code == 201
        mock_email.assert_not_awaited()
        mock_notify.assert_not_awaited()

    def test_send_message_persists_to_db(self, client, auth_as_buyer):
        """A successful send must write one row to the messages table in the DB."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id, first_message_notified=True)

        with patch("app.services.chat_service.supabase_admin.fetch_user_email", new_callable=AsyncMock), \
             patch("app.services.chat_service.notification_service.send_new_message_email", new_callable=AsyncMock):
            resp = client.post(
                f"/v1/conversations/{conv_id}/messages",
                json={"body": "Persisted message"},
            )

        assert resp.status_code == 201
        msg_id = resp.json()["id"]
        row = _get_message_row(msg_id)
        assert row is not None
        assert row["body"] == "Persisted message"
        assert str(row["sender_id"]) == BUYER_ID

    def test_send_message_response_has_no_contact_fields(
        self, client, auth_as_buyer
    ):
        """The MessageOut response from a send must NEVER contain email, phone,
        avatar_url, or full_name."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id, first_message_notified=True)

        with patch("app.services.chat_service.supabase_admin.fetch_user_email", new_callable=AsyncMock), \
             patch("app.services.chat_service.notification_service.send_new_message_email", new_callable=AsyncMock):
            resp = client.post(
                f"/v1/conversations/{conv_id}/messages",
                json={"body": "PII check message"},
            )

        assert resp.status_code == 201
        body = resp.json()
        for forbidden in ("email", "phone", "avatar_url", "full_name"):
            assert forbidden not in body, f"Forbidden field '{forbidden}' found in MessageOut response"

    def test_send_message_rate_limit_counter_ttl_is_one_hour(
        self, client, auth_as_buyer, fake_redis
    ):
        """The rate-limit counter key must have a TTL of 3600 seconds (1 hour).
        Verify by intercepting the expire call on the rate-limit key."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id, first_message_notified=True)

        captured_ttls: list = []
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
# TestMarkRead
# ===========================================================================

class TestMarkRead:
    def test_mark_read_returns_204(self, client, auth_as_buyer):
        """PATCH /conversations/{id}/messages/read for a participant must return 204."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)
        _create_message(conv_id, sender_id=SELLER_ID, body="Seller message", is_read=False)

        resp = client.patch(f"/v1/conversations/{conv_id}/messages/read")
        assert resp.status_code == 204

    def test_mark_read_non_participant_returns_403(self, client, auth_as_other):
        """PATCH /conversations/{id}/messages/read by a non-participant must return 403."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id, buyer_id=BUYER_ID, seller_id=SELLER_ID)
        resp = client.patch(f"/v1/conversations/{conv_id}/messages/read")
        assert resp.status_code == 403

    def test_mark_read_requires_auth_returns_401(self, client):
        """PATCH /conversations/{id}/messages/read with no Authorization header
        must return 401."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)
        resp = client.patch(f"/v1/conversations/{conv_id}/messages/read")
        assert resp.status_code == 401

    def test_mark_read_only_marks_other_party_messages(self, client, auth_as_buyer):
        """PATCH mark-read must ONLY mark messages where sender_id != caller.
        The caller's own messages must NOT be marked as read by this operation."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)

        # Seller's unread message — should be marked read
        seller_msg_id = _create_message(
            conv_id, sender_id=SELLER_ID, body="Seller unread", is_read=False
        )
        # Buyer's own unread message — must NOT be affected
        buyer_msg_id = _create_message(
            conv_id, sender_id=BUYER_ID, body="Buyer own message", is_read=False
        )

        resp = client.patch(f"/v1/conversations/{conv_id}/messages/read")
        assert resp.status_code == 204

        seller_row = _get_message_row(seller_msg_id)
        buyer_row = _get_message_row(buyer_msg_id)

        assert seller_row["is_read"] is True, "Seller's message must be marked read"
        assert buyer_row["is_read"] is False, "Buyer's own message must NOT be marked read"

    def test_mark_read_clears_cache(self, client, auth_as_buyer, fake_redis):
        """PATCH mark-read must delete the Redis message cache key `chat:{conv_id}`
        so subsequent GET calls reflect the updated read state."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)
        _create_message(conv_id, sender_id=SELLER_ID, is_read=False)

        # Pre-seed cache
        cache_key = f"chat:{conv_id}"
        asyncio.run(fake_redis.set(cache_key, json.dumps([])))
        assert asyncio.run(fake_redis.get(cache_key)) is not None

        resp = client.patch(f"/v1/conversations/{conv_id}/messages/read")
        assert resp.status_code == 204

        # Cache must be cleared after mark-read
        assert asyncio.run(fake_redis.get(cache_key)) is None

    def test_mark_read_cache_key_uses_correct_format(
        self, client, auth_as_buyer, fake_redis
    ):
        """The delete call on mark-read must target `chat:{conv_id}` exactly."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)
        _create_message(conv_id, sender_id=SELLER_ID, is_read=False)

        # Pre-seed cache so delete has something to remove
        cache_key = f"chat:{conv_id}"
        asyncio.run(fake_redis.set(cache_key, json.dumps([])))

        resp = client.patch(f"/v1/conversations/{conv_id}/messages/read")
        assert resp.status_code == 204

        assert cache_key in fake_redis._deleted_keys

    def test_mark_read_nonexistent_conversation_returns_404(
        self, client, auth_as_buyer
    ):
        """PATCH mark-read on a nonexistent conversation must return 404."""
        resp = client.patch(f"/v1/conversations/{uuid.uuid4()}/messages/read")
        assert resp.status_code == 404

    def test_mark_read_204_has_no_response_body(self, client, auth_as_buyer):
        """204 No Content must have an empty response body."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)
        _create_message(conv_id, sender_id=SELLER_ID, is_read=False)

        resp = client.patch(f"/v1/conversations/{conv_id}/messages/read")
        assert resp.status_code == 204
        assert resp.content == b""


# ===========================================================================
# TestSchemaNoContactInfo
# ===========================================================================

class TestSchemaNoContactInfo:
    """Static schema inspection tests — confirm Pydantic schemas never
    accidentally expose contact/PII fields."""

    def test_message_out_schema_has_no_email_field(self):
        """MessageOut Pydantic model must not declare an 'email' field."""
        field_names = set(MessageOut.model_fields.keys())
        assert "email" not in field_names, (
            "MessageOut must not have an 'email' field — never expose contact info"
        )

    def test_message_out_schema_has_no_phone_field(self):
        """MessageOut Pydantic model must not declare a 'phone' field."""
        field_names = set(MessageOut.model_fields.keys())
        assert "phone" not in field_names, (
            "MessageOut must not have a 'phone' field — never expose contact info"
        )

    def test_message_out_schema_has_no_avatar_url_field(self):
        """MessageOut must not expose avatar_url."""
        field_names = set(MessageOut.model_fields.keys())
        assert "avatar_url" not in field_names

    def test_message_out_schema_has_no_full_name_field(self):
        """MessageOut must not expose full_name."""
        field_names = set(MessageOut.model_fields.keys())
        assert "full_name" not in field_names

    def test_conversation_out_schema_has_no_email_field(self):
        """ConversationOut Pydantic model must not declare an 'email' field."""
        field_names = set(ConversationOut.model_fields.keys())
        assert "email" not in field_names, (
            "ConversationOut must not have an 'email' field — never expose contact info"
        )

    def test_conversation_out_schema_has_no_phone_field(self):
        """ConversationOut Pydantic model must not declare a 'phone' field."""
        field_names = set(ConversationOut.model_fields.keys())
        assert "phone" not in field_names, (
            "ConversationOut must not have a 'phone' field — never expose contact info"
        )

    def test_message_out_schema_contains_expected_fields(self):
        """MessageOut must contain exactly the documented fields:
        id, conversation_id, sender_id, body, is_read, created_at."""
        expected_fields = {"id", "conversation_id", "sender_id", "body", "is_read", "created_at"}
        actual_fields = set(MessageOut.model_fields.keys())
        for field in expected_fields:
            assert field in actual_fields, f"Expected field '{field}' missing from MessageOut"

    def test_conversation_out_schema_contains_expected_fields(self):
        """ConversationOut must contain id, listing_id, buyer_id, seller_id, created_at."""
        expected_fields = {"id", "listing_id", "buyer_id", "seller_id", "created_at"}
        actual_fields = set(ConversationOut.model_fields.keys())
        for field in expected_fields:
            assert field in actual_fields, f"Expected field '{field}' missing from ConversationOut"


# ===========================================================================
# TestRedisRateLimitBoundary
# ===========================================================================

class TestRedisRateLimitBoundary:
    """Isolated rate-limit boundary tests using FakeRedis pre-seeded to specific
    counter values, without depending on the DB for conversation existence."""

    def test_rate_limit_key_format_is_chat_rate_conv_sender(
        self, client, auth_as_buyer, fake_redis
    ):
        """The rate-limit Redis key must be `chat_rate:{conv_id}:{sender_id}`.
        Confirm by asserting no other prefixed key is created on a valid send."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id, first_message_notified=True)

        with patch("app.services.chat_service.supabase_admin.fetch_user_email", new_callable=AsyncMock), \
             patch("app.services.chat_service.notification_service.send_new_message_email", new_callable=AsyncMock):
            client.post(
                f"/v1/conversations/{conv_id}/messages",
                json={"body": "key format test"},
            )

        # Only the canonical key must be present in the store
        canonical_key = f"chat_rate:{conv_id}:{BUYER_ID}"
        for key in fake_redis._store:
            if key.startswith("chat_rate:"):
                assert key == canonical_key, (
                    f"Unexpected rate-limit key '{key}'; expected '{canonical_key}'"
                )

    def test_rate_limit_counter_increments_on_each_send(
        self, client, auth_as_buyer, fake_redis
    ):
        """Each successful send must increment the rate counter by 1."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id, first_message_notified=True)
        rate_key = f"chat_rate:{conv_id}:{BUYER_ID}"

        with patch("app.services.chat_service.supabase_admin.fetch_user_email", new_callable=AsyncMock), \
             patch("app.services.chat_service.notification_service.send_new_message_email", new_callable=AsyncMock):
            client.post(f"/v1/conversations/{conv_id}/messages", json={"body": "msg 1"})
            client.post(f"/v1/conversations/{conv_id}/messages", json={"body": "msg 2"})
            client.post(f"/v1/conversations/{conv_id}/messages", json={"body": "msg 3"})

        counter = int(asyncio.run(fake_redis.get(rate_key)))
        assert counter == 3

    def test_rate_limit_blocks_exactly_at_101_not_100(
        self, client, auth_as_buyer, fake_redis
    ):
        """The spec says 100 messages/user/conversation/hour. The 101st must be
        blocked (counter at 100 when the next request arrives)."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)
        rate_key = f"chat_rate:{conv_id}:{BUYER_ID}"

        # Pre-seed at 100 (already used all allowed messages)
        asyncio.run(fake_redis.set(rate_key, 100))

        resp = client.post(
            f"/v1/conversations/{conv_id}/messages",
            json={"body": "101st message"},
        )
        assert resp.status_code == 429


# ===========================================================================
# TestConversationOrdering
# ===========================================================================

class TestConversationOrdering:
    def test_list_conversations_ordered_by_created_at_desc(
        self, client, auth_as_buyer
    ):
        """GET /conversations must return conversations ordered by created_at
        descending (most recent first)."""
        listing_id_1 = _create_listing(seller_id=SELLER_ID)
        listing_id_2 = _create_listing(seller_id=SELLER_ID)
        _create_conversation(listing_id_1, buyer_id=BUYER_ID, seller_id=SELLER_ID)
        _create_conversation(listing_id_2, buyer_id=BUYER_ID, seller_id=SELLER_ID)

        resp = client.get("/v1/conversations")
        assert resp.status_code == 200
        conversations = resp.json()

        if len(conversations) >= 2:
            # Verify descending order by created_at string comparison
            # ISO timestamps sort lexicographically correctly
            from datetime import datetime
            timestamps = [c["created_at"] for c in conversations]
            parsed = [
                datetime.fromisoformat(ts.replace("Z", "+00:00")) for ts in timestamps
            ]
            for i in range(len(parsed) - 1):
                assert parsed[i] >= parsed[i + 1], (
                    f"Conversations not in descending created_at order: "
                    f"{timestamps[i]} should be >= {timestamps[i + 1]}"
                )

    def test_get_messages_ordered_by_created_at_asc(
        self, client, auth_as_buyer
    ):
        """GET /conversations/{id}/messages must return messages ordered by
        created_at ascending (oldest first, for chronological chat rendering)."""
        listing_id = _create_listing(seller_id=SELLER_ID)
        conv_id = _create_conversation(listing_id)
        _create_message(conv_id, sender_id=BUYER_ID, body="First")
        _create_message(conv_id, sender_id=SELLER_ID, body="Second")
        _create_message(conv_id, sender_id=BUYER_ID, body="Third")

        resp = client.get(f"/v1/conversations/{conv_id}/messages")
        assert resp.status_code == 200
        messages = resp.json()

        if len(messages) >= 2:
            from datetime import datetime
            timestamps = [m["created_at"] for m in messages]
            parsed = [
                datetime.fromisoformat(ts.replace("Z", "+00:00")) for ts in timestamps
            ]
            for i in range(len(parsed) - 1):
                assert parsed[i] <= parsed[i + 1], (
                    f"Messages not in ascending created_at order: "
                    f"{timestamps[i]} should be <= {timestamps[i + 1]}"
                )


# ===========================================================================
# TestChatRouteRegistration
# ===========================================================================

class TestChatRouteRegistration:
    """Confirm chat routes are registered under /v1 on the FastAPI app."""

    def test_conversations_get_route_exists(self):
        paths = {route.path for route in app.routes}
        assert "/v1/conversations" in paths

    def test_conversations_post_route_exists(self):
        paths = {route.path for route in app.routes}
        assert "/v1/conversations" in paths

    def test_conversations_messages_get_route_exists(self):
        paths = {route.path for route in app.routes}
        assert "/v1/conversations/{conversation_id}/messages" in paths

    def test_conversations_messages_post_route_exists(self):
        paths = {route.path for route in app.routes}
        assert "/v1/conversations/{conversation_id}/messages" in paths

    def test_conversations_messages_read_patch_route_exists(self):
        paths = {route.path for route in app.routes}
        assert "/v1/conversations/{conversation_id}/messages/read" in paths

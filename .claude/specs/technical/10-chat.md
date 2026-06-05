# Spec 10: Chat

## Purpose

This spec covers the complete chat system for Study Material Exchange India — polling-based messaging between a buyer and a seller on a specific listing, Redis-backed rate limiting, Redis message cache, and a one-time email notification to the seller on the first message of each conversation. Chat is the primary pre-purchase communication channel: buyers contact sellers to negotiate price, confirm condition, and arrange the in-person meetup. The system is intentionally simple: no WebSockets, no presence indicators, no read receipts visible to the sender, no contact-info sharing. Conversations are permanently archived when a listing is deleted — they are never hard-deleted because they serve as dispute history. One conversation exists per buyer per listing (`UNIQUE(listing_id, buyer_id)`). The buyer opens a conversation; both parties send and receive messages within it.

---

## Depends on

- **Spec 06 — Schema:** `conversations`, `messages`, `public.users`, `listings` tables
- **Spec 07 — Auth:** `verify_token` dependency, `user["sub"]` as sender UUID

---

## Scope

**In scope:**
- `GET /conversations` — list caller's conversations (as buyer or seller)
- `POST /conversations` — create or return existing conversation for a listing
- `GET /conversations/{id}/messages` — fetch messages, 4-second polling
- `POST /conversations/{id}/messages` — send a message
- `PATCH /conversations/{id}/messages/read` — mark all messages in a conversation as read
- Redis rate limiting: 100 messages/user/conversation/hour
- Redis message cache: 30-second TTL per conversation
- Email on first message: one email to seller when `first_message_notified = FALSE`, then set to `TRUE`
- Frontend: `/chat/[id]` client page with TanStack Query polling
- Frontend: conversation list in dashboard

**Out of scope:**
- WebSockets — not in v1 and explicitly listed in "What NOT to build"
- Read receipts visible to the sender (is_read is set server-side only)
- Push/in-app notifications — no in-app notifications in v1
- Contact info in messages — never returned in any response
- Message deletion or editing
- Conversation deletion — archive only
- File or image attachments

---

## Data model

From SCHEMA.md — no schema changes needed for this spec.

### conversations

```sql
id          UUID PRIMARY KEY DEFAULT gen_random_uuid()
listing_id  UUID REFERENCES listings(id) ON DELETE SET NULL   -- NULL after listing deleted; row preserved for dispute history
buyer_id    UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE
seller_id   UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE
first_message_notified  BOOLEAN NOT NULL DEFAULT FALSE
created_at  TIMESTAMPTZ NOT NULL DEFAULT now()

UNIQUE(listing_id, buyer_id)
```

One conversation per buyer per listing. `seller_id` is denormalised here for query efficiency — it matches `listings.seller_id` at creation time. `listing_id` is nullable so that the conversation row survives if the listing is deleted (`ON DELETE SET NULL`). See Spec 06 for the full schema definition.

### messages

```sql
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
conversation_id  UUID REFERENCES conversations(id) ON DELETE CASCADE
sender_id        UUID REFERENCES public.users(id) ON DELETE CASCADE
body             TEXT NOT NULL
is_read          BOOLEAN DEFAULT FALSE
created_at       TIMESTAMPTZ DEFAULT now()
```

---

## Redis keys

From CLAUDE.md canonical constants:

```
chat_rate:{conversation_id}:{sender_id}    integer, TTL 1 hour  — rate limit counter
chat:{conversation_id}                     cached messages JSON, TTL 30s
```

---

## Backend — conversation service

```python
# backend/app/services/chat_service.py
import json
import logging
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from fastapi import HTTPException
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.listing import Listing
from app.core.redis import redis
from app.core import supabase_admin
from app.services import notification_service

logger = logging.getLogger(__name__)

RATE_LIMIT = 100       # messages per hour per user per conversation
CACHE_TTL  = 30        # seconds


async def get_or_create_conversation(
    db: AsyncSession,
    listing_id: UUID,
    buyer_id: str
) -> Conversation:
    result = await db.execute(
        select(Conversation).where(
            Conversation.listing_id == listing_id,
            Conversation.buyer_id == buyer_id
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    listing = await db.get(Listing, listing_id)
    if not listing or not listing.is_available:
        raise HTTPException(404, "Listing not found.")
    if str(listing.seller_id) == buyer_id:
        raise HTTPException(403, "You cannot message yourself about your own listing.")

    conversation = Conversation(
        listing_id=listing_id,
        buyer_id=buyer_id,
        seller_id=listing.seller_id
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    logger.info(
        "Conversation created: conversation=%s listing=%s buyer=%s seller=%s",
        conversation.id, listing_id, buyer_id, listing.seller_id
    )
    return conversation


async def get_conversations(db: AsyncSession, user_id: str) -> list[Conversation]:
    result = await db.execute(
        select(Conversation).where(
            (Conversation.buyer_id == user_id) | (Conversation.seller_id == user_id)
        ).order_by(Conversation.created_at.desc())
    )
    return result.scalars().all()


async def get_messages(
    db: AsyncSession,
    conversation_id: UUID,
    user_id: str
) -> list[Message]:
    await _assert_participant(db, conversation_id, user_id)

    cache_key = f"chat:{conversation_id}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()

    serialised = [
        {
            "id": str(m.id),
            "conversation_id": str(m.conversation_id),
            "sender_id": str(m.sender_id),
            "body": m.body,
            "is_read": m.is_read,
            "created_at": m.created_at.isoformat()
        }
        for m in messages
    ]
    await redis.set(cache_key, json.dumps(serialised), ex=CACHE_TTL)
    return serialised


async def send_message(
    db: AsyncSession,
    conversation_id: UUID,
    sender_id: str,
    body: str
) -> Message:
    conversation = await _assert_participant(db, conversation_id, sender_id)

    # Rate limit check — 100 messages/user/conversation/hour
    rate_key = f"chat_rate:{conversation_id}:{sender_id}"
    count = await redis.get(rate_key)
    if count and int(count) >= RATE_LIMIT:
        raise HTTPException(429, "Message rate limit reached. Try again later.")

    message = Message(
        conversation_id=conversation_id,
        sender_id=sender_id,
        body=body
    )
    db.add(message)

    # Increment rate counter
    pipe = redis.pipeline()
    pipe.incr(rate_key)
    pipe.expire(rate_key, 3600)
    await pipe.execute()

    # Invalidate message cache so next poll fetches fresh
    await redis.delete(f"chat:{conversation_id}")

    # First-message email to seller
    if not conversation.first_message_notified:
        await db.execute(
            update(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.first_message_notified == False
            )
            .values(first_message_notified=True)
        )
        seller_email = await supabase_admin.fetch_user_email(str(conversation.seller_id))
        if seller_email:
            await notification_service.send_new_message_email(conversation, seller_email)
        else:
            logger.warning(
                "Could not resolve seller email for conversation=%s", conversation_id
            )

    await db.commit()
    await db.refresh(message)
    logger.info(
        "Message sent: message=%s conversation=%s sender=%s",
        message.id, conversation_id, sender_id
    )
    return message


async def mark_read(
    db: AsyncSession,
    conversation_id: UUID,
    user_id: str
) -> None:
    await _assert_participant(db, conversation_id, user_id)
    await db.execute(
        update(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.sender_id != user_id,
            Message.is_read == False
        )
        .values(is_read=True)
    )
    await db.commit()
    await redis.delete(f"chat:{conversation_id}")


async def _assert_participant(
    db: AsyncSession,
    conversation_id: UUID,
    user_id: str
) -> Conversation:
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(404, "Conversation not found.")
    if str(conversation.buyer_id) != user_id and str(conversation.seller_id) != user_id:
        raise HTTPException(403, "Not a participant in this conversation.")
    return conversation
```

---

## Backend — router

```python
# backend/app/routers/chat.py
import logging
from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import verify_token
from app.schemas.chat import (
    ConversationCreate,
    ConversationOut,
    MessageCreate,
    MessageOut
)
from app.services import chat_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token)
):
    return await chat_service.get_conversations(db, user["sub"])


@router.post("/conversations", response_model=ConversationOut)
async def create_conversation(
    data: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token)
):
    return await chat_service.get_or_create_conversation(db, data.listing_id, user["sub"])


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
async def get_messages(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token)
):
    return await chat_service.get_messages(db, conversation_id, user["sub"])


@router.post("/conversations/{conversation_id}/messages", response_model=MessageOut)
async def send_message(
    conversation_id: UUID,
    data: MessageCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token)
):
    return await chat_service.send_message(db, conversation_id, user["sub"], data.body)


@router.patch("/conversations/{conversation_id}/messages/read", status_code=204)
async def mark_read(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token)
):
    await chat_service.mark_read(db, conversation_id, user["sub"])
```

---

## Backend — Pydantic schemas

```python
# backend/app/schemas/chat.py
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, field_validator


class ConversationCreate(BaseModel):
    listing_id: UUID


class ConversationOut(BaseModel):
    id: UUID
    listing_id: UUID | None   # nullable — NULL after listing deleted
    buyer_id: UUID
    seller_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    body: str

    @field_validator("body")
    @classmethod
    def body_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message body cannot be empty.")
        if len(v) > 2000:
            raise ValueError("Message too long (max 2000 characters).")
        return v


class MessageOut(BaseModel):
    id: UUID
    conversation_id: UUID
    sender_id: UUID
    body: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}
```

---

## Backend — SQLAlchemy models

`Conversation` and `Message` models are already fully defined in **Spec 06 — Schema** at `backend/app/models/conversation.py` and `backend/app/models/message.py`. Do not redefine or overwrite them. The canonical definitions use `Column()` style and the correct FK semantics:

- `conversations.listing_id` → `ForeignKey("listings.id", ondelete="SET NULL")`, nullable
- `messages.conversation_id` → `ForeignKey("conversations.id", ondelete="CASCADE")`, not null

Import them as-is:

```python
from app.models.conversation import Conversation
from app.models.message import Message
```

---

## Backend — email notification

```python
# backend/app/services/notification_service.py  (add to existing file)
async def send_new_message_email(conversation, seller_email: str) -> None:
    try:
        resend.Emails.send({
            "from": "NextPrep <no-reply@yourdomain.com>",
            "to": [seller_email],
            "subject": "Someone is interested in your listing",
            "html": (
                "<p>A buyer has sent you a message about your listing on NextPrep. "
                "Log in to reply.</p>"
            )
        })
        logger.info("First-message email sent: conversation=%s", conversation.id)
    except Exception as e:
        logger.error(
            "Failed to send first-message email: conversation=%s error=%s",
            conversation.id, str(e)
        )
```

Email is fire-and-forget. A failure must not block the message from being stored. The `first_message_notified` flag is set to `TRUE` before the email attempt — if the send fails, the flag stays `TRUE` and the email is not retried. One notification is sufficient; a missed email is preferable to spamming the seller.

---

## Backend — register router

```python
# backend/app/main.py  (add alongside other routers)
from app.routers.chat import router as chat_router
app.include_router(chat_router, prefix="/v1")
```

---

## Frontend — chat page

```jsx
// frontend/app/chat/[id]/page.jsx
'use client'
import { useEffect, useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'

export default function ChatPage({ params }) {
  const conversationId = params.id
  const queryClient = useQueryClient()
  const [body, setBody] = useState('')
  const bottomRef = useRef(null)

  const { data: messages = [] } = useQuery({
    queryKey: ['messages', conversationId],
    queryFn: () => api.get(`/conversations/${conversationId}/messages`).then(r => r.data),
    refetchInterval: 4000
  })

  const send = useMutation({
    mutationFn: () =>
      api.post(`/conversations/${conversationId}/messages`, { body }),
    onSuccess: () => {
      setBody('')
      queryClient.invalidateQueries({ queryKey: ['messages', conversationId] })
    }
  })

  // Mark messages as read when page is open
  useEffect(() => {
    api.patch(`/conversations/${conversationId}/messages/read`).catch(() => {})
  }, [conversationId, messages])

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="flex flex-col h-screen max-w-2xl mx-auto">
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((m) => (
          <div key={m.id} className="rounded p-2 bg-muted text-sm">
            <span className="font-medium text-xs text-muted-foreground block mb-1">
              {m.sender_id}
            </span>
            {m.body}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="border-t p-3 flex gap-2">
        <input
          className="flex-1 border rounded px-3 py-2 text-sm"
          placeholder="Type a message..."
          value={body}
          onChange={e => setBody(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey && body.trim()) {
              e.preventDefault()
              send.mutate()
            }
          }}
          maxLength={2000}
        />
        <button
          onClick={() => send.mutate()}
          disabled={!body.trim() || send.isPending}
          className="px-4 py-2 rounded bg-primary text-primary-foreground text-sm disabled:opacity-50"
        >
          Send
        </button>
      </div>

      {send.isError && (
        <p className="text-red-500 text-xs px-3 pb-2">
          {send.error?.response?.data?.detail ?? 'Failed to send message.'}
        </p>
      )}
    </div>
  )
}
```

---

## Frontend — conversation list (dashboard)

```jsx
// frontend/components/chat/ConversationList.jsx
'use client'
import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import api from '@/lib/api'

export default function ConversationList() {
  const { data: conversations = [], isLoading } = useQuery({
    queryKey: ['conversations'],
    queryFn: () => api.get('/conversations').then(r => r.data)
  })

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading chats...</p>
  if (!conversations.length) return <p className="text-sm text-muted-foreground">No conversations yet.</p>

  return (
    <ul className="space-y-2">
      {conversations.map((c) => (
        <li key={c.id}>
          <Link
            href={`/chat/${c.id}`}
            className="block border rounded p-3 hover:bg-muted transition-colors text-sm"
          >
            <span className="text-xs text-muted-foreground">Listing {c.listing_id}</span>
          </Link>
        </li>
      ))}
    </ul>
  )
}
```

---

## Frontend — start a conversation from listing page

The listing detail page (`/listings/[id]`) embeds a "Message Seller" button. Clicking it calls `POST /conversations` then redirects to `/chat/{id}`.

```jsx
// frontend/components/listings/MessageSellerButton.jsx
'use client'
import { useRouter } from 'next/navigation'
import { useMutation } from '@tanstack/react-query'
import api from '@/lib/api'

export default function MessageSellerButton({ listingId }) {
  const router = useRouter()

  const open = useMutation({
    mutationFn: () => api.post('/conversations', { listing_id: listingId }),
    onSuccess: (res) => router.push(`/chat/${res.data.id}`)
  })

  return (
    <button
      onClick={() => open.mutate()}
      disabled={open.isPending}
      className="w-full border rounded px-4 py-2 text-sm disabled:opacity-50"
    >
      {open.isPending ? 'Opening chat...' : 'Message Seller'}
    </button>
  )
}
```

---

## Alembic migration

No new migration is needed for this spec. The `conversations` and `messages` tables — including all columns, FKs, constraints, and indexes — are created by Spec 06's migration `alembic/versions/0001_initial_schema.py`. Running a second migration that re-creates these tables would fail with `DuplicateTable`.

The chat service and router implement application logic only; they do not require any schema changes.

---

## Files to create

```
backend/app/schemas/chat.py
backend/app/services/chat_service.py
backend/app/routers/chat.py
frontend/app/chat/[id]/page.jsx
frontend/components/chat/ConversationList.jsx
frontend/components/listings/MessageSellerButton.jsx
```

`backend/app/models/conversation.py` and `backend/app/models/message.py` already exist from Spec 06 — do not create or overwrite them. No Alembic migration file is needed — see "Alembic migration" section.

---

## Files to modify

```
backend/app/main.py
  — import and register chat router

backend/app/services/notification_service.py
  — add send_new_message_email function

frontend/app/listings/[id]/page.jsx
  — embed MessageSellerButton (client boundary, seller cannot see it on their own listing)

frontend/app/dashboard/page.jsx (or equivalent)
  — embed ConversationList component
```

---

## New dependencies

No new dependencies. `redis`, `resend`, and `sqlalchemy` are already required by prior specs.

---

## Security considerations

The following rules from CLAUDE.md apply directly to this feature:

- **Rule 1** — Never expose seller contact info in any API response. Chat message bodies are returned as-is — the API does not scan or redact them, but contact info in message bodies is a content moderation concern handled via the Supabase dashboard. The API must never inject contact info into responses.
- **Rule 4** — Supabase session in httpOnly cookies — all chat endpoints are protected via `verify_token`.
- **Rule 5** — Ownership validated: `_assert_participant` checks that the caller is buyer or seller before any read or write. Non-participants receive 403.
- **Rule 7** — Parameterized queries only. All DB queries go through SQLAlchemy ORM.
- **Rule 9** — `SUPABASE_SERVICE_ROLE_KEY` used in `fetch_user_email` which is called from `chat_service`. This is called inside a request handler context (not a background job). The service role key is used only server-side in FastAPI — it is never sent to the frontend and never appears in any response.

Additional:
- Rate limit enforced in Redis before DB write — prevents abuse without DB round-trips.
- `first_message_notified` is updated atomically via a conditional `UPDATE ... WHERE first_message_notified = FALSE` to avoid double emails if two concurrent messages race on a new conversation.
- Redis cache is invalidated on every `send_message` and `mark_read` — stale data window is at most 30 seconds on get but zero on write.

---

## Definition of done

- [ ] `POST /conversations` with a valid `listing_id` creates a conversation row and returns it; second call with the same `listing_id` and same buyer returns the existing row (idempotent)
- [ ] `POST /conversations` where caller is the listing's seller returns 403 "You cannot message yourself about your own listing."
- [ ] `GET /conversations` returns only conversations where the caller is buyer or seller — other users' conversations are not returned
- [ ] `GET /conversations/{id}/messages` returns 403 for a non-participant
- [ ] `POST /conversations/{id}/messages` sends a message and returns the new message object
- [ ] `POST /conversations/{id}/messages` with an empty or whitespace-only body returns 422
- [ ] `POST /conversations/{id}/messages` with a body over 2000 characters returns 422
- [ ] Rate limit: 101st message in the same conversation within an hour returns 429; counter resets after TTL (verify with Redis key `chat_rate:{id}:{sender_id}`)
- [ ] First message in a conversation triggers a seller email; `first_message_notified` is set to `TRUE` in DB; second message does not trigger another email
- [ ] Seller email is resolved from `auth.users` via service role — no `seller_email` column on `conversations` or `messages`
- [ ] `PATCH /conversations/{id}/messages/read` marks all messages sent by the other party as `is_read = TRUE`; caller's own messages are not affected
- [ ] Redis cache key `chat:{conversation_id}` is present after first GET and absent after a send or mark-read (TTL or explicit delete)
- [ ] `/chat/[id]` page polls every 4 seconds (verify in browser network tab — requests repeat on 4-second interval)
- [ ] Sending a message via Enter key (without Shift) submits the form
- [ ] Message Seller button on listing page creates a conversation and redirects to `/chat/{id}`
- [ ] ConversationList in dashboard renders all buyer and seller conversations for the logged-in user
- [ ] `MessageOut` schema definition contains no `email`, `phone`, `avatar_url`, or `full_name` fields — confirm by reading `backend/app/schemas/chat.py`
- [ ] `alembic upgrade head` runs cleanly against a DB that already has `conversations` and `messages` tables from Spec 06's migration — no errors, no new tables created by this spec

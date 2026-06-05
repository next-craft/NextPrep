# Spec 06: Schema

## Purpose

This spec documents every table, column, constraint, index, and trigger in the Study Material Exchange India database. The schema is the single source of truth for data shape, integrity rules, and relational guarantees. It must be created once via Alembic and the Supabase trigger, and never modified by raw SQL directly. Every entity — users, listings, conversations, messages, transactions, ratings — is covered here in full, including column types, default values, CHECK constraints, UNIQUE constraints, indexes, and the one Postgres trigger that auto-creates a public profile on Google OAuth signup. This spec exists to give both developers a complete, unambiguous reference before any backend model or migration is written.

---

## Depends on

- Spec 01 (Overview) — product decisions that drive schema shape (meetup-only, India-only, unified search stream, no shipping, single account)
- Spec 02 (User Flows) — buyer/seller flows that determine which columns must exist and what states they track
- `.claude/docs/AUTH.md` — Supabase trigger, `public.users` creation
- `.claude/docs/PAYMENT.md` — transaction statuses, passkey lifecycle, partial unique index
- `.claude/docs/SCHEMA.md` — canonical column definitions and debug queries (this spec expands and cross-references that file)

---

## Scope

**In scope:**
- All six tables: `public.users`, `listings`, `conversations`, `messages`, `transactions`, `seller_ratings`
- All column types, nullability, defaults, and CHECK constraints
- All UNIQUE constraints and UNIQUE indexes
- The partial unique index on `transactions`
- All foreign keys and cascade rules
- The `handle_new_user` Postgres trigger
- SQLAlchemy 2.0 async model classes (one per table)
- Alembic migration that creates every table, index, and constraint
- The Supabase dashboard SQL for the trigger (not in Alembic — runs once manually)
- Debug queries for integrity verification

**Out of scope:**
- Supabase Auth's `auth.users` table (managed by Supabase, not editable)
- Row Level Security (RLS) — backend enforces ownership in application code, not DB policy
- Full-text search indexes — search uses WHERE + ILIKE only, no tsvector
- Any table not listed above (no admin, no feature flags, no audit log table)

---

## Tables

### public.users

Mirror of `auth.users` for the application. Auto-created by trigger on Google OAuth signup. Never created directly by application code.

```sql
CREATE TABLE public.users (
    id            UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name     TEXT NOT NULL,
    city          TEXT,
    avatar_url    TEXT,
    is_verified   BOOLEAN NOT NULL DEFAULT FALSE,
    seller_rating NUMERIC(3,2),
    total_sales   INTEGER NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Column notes:**
- `id` — same UUID as `auth.users.id`. Not generated here — provided by trigger.
- `full_name` — pulled from `raw_user_meta_data->>'full_name'` at signup. Falls back to `'User'`.
- `city` — nullable. Set by user in profile edit. Used as default city filter in listing creation.
- `avatar_url` — Cloudinary URL or Google profile photo URL from OAuth.
- `is_verified` — `TRUE` if Google verified the email at OAuth time. Not Aadhaar, not manual OTP.
- `seller_rating` — `NUMERIC(3,2)`, e.g. `4.75`. NULL until first rating received. Updated by application after each `seller_ratings` insert.
- `total_sales` — incremented by application after each `transactions` row reaches `released` status.
- No `email`, no `password_hash`, no `phone` — Supabase Auth owns identity. Email available via `payload["email"]` in JWT.

---

### listings

Core entity. One row per item a seller puts up for sale.

```sql
CREATE TABLE listings (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seller_id               UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    title                   TEXT NOT NULL,
    description             TEXT,
    exam_category           TEXT NOT NULL,
    subject                 TEXT,
    listing_type            TEXT NOT NULL
                              CHECK (listing_type IN ('BOOK', 'NOTES', 'MODULE', 'BUNDLE')),
    condition               TEXT NOT NULL
                              CHECK (condition IN ('A', 'B', 'C')),
    asking_price            INTEGER NOT NULL CHECK (asking_price > 0),
    original_price          INTEGER CHECK (original_price > 0),
    city                    TEXT NOT NULL,
    images                  TEXT[],
    is_available            BOOLEAN NOT NULL DEFAULT TRUE,
    sold_at                 TIMESTAMPTZ DEFAULT NULL,
    passkey_hash            TEXT NOT NULL,
    passkey_invalidated     BOOLEAN NOT NULL DEFAULT FALSE,
    passkey_invalidated_at  TIMESTAMPTZ DEFAULT NULL,
    views                   INTEGER NOT NULL DEFAULT 0,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at              TIMESTAMPTZ DEFAULT NULL,

    CONSTRAINT no_available_sold_listing
        CHECK (NOT (is_available = TRUE AND (sold_at IS NOT NULL OR deleted_at IS NOT NULL))),
    CONSTRAINT sold_xor_deleted
        CHECK (NOT (sold_at IS NOT NULL AND deleted_at IS NOT NULL))
);
```

**Column notes:**
- `exam_category` — enforced by application against canonical list (see CLAUDE.md). No DB CHECK — list is long and may grow. Application validates on write.
- `listing_type` CHECK enforced at DB level — protects against any code path including direct writes.
- `condition` — `A` (like new), `B` (good), `C` (acceptable). CHECK at DB level.
- `asking_price` — whole rupees only, no paise, no decimals. `INTEGER NOT NULL`.
- `original_price` — optional, whole rupees. Used to show discount percentage in UI.
- `subject` — free text. No DB constraint. UI shows popular dropdown defaults + "Other". Enables flexible search.
- `images` — `TEXT[]`, Cloudinary URLs. Max 5 enforced by application. No DB array length constraint.
- `is_available`, `sold_at`, `deleted_at` — full listing state model:

  | `is_available` | `sold_at` | `deleted_at` | State |
  |---|---|---|---|
  | `TRUE` | `NULL` | `NULL` | **active** — visible in search, for sale |
  | `FALSE` | `NULL` | `NULL` | **paused** (seller) or **suspended** (moderation) |
  | `FALSE` | `<timestamp>` | `NULL` | **sold** — payment confirmed via webhook |
  | `FALSE` | `NULL` | `<timestamp>` | **deleted** — seller soft-deleted |
  | Any other combination | — | — | impossible — blocked by constraints |

  `sold_xor_deleted` constraint prevents `sold_at` and `deleted_at` from both being non-NULL. A deleted listing is never a sold listing. `total_sales` is incremented only when a transaction reaches `released` — never on deletion.

- `deleted_at` — set by `DELETE /v1/listings/{id}`. `sold_at` stays NULL. Conversations survive via `ON DELETE SET NULL` on their FK. Financial records in `transactions` survive via `ON DELETE SET NULL` on their FK.
- `passkey_hash` — HMAC-SHA256 of `passkey + listing_id` using `PASSKEY_HMAC_SECRET`. Plaintext never stored.
- `passkey_invalidated` — set `TRUE` atomically when a payment completes (webhook Step 8). Prevents reuse.
- `views` — incremented on each `GET /listings/{id}` call. No auth required.

**Indexes:**

```sql
-- Listing search: filter by availability + category + type
CREATE INDEX idx_listings_available ON listings (is_available, exam_category, listing_type);

-- Seller dashboard: all listings by a seller
CREATE INDEX idx_listings_seller_id ON listings (seller_id);

-- Sort by newest first (default ordering); Alembic: use sa.text('created_at DESC') in column list
CREATE INDEX idx_listings_created_at ON listings (created_at DESC);
```

---

### conversations

One conversation per buyer per listing. Survives listing deletion (archived, not deleted).

```sql
CREATE TABLE conversations (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id              UUID REFERENCES listings(id) ON DELETE SET NULL,
    buyer_id                UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    seller_id               UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    first_message_notified  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (listing_id, buyer_id)
);
```

**Column notes:**
- `listing_id` uses `ON DELETE SET NULL` — conversation row survives listing deletion. `listing_id` becomes NULL. This is intentional: dispute history and chat history must be preserved.
- `buyer_id` and `seller_id` — both denormalised here. Avoids joining to the listing to find the participants.
- `first_message_notified` — `TRUE` after the seller email notification for the first message has been sent. Application checks this flag before sending email; only one email per conversation.
- `UNIQUE(listing_id, buyer_id)` — prevents a buyer opening two parallel conversations on the same listing.

**Indexes:**

```sql
-- Fetch all conversations for a user (inbox)
CREATE INDEX idx_conversations_buyer_id ON conversations (buyer_id);
CREATE INDEX idx_conversations_seller_id ON conversations (seller_id);
```

---

### messages

Individual messages inside a conversation.

```sql
CREATE TABLE messages (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id  UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender_id        UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    body             TEXT NOT NULL,
    is_read          BOOLEAN NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Column notes:**
- `body` — free text. Application enforces max length (2000 chars) at API boundary. No DB constraint.
- `is_read` — set `TRUE` by `PATCH /conversations/{id}/messages/read`. Marks all unread messages in a conversation as read for the calling user.

  A single `BOOLEAN` is sufficient here because every conversation has exactly two participants (buyer and seller). When a message is sent, the sender already knows its content — only the other party needs a read flag. The application identifies "which party hasn't read this" by comparing `sender_id` to the calling user's ID: messages where `sender_id != current_user` and `is_read = FALSE` are unread for that user. No per-recipient read table is needed. This model breaks only if a conversation has more than two participants — group chat is out of scope for v1 and is explicitly listed in "What NOT to build."

- No `recipient_id` — the other participant is implied by `sender_id` vs `conversations.buyer_id`/`seller_id`. This avoids a redundant column that would have to be kept in sync.

**Indexes:**

```sql
-- Fetch messages in a conversation, newest last
CREATE INDEX idx_messages_conversation_id ON messages (conversation_id, created_at ASC);
```

---

### transactions

One row per payment initiation. Created when buyer enters correct passkey.

```sql
CREATE TABLE transactions (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id                  UUID REFERENCES listings(id) ON DELETE SET NULL,
    buyer_id                    UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    seller_id                   UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    amount_rupees               INTEGER NOT NULL CHECK (amount_rupees > 0),
    platform_fee_rupees         INTEGER NOT NULL DEFAULT 0,
    seller_payout_rupees        INTEGER NOT NULL CHECK (seller_payout_rupees >= 0),
    razorpay_payment_link_id    TEXT UNIQUE,
    razorpay_payment_link_url   TEXT,
    razorpay_payment_id         TEXT UNIQUE,
    status                      TEXT NOT NULL DEFAULT 'initiated'
                                  CHECK (status IN ('initiated', 'released', 'cancelled')),
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    released_at                 TIMESTAMPTZ,
    refunded_at                 TIMESTAMPTZ
);
```

**Column notes:**
- `listing_id` — `ON DELETE SET NULL` for the same reason as conversations: financial records must survive listing deletion.
- `amount_rupees` — copied from `listing.asking_price` at initiation time. Immutable after creation.
- `platform_fee_rupees` — `0` in v1. Column exists so fee can be introduced without schema change.
- `seller_payout_rupees` — `amount_rupees - platform_fee_rupees`. In v1 equals `amount_rupees`.
- `razorpay_payment_link_id` — UNIQUE. Used to match incoming webhooks to transactions.
- `razorpay_payment_id` — UNIQUE. Set by webhook handler on payment confirmation.
- `status` values: `initiated` (link generated, awaiting payment), `released` (payment confirmed, seller paid), `cancelled` (abandoned or concurrent loser). No other values.
- `released_at` — set in webhook Step 7 when status transitions to `released`.
- `refunded_at` — set when a refund is issued (late webhook or concurrent payment loser).

**Partial unique index — prevents payment link spam:**

```sql
CREATE UNIQUE INDEX one_active_transaction_per_buyer_listing
    ON transactions (listing_id, buyer_id)
    WHERE status = 'initiated';
```

Same buyer cannot generate a second payment link for the same listing while one is already `initiated`. Once `released` or `cancelled`, a new transaction can be created.

**Indexes:**

```sql
-- APScheduler query: find stale initiated transactions
CREATE INDEX idx_transactions_status_created ON transactions (status, created_at)
    WHERE status = 'initiated';

-- Buyer's transaction history
CREATE INDEX idx_transactions_buyer_id ON transactions (buyer_id);

-- Seller's transaction history
CREATE INDEX idx_transactions_seller_id ON transactions (seller_id);
```

---

### seller_ratings

Buyer rates the seller after a completed transaction. One rating per transaction per rater.

```sql
CREATE TABLE seller_ratings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id  UUID NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    rated_by        UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    seller_id       UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    rating          INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (transaction_id, rated_by)
);
```

**Column notes:**
- `UNIQUE(transaction_id, rated_by)` — prevents duplicate ratings at DB level, no application guard needed.
- `seller_id` — denormalised for efficient `AVG(rating)` queries without joining to transactions.
- After insert, application recomputes `public.users.seller_rating = AVG(rating) WHERE seller_id = <id>` and updates the users row.

---

## Trigger — auto-create public.users on signup

This SQL runs once in the Supabase dashboard. It is NOT in Alembic — Alembic cannot write to `auth` schema.

```sql
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.users (id, full_name, avatar_url, is_verified)
    VALUES (
        NEW.id,
        COALESCE(NEW.raw_user_meta_data->>'full_name', 'User'),
        NEW.raw_user_meta_data->>'avatar_url',
        COALESCE((NEW.raw_user_meta_data->>'email_verified')::boolean, FALSE)
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();
```

- `SECURITY DEFINER` — runs with the function owner's privileges. Required to write to `public.users` from the `auth` schema trigger context.
- If trigger fails, `auth.users` row still exists but `public.users` row is missing. Use the debug query below to detect this.

---

## SQLAlchemy Models

All models live in `backend/app/models/`. One file per table.

```python
# backend/app/models/user.py
from sqlalchemy import Column, String, Boolean, Integer, TIMESTAMP, Numeric, text
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "public"}

    id            = Column(UUID(as_uuid=True), primary_key=True)
    full_name     = Column(String, nullable=False)
    city          = Column(String)
    avatar_url    = Column(String)
    is_verified   = Column(Boolean, nullable=False, default=False)
    seller_rating = Column(Numeric(3, 2))
    total_sales   = Column(Integer, nullable=False, default=0)
    created_at    = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
```

```python
# backend/app/models/listing.py
from sqlalchemy import Column, String, Boolean, Integer, TIMESTAMP, ARRAY, CheckConstraint, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

class Listing(Base):
    __tablename__ = "listings"

    id                     = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    seller_id              = Column(UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    title                  = Column(String, nullable=False)
    description            = Column(String)
    exam_category          = Column(String, nullable=False)
    subject                = Column(String)
    listing_type           = Column(String, nullable=False)
    condition              = Column(String, nullable=False)
    asking_price           = Column(Integer, nullable=False)
    original_price         = Column(Integer)
    city                   = Column(String, nullable=False)
    images                 = Column(ARRAY(String))
    is_available           = Column(Boolean, nullable=False, default=True)
    sold_at                = Column(TIMESTAMP(timezone=True))
    passkey_hash           = Column(String, nullable=False)
    passkey_invalidated    = Column(Boolean, nullable=False, default=False)
    passkey_invalidated_at = Column(TIMESTAMP(timezone=True))
    views                  = Column(Integer, nullable=False, default=0)
    created_at             = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    deleted_at             = Column(TIMESTAMP(timezone=True))

    __table_args__ = (
        CheckConstraint("listing_type IN ('BOOK', 'NOTES', 'MODULE', 'BUNDLE')", name="ck_listing_type"),
        CheckConstraint("condition IN ('A', 'B', 'C')", name="ck_condition"),
        CheckConstraint("asking_price > 0", name="ck_asking_price_positive"),
        CheckConstraint("NOT (is_available = TRUE AND (sold_at IS NOT NULL OR deleted_at IS NOT NULL))", name="no_available_sold_listing"),
        CheckConstraint("NOT (sold_at IS NOT NULL AND deleted_at IS NOT NULL)", name="sold_xor_deleted"),
    )
```

```python
# backend/app/models/conversation.py
from sqlalchemy import Column, Boolean, TIMESTAMP, UniqueConstraint, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

class Conversation(Base):
    __tablename__ = "conversations"

    id                     = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    listing_id             = Column(UUID(as_uuid=True), ForeignKey("listings.id", ondelete="SET NULL"))
    buyer_id               = Column(UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    seller_id              = Column(UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    first_message_notified = Column(Boolean, nullable=False, default=False)
    created_at             = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (
        UniqueConstraint("listing_id", "buyer_id", name="uq_conversation_listing_buyer"),
    )
```

```python
# backend/app/models/message.py
from sqlalchemy import Column, String, Boolean, TIMESTAMP, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

class Message(Base):
    __tablename__ = "messages"

    id              = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    sender_id       = Column(UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    body            = Column(String, nullable=False)
    is_read         = Column(Boolean, nullable=False, default=False)
    created_at      = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
```

```python
# backend/app/models/transaction.py
from sqlalchemy import Column, String, Integer, TIMESTAMP, CheckConstraint, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

class Transaction(Base):
    __tablename__ = "transactions"

    id                       = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    listing_id               = Column(UUID(as_uuid=True), ForeignKey("listings.id", ondelete="SET NULL"))
    buyer_id                 = Column(UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    seller_id                = Column(UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    amount_rupees            = Column(Integer, nullable=False)
    platform_fee_rupees      = Column(Integer, nullable=False, default=0)
    seller_payout_rupees     = Column(Integer, nullable=False)
    razorpay_payment_link_id = Column(String, unique=True)
    razorpay_payment_link_url= Column(String)
    razorpay_payment_id      = Column(String, unique=True)
    status                   = Column(String, nullable=False, default="initiated")
    created_at               = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    released_at              = Column(TIMESTAMP(timezone=True))
    refunded_at              = Column(TIMESTAMP(timezone=True))

    __table_args__ = (
        CheckConstraint("status IN ('initiated', 'released', 'cancelled')", name="ck_transaction_status"),
        CheckConstraint("amount_rupees > 0", name="ck_amount_positive"),
        CheckConstraint("seller_payout_rupees >= 0", name="ck_payout_nonnegative"),
    )
```

```python
# backend/app/models/seller_rating.py
from sqlalchemy import Column, Integer, TIMESTAMP, UniqueConstraint, CheckConstraint, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

class SellerRating(Base):
    __tablename__ = "seller_ratings"

    id             = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False)
    rated_by       = Column(UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    seller_id      = Column(UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    rating         = Column(Integer, nullable=False)
    created_at     = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (
        UniqueConstraint("transaction_id", "rated_by", name="uq_rating_transaction_rater"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_rating_range"),
    )
```

---

## Alembic Migration

```python
# alembic/versions/0001_initial_schema.py
"""Initial schema

Revision ID: 0001
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY

revision = '0001'
down_revision = None

def upgrade():
    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('full_name', sa.String(), nullable=False),
        sa.Column('city', sa.String()),
        sa.Column('avatar_url', sa.String()),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('seller_rating', sa.Numeric(3, 2)),
        sa.Column('total_sales', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema='public'
    )

    op.create_table(
        'listings',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('seller_id', UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.String()),
        sa.Column('exam_category', sa.String(), nullable=False),
        sa.Column('subject', sa.String()),
        sa.Column('listing_type', sa.String(), nullable=False),
        sa.Column('condition', sa.String(), nullable=False),
        sa.Column('asking_price', sa.Integer(), nullable=False),
        sa.Column('original_price', sa.Integer()),
        sa.Column('city', sa.String(), nullable=False),
        sa.Column('images', ARRAY(sa.String())),
        sa.Column('is_available', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('sold_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('passkey_hash', sa.String(), nullable=False),
        sa.Column('passkey_invalidated', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('passkey_invalidated_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('views', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column('deleted_at', sa.TIMESTAMP(timezone=True)),
        sa.CheckConstraint("listing_type IN ('BOOK', 'NOTES', 'MODULE', 'BUNDLE')", name='ck_listing_type'),
        sa.CheckConstraint("condition IN ('A', 'B', 'C')", name='ck_condition'),
        sa.CheckConstraint("asking_price > 0", name='ck_asking_price_positive'),
        sa.CheckConstraint(
            "NOT (is_available = TRUE AND (sold_at IS NOT NULL OR deleted_at IS NOT NULL))",
            name='no_available_sold_listing'
        ),
        sa.CheckConstraint(
            "NOT (sold_at IS NOT NULL AND deleted_at IS NOT NULL)",
            name='sold_xor_deleted'
        ),
        sa.ForeignKeyConstraint(['seller_id'], ['public.users.id'], ondelete='CASCADE'),
    )

    op.create_table(
        'conversations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('listing_id', UUID(as_uuid=True)),
        sa.Column('buyer_id', UUID(as_uuid=True), nullable=False),
        sa.Column('seller_id', UUID(as_uuid=True), nullable=False),
        sa.Column('first_message_notified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(['listing_id'], ['listings.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['buyer_id'], ['public.users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['seller_id'], ['public.users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('listing_id', 'buyer_id', name='uq_conversation_listing_buyer'),
    )

    op.create_table(
        'messages',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('conversation_id', UUID(as_uuid=True), nullable=False),
        sa.Column('sender_id', UUID(as_uuid=True), nullable=False),
        sa.Column('body', sa.String(), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sender_id'], ['public.users.id'], ondelete='CASCADE'),
    )

    op.create_table(
        'transactions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('listing_id', UUID(as_uuid=True)),
        sa.Column('buyer_id', UUID(as_uuid=True), nullable=False),
        sa.Column('seller_id', UUID(as_uuid=True), nullable=False),
        sa.Column('amount_rupees', sa.Integer(), nullable=False),
        sa.Column('platform_fee_rupees', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('seller_payout_rupees', sa.Integer(), nullable=False),
        sa.Column('razorpay_payment_link_id', sa.String(), unique=True),
        sa.Column('razorpay_payment_link_url', sa.String()),
        sa.Column('razorpay_payment_id', sa.String(), unique=True),
        sa.Column('status', sa.String(), nullable=False, server_default='initiated'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column('released_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('refunded_at', sa.TIMESTAMP(timezone=True)),
        sa.CheckConstraint("status IN ('initiated', 'released', 'cancelled')", name='ck_transaction_status'),
        sa.CheckConstraint("amount_rupees > 0", name='ck_amount_positive'),
        sa.CheckConstraint("seller_payout_rupees >= 0", name='ck_payout_nonnegative'),
        sa.ForeignKeyConstraint(['listing_id'], ['listings.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['buyer_id'], ['public.users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['seller_id'], ['public.users.id'], ondelete='CASCADE'),
    )

    op.create_table(
        'seller_ratings',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('transaction_id', UUID(as_uuid=True), nullable=False),
        sa.Column('rated_by', UUID(as_uuid=True), nullable=False),
        sa.Column('seller_id', UUID(as_uuid=True), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name='ck_rating_range'),
        sa.UniqueConstraint('transaction_id', 'rated_by', name='uq_rating_transaction_rater'),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['rated_by'], ['public.users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['seller_id'], ['public.users.id'], ondelete='CASCADE'),
    )

    # Indexes
    op.create_index('idx_listings_available', 'listings',
                    ['is_available', 'exam_category', 'listing_type'])
    op.create_index('idx_listings_seller_id', 'listings', ['seller_id'])
    # DESC index — use sa.text() for sort direction; postgresql_ops is for operator classes, not ordering
    op.create_index('idx_listings_created_at', 'listings', [sa.text('created_at DESC')])
    op.create_index('idx_conversations_buyer_id', 'conversations', ['buyer_id'])
    op.create_index('idx_conversations_seller_id', 'conversations', ['seller_id'])
    op.create_index('idx_messages_conversation_id', 'messages', ['conversation_id', 'created_at'])
    op.create_index('idx_transactions_buyer_id', 'transactions', ['buyer_id'])
    op.create_index('idx_transactions_seller_id', 'transactions', ['seller_id'])
    op.create_index(
        'one_active_transaction_per_buyer_listing',
        'transactions',
        ['listing_id', 'buyer_id'],
        unique=True,
        postgresql_where=sa.text("status = 'initiated'")
    )
    op.create_index(
        'idx_transactions_status_created',
        'transactions',
        ['status', 'created_at'],
        postgresql_where=sa.text("status = 'initiated'")
    )


def downgrade():
    op.drop_table('seller_ratings')
    op.drop_table('transactions')
    op.drop_table('messages')
    op.drop_table('conversations')
    op.drop_table('listings')
    op.drop_table('users', schema='public')
```

---

## Integrity Debug Queries

Run these in Supabase SQL editor to verify state:

```sql
-- Users missing a public.users row (trigger failure)
SELECT id FROM auth.users au
WHERE NOT EXISTS (
    SELECT 1 FROM public.users pu WHERE pu.id = au.id
);

-- Impossible listing state (should always return 0 rows)
SELECT * FROM listings
WHERE is_available = TRUE AND sold_at IS NOT NULL;

-- Listings with invalidated passkey still available (should not exist)
SELECT * FROM listings
WHERE passkey_invalidated = TRUE AND is_available = TRUE;

-- Initiated transactions older than 15 min (APScheduler missed these)
SELECT * FROM transactions
WHERE status = 'initiated'
AND created_at < now() - interval '15 minutes';

-- Duplicate ratings (should not exist due to unique constraint)
SELECT transaction_id, rated_by, COUNT(*)
FROM seller_ratings
GROUP BY transaction_id, rated_by
HAVING COUNT(*) > 1;

-- Conversations with unread messages older than 24h
SELECT c.id, c.listing_id, COUNT(m.id) AS unread
FROM conversations c
JOIN messages m ON m.conversation_id = c.id
WHERE m.is_read = FALSE
AND m.created_at < now() - interval '24 hours'
GROUP BY c.id, c.listing_id;

-- Deleted listings incorrectly showing sold_at (should always return 0 rows)
SELECT id, sold_at, deleted_at FROM listings
WHERE sold_at IS NOT NULL AND deleted_at IS NOT NULL;

-- Listing state breakdown
SELECT
    CASE
        WHEN is_available = TRUE THEN 'active'
        WHEN deleted_at IS NOT NULL THEN 'deleted'
        WHEN sold_at IS NOT NULL THEN 'sold'
        ELSE 'paused'
    END AS state,
    COUNT(*) AS count
FROM listings
GROUP BY 1;
```

---

## Files to create

```
backend/app/models/__init__.py
backend/app/models/user.py
backend/app/models/listing.py
backend/app/models/conversation.py
backend/app/models/message.py
backend/app/models/transaction.py
backend/app/models/seller_rating.py
alembic/versions/0001_initial_schema.py
```

## Files to modify

```
backend/app/core/database.py   — import Base, configure async engine + session
alembic/env.py                 — import all models so Alembic sees metadata
```

## New dependencies

No new dependencies. SQLAlchemy 2.0, psycopg3 (`psycopg[binary]`), and Alembic are already in `pyproject.toml`.

---

## Security considerations

The following security rules from CLAUDE.md apply directly to this spec:

- **Rule 5** — Validate ownership before every mutation: `listing.seller_id == user["sub"]`. Schema provides `seller_id` on `listings` and `seller_id` on `transactions` to make this check possible without extra joins.
- **Rule 7** — Parameterized queries only. All queries against these tables go through SQLAlchemy ORM — no f-string SQL, no raw string interpolation.
- **Rule 10** — `PASSKEY_HMAC_SECRET` never logged, never in responses. `passkey_hash` column exists in DB but is never included in any API response after passkey invalidation.
- **Rule 11** — `hmac.compare_digest` for all hash comparisons. The `passkey_hash` column is read-compared only via `verify_passkey()` in `security.py`, never with `==`.
- **Rule 12** — No reopening cancelled transactions. Schema enforces this by design: a `cancelled` transaction row stays cancelled. Late webhooks refund inline and return 200. No UPDATE path from `cancelled` → anything.
- **Rule 1** — Seller contact info is not a column in any table. `public.users` has no phone, no email, no WhatsApp. Email is available only server-side from the JWT payload and is never stored in application tables.

---

## Definition of done

- [ ] `alembic upgrade head` runs against a fresh Supabase Postgres instance with zero errors
- [ ] All six tables exist with correct columns: verify via `\d listings`, `\d transactions`, etc.
- [ ] `listing_type` CHECK constraint rejects `INSERT INTO listings (listing_type, ...) VALUES ('INVALID', ...)` with a constraint violation
- [ ] `condition` CHECK constraint rejects values outside `'A'`, `'B'`, `'C'`
- [ ] `no_available_sold_listing` constraint rejects `UPDATE listings SET is_available=TRUE, sold_at=now() WHERE id=...`
- [ ] `no_available_sold_listing` also rejects `UPDATE listings SET is_available=TRUE, deleted_at=now() WHERE id=...`
- [ ] `sold_xor_deleted` constraint rejects `UPDATE listings SET sold_at=now(), deleted_at=now() WHERE id=...`
- [ ] Deleting a listing sets `deleted_at=now()`, leaves `sold_at=NULL`; listing state breakdown query shows it under "deleted" not "sold"
- [ ] `UNIQUE(listing_id, buyer_id)` on conversations rejects a second conversation row for same buyer/listing pair
- [ ] `one_active_transaction_per_buyer_listing` partial index rejects a second `initiated` transaction for same buyer/listing; allows a second row after first is `cancelled`
- [ ] `UNIQUE(transaction_id, rated_by)` on seller_ratings rejects duplicate ratings
- [ ] `rating CHECK (rating BETWEEN 1 AND 5)` rejects rating of 0 or 6
- [ ] Trigger `on_auth_user_created` fires on new `auth.users` insert and creates a `public.users` row with correct `full_name`, `avatar_url`, `is_verified`
- [ ] Debug query "Users missing a public.users row" returns 0 rows after trigger setup
- [ ] Debug query "Impossible listing state" returns 0 rows on a clean DB
- [ ] All SQLAlchemy model files import without error: `python -c "from app.models.listing import Listing"`
- [ ] `alembic downgrade base` runs cleanly and drops all tables in correct order (FK-safe)

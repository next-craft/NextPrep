# SCHEMA.md — Database Schema

Primary DB: Supabase Postgres. ORM: SQLAlchemy 2.0 async. Driver: psycopg3.
Migrations: Alembic — never make raw schema changes.

---

## public.users

```sql
id            UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE
full_name     TEXT NOT NULL
state         TEXT                          -- state/UT (igod), nullable
city          TEXT                          -- district within `state` (igod), nullable
avatar_url    TEXT
is_verified   BOOLEAN DEFAULT FALSE    -- verification badge: auto TRUE once books_sold >= 10
seller_rating NUMERIC(3,2)            -- avg of received 1-5 seller ratings
books_sold    INTEGER DEFAULT 0       -- verified completed sales (== verified transactions)
books_bought  INTEGER DEFAULT 0       -- verified completed purchases
created_at    TIMESTAMPTZ DEFAULT now()
```

- No `email`, no `password_hash`, no `phone` — Supabase Auth owns identity
- One account per user — same account for buying and selling
- Email available via `payload["email"]` from JWT when needed in backend
- Row auto-created by trigger on Supabase signup (see AUTH.md). The trigger no longer
  sets `is_verified` — the badge is earned via verified transactions, not OAuth email.
- `books_sold` / `books_bought` are counters incremented atomically when a passkey is
  verified (see TRANSACTIONS.md). `is_verified` is flipped TRUE in the same step at 10 sales.

---

## listings

```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
seller_id       UUID REFERENCES public.users(id) ON DELETE CASCADE
title           TEXT NOT NULL
description     TEXT
exam_category   TEXT NOT NULL
subject         TEXT                          -- free text, dropdown defaults in UI
listing_type    TEXT NOT NULL
  CHECK (listing_type IN ('BOOK', 'NOTES', 'MODULE', 'BUNDLE'))
condition       TEXT NOT NULL                 -- A / B / C
asking_price    INTEGER NOT NULL              -- whole rupees, no decimals
original_price  INTEGER                       -- whole rupees
year            INTEGER                       -- optional, CHECK 2000–2026 (book year)
  CHECK (year IS NULL OR (year >= 2000 AND year <= 2026))
edition         TEXT                          -- optional, free text (e.g. "7th edition")
state           TEXT                          -- state/UT (igod). Nullable (legacy rows backfilled).
city            TEXT NOT NULL                 -- district within `state` (igod). Validated app-side.
images          TEXT[]                        -- Cloudinary URLs, max 5
is_available    BOOLEAN DEFAULT TRUE
sold_at         TIMESTAMPTZ DEFAULT NULL
passkey_hash    TEXT NOT NULL                 -- HMAC_SHA256(secret, passkey + listing_id)
passkey_invalidated      BOOLEAN DEFAULT FALSE
passkey_invalidated_at   TIMESTAMPTZ DEFAULT NULL
views           INTEGER DEFAULT 0
created_at      TIMESTAMPTZ DEFAULT now()

CONSTRAINT no_available_sold_listing CHECK (
    NOT (is_available = TRUE AND sold_at IS NOT NULL)
)
```

**Notes:**
- `listing_type` CHECK enforced at DB level — not just application level
- No `is_featured` column
- No `status` text column — availability via `is_available` boolean
- `asking_price` and `original_price` in whole rupees — no paise, ever
- `subject` accepts free text, no DB constraint. UI shows popular dropdown defaults + "Other"
- Passkey stored as hash only — plaintext never persisted. See TRANSACTIONS.md.
- Constraint blocks only: `is_available=TRUE AND sold_at IS NOT NULL` (impossible state)
- Valid states: `is_available=TRUE/sold_at=NULL` (active), `is_available=FALSE/sold_at=NULL` (paused/suspended), `is_available=FALSE/sold_at=NOT NULL` (sold)

---

## conversations

```sql
id          UUID PRIMARY KEY DEFAULT gen_random_uuid()
listing_id  UUID REFERENCES listings(id) ON DELETE CASCADE
buyer_id    UUID REFERENCES public.users(id) ON DELETE CASCADE
seller_id   UUID REFERENCES public.users(id) ON DELETE CASCADE
first_message_notified  BOOLEAN DEFAULT FALSE  -- tracks if seller email was sent
created_at  TIMESTAMPTZ DEFAULT now()

UNIQUE(listing_id, buyer_id)    -- one conversation per buyer per listing
```

Conversations are archived (not deleted) when listing is deleted — needed for dispute history.

---

## messages

```sql
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
conversation_id  UUID REFERENCES conversations(id) ON DELETE CASCADE
sender_id        UUID REFERENCES public.users(id) ON DELETE CASCADE
body             TEXT NOT NULL
is_read          BOOLEAN DEFAULT FALSE
created_at       TIMESTAMPTZ DEFAULT now()
```

---

## transactions

A row exists ONLY for a completed, passkey-verified exchange — there is no payment or
pending state, and no amount is tracked (the platform processes no money). One row per
sold listing.

```sql
id          UUID PRIMARY KEY DEFAULT gen_random_uuid()
listing_id  UUID REFERENCES listings(id) ON DELETE SET NULL
buyer_id    UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE
seller_id   UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE
created_at  TIMESTAMPTZ DEFAULT now()
```

Partial unique index — a listing sells exactly once, so at most one verified transaction
per listing (NULL `listing_id`, set when a listing is deleted, is not deduped):
```sql
CREATE UNIQUE INDEX uq_transaction_per_listing
    ON transactions (listing_id)
    WHERE listing_id IS NOT NULL;
```

No `status`, no `amount_rupees`, no payout, no Razorpay columns. Blocked buyers
(3 wrong passkey attempts) are tracked in Redis only.

---

## seller_ratings

```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
transaction_id  UUID REFERENCES transactions(id) ON DELETE CASCADE
rated_by        UUID REFERENCES public.users(id)
seller_id       UUID REFERENCES public.users(id)
rating          INTEGER CHECK (rating BETWEEN 1 AND 5)
review          TEXT                    -- optional free-text review
created_at      TIMESTAMPTZ DEFAULT now()

UNIQUE(transaction_id, rated_by)    -- one rating per transaction (buyer only)
```

Only the buyer of a transaction may rate, and only once. After each insert the seller's
`public.users.seller_rating` is recomputed as `AVG(rating)` over their ratings.

---

## Search implementation

Search uses WHERE clause + ILIKE only. No similarity search. No vector search. No pg_trgm.

```python
# backend/app/services/listing_service.py
from sqlalchemy import select, or_
from app.models.listing import Listing

async def search_listings(db, q=None, exam_category=None, subject=None,
                           city=None, condition=None, listing_type=None):
    stmt = select(Listing).where(Listing.is_available == True)

    if q:
        stmt = stmt.where(
            or_(
                Listing.title.ilike(f"%{q}%"),
                Listing.description.ilike(f"%{q}%")
            )
        )
    if exam_category:
        stmt = stmt.where(Listing.exam_category == exam_category)
    if subject:
        stmt = stmt.where(Listing.subject.ilike(f"%{subject}%"))
    if city:
        stmt = stmt.where(Listing.city.ilike(f"%{city}%"))
    if condition:
        stmt = stmt.where(Listing.condition == condition)
    if listing_type:
        stmt = stmt.where(Listing.listing_type == listing_type)

    stmt = stmt.order_by(Listing.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()
```

All parameters through SQLAlchemy ORM — never string-interpolated.

---

## Debug queries

```sql
-- Conversations with unread messages older than 24h (seller not responding)
SELECT c.id, c.listing_id, COUNT(m.id) as unread
FROM conversations c
JOIN messages m ON m.conversation_id = c.id
WHERE m.is_read = FALSE
AND m.created_at < now() - interval '24 hours'
GROUP BY c.id, c.listing_id;

-- Top listings by views
SELECT title, exam_category, listing_type, views, asking_price
FROM listings
WHERE is_available = TRUE
ORDER BY views DESC LIMIT 20;

-- Breakdown by listing_type
SELECT listing_type, COUNT(*) as count, AVG(asking_price) as avg_price
FROM listings
WHERE is_available = TRUE
GROUP BY listing_type;

-- Verified transactions (completed exchanges) by day
SELECT
  DATE_TRUNC('day', created_at) as day,
  COUNT(*) as transactions
FROM transactions
GROUP BY 1 ORDER BY 1 DESC;

-- Reputation drift check: counters vs source-of-truth transaction counts
SELECT u.id, u.books_sold,
       (SELECT count(*) FROM transactions t WHERE t.seller_id = u.id) AS actual_sold,
       u.books_bought,
       (SELECT count(*) FROM transactions t WHERE t.buyer_id = u.id) AS actual_bought
FROM public.users u
WHERE u.books_sold <> (SELECT count(*) FROM transactions t WHERE t.seller_id = u.id)
   OR u.books_bought <> (SELECT count(*) FROM transactions t WHERE t.buyer_id = u.id);

-- Impossible state check (should always return 0 rows)
SELECT * FROM listings
WHERE is_available = TRUE AND sold_at IS NOT NULL;

-- Users missing a public.users row (trigger failure check)
SELECT id FROM auth.users au
WHERE NOT EXISTS (
  SELECT 1 FROM public.users pu WHERE pu.id = au.id
);

-- Listings with invalidated passkey but still available (should not exist)
SELECT * FROM listings
WHERE passkey_invalidated = TRUE AND is_available = TRUE;
```
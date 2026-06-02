# SCHEMA.md — Database Schema

Primary DB: Supabase Postgres. ORM: SQLAlchemy 2.0 async. Driver: psycopg3.
Migrations: Alembic — never make raw schema changes.

---

## public.users

```sql
id            UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE
full_name     TEXT NOT NULL
city          TEXT
avatar_url    TEXT
is_verified   BOOLEAN DEFAULT FALSE    -- Google OAuth email verified
seller_rating NUMERIC(3,2)            -- avg of received seller ratings
total_sales   INTEGER DEFAULT 0
created_at    TIMESTAMPTZ DEFAULT now()
```

- No `email`, no `password_hash`, no `phone` — Supabase Auth owns identity
- One account per user — same account for buying and selling
- Email available via `payload["email"]` from JWT when needed in backend
- Row auto-created by trigger on Supabase signup (see AUTH.md)

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
city            TEXT NOT NULL
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
- Passkey stored as hash only — plaintext never persisted. See PAYMENT.md.
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

```sql
id                          UUID PRIMARY KEY DEFAULT gen_random_uuid()
listing_id                  UUID REFERENCES listings(id)
buyer_id                    UUID REFERENCES public.users(id)
seller_id                   UUID REFERENCES public.users(id)
amount_rupees               INTEGER NOT NULL        -- whole rupees
platform_fee_rupees         INTEGER NOT NULL DEFAULT 0   -- 0% in v1
seller_payout_rupees        INTEGER NOT NULL
razorpay_payment_link_id    TEXT UNIQUE
razorpay_payment_link_url   TEXT
razorpay_payment_id         TEXT UNIQUE
status                      TEXT DEFAULT 'initiated'
  -- initiated | released | cancelled
created_at                  TIMESTAMPTZ DEFAULT now()
released_at                 TIMESTAMPTZ
refunded_at                 TIMESTAMPTZ
```

Partial unique index — prevents duplicate initiated transactions per buyer per listing:
```sql
CREATE UNIQUE INDEX one_active_transaction_per_buyer_listing
    ON transactions (listing_id, buyer_id)
    WHERE status = 'initiated';
```

**Status definitions:**
- `initiated` — passkey correct, Razorpay payment link generated, buyer on payment screen
- `released` — webhook confirmed payment, seller paid via Route (terminal)
- `cancelled` — abandoned after 15 min, or late/concurrent webhook refund (terminal)

`disputed` does not exist as a transaction status. Blocked buyers tracked in Redis only.

---

## seller_ratings

```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
transaction_id  UUID REFERENCES transactions(id)
rated_by        UUID REFERENCES public.users(id)
seller_id       UUID REFERENCES public.users(id)
rating          INTEGER CHECK (rating BETWEEN 1 AND 5)
created_at      TIMESTAMPTZ DEFAULT now()

UNIQUE(transaction_id, rated_by)    -- prevents duplicate ratings per transaction
```

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
-- Initiated transactions older than 15 min (APScheduler should have caught these)
SELECT * FROM transactions
WHERE status = 'initiated'
AND created_at < now() - interval '15 minutes';

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

-- Revenue summary by day
SELECT
  DATE_TRUNC('day', created_at) as day,
  COUNT(*) as transactions,
  SUM(amount_rupees) as volume_inr
FROM transactions
WHERE status = 'released'
GROUP BY 1 ORDER BY 1 DESC;

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
# NextPrep — Study Material Exchange India (SMEI)

India's peer-to-peer marketplace for exam books, notes, and coaching modules. Students buy and sell **physical** study material via **in-person meetup** — like OLX, but structured for JEE, NEET, UPSC, CA, GATE, and school exams.

> **Exchange model:** in-person meetup only. No shipping, no courier, no delivery tracking.
> **Payments:** the platform processes **no money** — buyers and sellers settle directly, offline, at the meetup. A buyer-entered 8-digit passkey is the sole record of a completed transaction.
> **Market:** India only · **Currency:** INR whole rupees (display only) · **Accounts:** one account per user — same account buys and sells.

---

## Table of contents

- [What makes it different](#what-makes-it-different)
- [The passkey transaction flow](#the-passkey-transaction-flow)
- [Reputation & ratings](#reputation--ratings)
- [Tech stack](#tech-stack)
- [Repository layout](#repository-layout)
- [Getting started](#getting-started)
- [Environment variables](#environment-variables)
- [API reference](#api-reference)
- [Data model](#data-model)
- [Background jobs](#background-jobs)
- [Security model](#security-model)
- [Testing](#testing)
- [Deployment](#deployment)
- [Out of scope (v1)](#out-of-scope-v1)
- [License](#license)

---

## What makes it different

Unlike a generic classifieds site, NextPrep is purpose-built for exam preparation material:

1. **Structured metadata** — every listing carries an exam category, subject, listing type, and condition grade, so search is precise.
2. **Trust without shipping or payment rails** — an 8-digit **passkey** proves the buyer and seller actually met in person and the buyer inspected the goods. The platform never touches the money.
3. **Focused scope** — study materials only. No pirated scans, no bulk photocopies, no off-topic spam.
4. **One unified search stream** — books, notes, and modules appear together; material type is a *filter*, not a separate section.

**Allowed:** published books (HC Verma, NCERT, RD Sharma), handwritten/self-made notes, original coaching modules (Allen, FIITJEE, PW, Aakash), formula sheets, test series, bundles.
**Not allowed:** pirated scans, bulk photocopies, unauthorized PDF reproductions.

---

## The passkey transaction flow

The platform **does not process payments**. Buyers and sellers settle money directly, offline, at the meetup (cash / UPI — their choice). A buyer-entered 8-digit passkey is the **sole** mechanism that confirms a completed transaction.

```
1. LIST       Seller creates a listing → system generates an 8-digit passkey.
              Only the HMAC-SHA256 hash is stored. Plaintext is shown ONCE.

2. MEET       Buyer messages the seller and they meet in person.
              Buyer inspects the material and settles payment directly with the seller.

3. PASSKEY    Once paid, the seller shares the 8-digit code verbally.
              Buyer enters it in the app → POST /transactions/verify-passkey
              (max 3 attempts per buyer per listing over 7 days, Redis-tracked).

4. CONFIRM    On a correct passkey, atomically in one transaction:
              listing → SOLD (drops out of active results, passkey invalidated),
              seller.books_sold += 1, buyer.books_bought += 1,
              seller earns the verification badge at 10 sales.
              The seller gets a "your listing has been sold" email.

5. RATE       The buyer is prompted to rate the seller (1-5 stars + optional
              review) → POST /transactions/{id}/rating. Buyer-only, once.
```

**Race safety:** completion is a single atomic, one-way step — `UPDATE listings ... WHERE is_available = TRUE` selects exactly one winning buyer. A second concurrent verify gets a clean `409`; a sold listing can never be reopened. There is no payment window, no webhook, and nothing to abandon — verification is instantaneous.

---

## Reputation & ratings

Every reputation metric derives **only** from verified transactions (a `transactions` row exists only after a correct passkey).

- **`books_sold`** — a seller's verified completed sales (≡ their verified transaction count).
- **`books_bought`** — a buyer's verified completed purchases.
- **`seller_rating`** — `NUMERIC(3,2)` average of 1–5 ratings, recomputed on every rating insert.
- **Verification badge** (`is_verified`) — a blue badge, auto-set `TRUE` once `books_sold >= 10`. Earned, not granted at signup.
- **Ratings** — only the buyer of a transaction can rate, only once (DB-enforced via `UNIQUE(transaction_id, rated_by)`), with an optional free-text review.

---

## Tech stack

### Frontend
- **Next.js 16** (App Router, React Server Components) — JavaScript only (`.js` / `.jsx`, no TypeScript)
- **React 19**, **TanStack Query v5** for client state, mutations, and polling
- **Supabase Auth** via `@supabase/ssr` — Google OAuth only, session in httpOnly cookies
- **Tailwind CSS v3** + Radix UI primitives — a warm "paper & ink" theme (Fraunces / Hanken Grotesk / JetBrains Mono)
- **Cloudinary** for direct browser-to-CDN image upload
- **Axios** API client with Bearer-token interceptor; **Framer Motion**; **Sonner** toasts
- No payment integration — transactions are confirmed by passkey only
- Deploys to **Vercel**

### Backend
- **FastAPI** (async, Python 3.11+) with **Pydantic v2**
- **SQLAlchemy 2.0** async ORM over **psycopg3** (`postgresql+psycopg://`)
- **Supabase** managed Postgres; **Alembic** migrations (never raw schema changes)
- **Supabase JWKS** ES256 JWT verification — no custom auth, no FastAPI auth endpoints
- **Redis** (Railway) for rate limiting, passkey attempts, message cache
- **APScheduler** in-process scheduler (no Celery), **Resend** email
- No payment SDK, no payouts, no webhooks — the platform processes no money
- **Cloudinary** image storage; Python `logging` (no `print`)
- Deploys to **Railway**

---

## Repository layout

```
NextPrep/
├── .claude/                 # Project instructions, specs, and feature docs
│   ├── CLAUDE.md            # Single source of truth — read before writing code
│   ├── docs/                # AUTH.md · TRANSACTIONS.md · SCHEMA.md
│   └── specs/               # product / technical / infrastructure / decisions
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app, CORS, lifespan (Redis + scheduler)
│   │   ├── core/            # config, database, security (JWT/passkey), redis, supabase_admin
│   │   ├── models/          # SQLAlchemy models (users, listings, transactions, ...)
│   │   ├── schemas/         # Pydantic request/response models
│   │   ├── routers/         # listings, transactions, users, chat, reports
│   │   ├── services/        # business logic (routers stay HTTP-only)
│   │   └── jobs/            # APScheduler (no jobs in v1 — kept for future use)
│   ├── alembic/             # migrations (initial schema → remove payments)
│   ├── tests/               # pytest suites per feature
│   └── pyproject.toml
├── frontend/
│   ├── app/                 # App Router pages (see route map below)
│   ├── components/          # listings / dashboard / chat / shared / ui
│   ├── lib/                 # supabase clients, api.js, queries.js, utils.js, motion.js
│   ├── constants/           # exam categories, listing types, cities, conditions, subjects
│   └── middleware.js        # Supabase session refresh on every request
├── supabase/                # Supabase project config
├── docker-compose.yml       # local Redis (host port 6390)
└── requirements.txt         # backend dependencies (source of truth)
```

### Frontend route map

| Route | Rendering | Purpose |
|-------|-----------|---------|
| `/` | SSR | Landing — hero, how-it-works, browse-by-exam, recent listings |
| `/login` | Client | Google OAuth sign-in |
| `/auth/callback` | Route handler | Exchange OAuth code for session |
| `/listings` | SSR | Browse + filters (search, exam, type, condition, city, subject) |
| `/listings/[id]` | SSR | Listing detail, gallery, seller card, confirm-exchange / Message / Report |
| `/listings/new` | Client | Create-listing form (auth-gated) |
| `/users/[id]` | SSR | Public seller profile + their active listings |
| `/dashboard` | Client | Selling / Messages / Transactions tabs |
| `/chat/[id]` | Client | Conversation thread, 4s polling, auto-read |
| `/settings` | Client | Edit profile (name, city, avatar) |
| `/contact` | SSR | Static contact + reporting guidance |

---

## Getting started

### Prerequisites
- Python 3.11, Node.js 20+, Docker (for local Redis)
- A reachable Supabase project (local auth uses Supabase's live JWKS endpoint)

### 1. Clone and start local services
```bash
docker-compose up -d        # Redis on localhost:6390
```

### 2. Backend
The repo uses a **single shared virtualenv at the project root** (`.venv/`) — always use it, never global Python.

```bash
# from project root, Windows PowerShell
.venv\Scripts\activate
.venv\Scripts\pip install -r requirements.txt

cd backend
..\.venv\Scripts\alembic upgrade head
..\.venv\Scripts\uvicorn app.main:app --reload --port 8000
```

Backend runs at `http://localhost:8000` · API base `http://localhost:8000/v1` · interactive docs at `/docs` (development only).

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:3000`.

### Adding a backend dependency
Add it to **both** `requirements.txt` and `backend/pyproject.toml`, then re-run `.venv\Scripts\pip install -r requirements.txt`.

---

## Environment variables

### Backend (`.env`)
```
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db
REDIS_URL=redis://localhost:6390/0
PASSKEY_HMAC_SECRET=<32+ random bytes hex>
CLOUDINARY_CLOUD_NAME=xxx
CLOUDINARY_API_KEY=xxx
CLOUDINARY_API_SECRET=xxx
RESEND_API_KEY=re_xxx
FRONTEND_URL=http://localhost:3000
ENVIRONMENT=development
```

### Frontend (`.env.local`)
```
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
NEXT_PUBLIC_API_URL=http://localhost:8000/v1
API_URL=http://localhost:8000/v1
```

> `SUPABASE_SERVICE_ROLE_KEY` and `PASSKEY_HMAC_SECRET` are **backend only** and must never be exposed to the client or committed.

---

## API reference

Base URL: `http://localhost:8000/v1` (prod: `https://api.yourdomain.com/v1`).
Auth header: `Authorization: Bearer <supabase_access_token>`. No auth endpoints live on FastAPI — all auth goes directly to Supabase.

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/listings` | Public | Search available listings (`?q=&exam_category=&subject=&city=&condition=&listing_type=&seller_id=`) |
| `POST` | `/listings` | Protected | Create listing; returns passkey **once** |
| `GET` | `/listings/mine` | Protected | Caller's own listings (all states) |
| `GET` | `/listings/{id}` | Public | Detail; increments view counter |
| `PATCH` | `/listings/{id}` | Owner | Update fields |
| `DELETE` | `/listings/{id}` | Owner | Soft-delete |
| `PATCH` | `/listings/{id}/passkey` | Owner | Regenerate passkey |
| `GET` | `/users/me` | Protected | Caller's profile (`books_sold`, `books_bought`, `seller_rating`, `is_verified`) |
| `PATCH` | `/users/me` | Protected | Update name / city / avatar |
| `GET` | `/users/{id}` | Public | Public profile |
| `GET` | `/conversations` | Protected | Caller's conversations |
| `POST` | `/conversations` | Protected | Get-or-create conversation for a listing |
| `GET` | `/conversations/{id}/messages` | Participant | Messages (30s Redis cache) |
| `POST` | `/conversations/{id}/messages` | Participant | Send message (100/hour limit) |
| `PATCH` | `/conversations/{id}/messages/read` | Participant | Mark other party's messages read |
| `POST` | `/transactions/verify-passkey` | Protected | Verify 8-digit code → mark listing SOLD, record verified transaction |
| `GET` | `/transactions` | Protected | Caller's transactions (buyer + seller) |
| `POST` | `/transactions/{id}/rating` | Buyer-only, once | Rate the seller (1–5 stars + optional review) |
| `POST` | `/reports` | Protected | Report a listing (20/hour limit) |

### Canonical constants

```
Exam categories  JEE_MAINS · JEE_ADVANCED · NEET_UG · NEET_PG · UPSC_CSE · UPSC_OTHER ·
                 CA_FOUNDATION · CA_INTERMEDIATE · CA_FINAL · GATE · GMAT · GRE · IELTS ·
                 CUET · CLASS_9 · CLASS_10 · CLASS_11 · CLASS_12 · OTHER
Listing types    BOOK · NOTES · MODULE · BUNDLE          (DB CHECK enforced)
Conditions       A (like new) · B (good) · C (acceptable) (DB CHECK enforced)
Transactions     No statuses — a row exists only for a completed, passkey-verified exchange
Report reasons   PIRACY · CONTACT_INFO · SPAM · NOT_STUDY_MATERIAL · PROHIBITED · ABUSIVE · OTHER
```

---

## Data model

Seven tables, SQLAlchemy 2.0 async ORM, Alembic-managed. Prices are whole rupees, display-only.

| Table | Key columns | Notes |
|-------|-------------|-------|
| `users` | `id` (= Supabase auth UUID), `full_name`, `city`, `avatar_url`, `is_verified`, `seller_rating`, `books_sold`, `books_bought` | Created by an `auth.users` trigger on first Google sign-in. No email column — Supabase Auth owns identity. `is_verified` is the badge (auto at 10 sales). Counters incremented atomically on passkey verification. |
| `listings` | `seller_id`, `title`, `exam_category`, `subject`, `listing_type`, `condition`, `asking_price`, `original_price`, `city`, `images[]`, `is_available`, `sold_at`, `passkey_hash`, `passkey_invalidated`, `views`, `deleted_at` | Soft-delete via `deleted_at`. CHECK constraints on type/condition/prices and `is_available` vs `sold_at`/`deleted_at`. |
| `transactions` | `listing_id`, `buyer_id`, `seller_id`, `created_at` | A row exists only for a completed, passkey-verified exchange — no payment/status columns. Partial unique index: at most one verified transaction per listing. |
| `conversations` | `listing_id` (SET NULL on delete), `buyer_id`, `seller_id`, `first_message_notified` | Unique (listing, buyer). Archived on listing delete, never removed. |
| `messages` | `conversation_id`, `sender_id`, `body`, `is_read` | Body ≤ 2000 chars (app-enforced). |
| `reports` | `listing_id`, `reporter_id`, `reason`, `note`, `status` | Unique (listing, reporter); idempotent. Indexed on `(status, created_at DESC)`. |
| `seller_ratings` | `transaction_id`, `rated_by`, `seller_id`, `rating` (1–5), `review` | Unique (transaction, rater). Buyer-only. Average denormalised onto `users.seller_rating`. |

Search is `WHERE` + `ILIKE` only — no vector search, no `pg_trgm`, no full-text engine.

---

## Background jobs

A single **APScheduler** `AsyncIOScheduler` runs inside the FastAPI process (started/stopped via the app lifespan). In v1 it has **no scheduled jobs** — transactions complete instantly when the buyer enters the passkey, so there is nothing to expire or abandon. The scheduler is kept wired into the app lifespan as the home for any future background job.

### Redis keys
```
passkey_attempts:{listing_id}:{buyer_id}    integer, TTL 7 days (3 attempts max)
chat_rate:{conversation_id}:{sender_id}     integer, TTL 1 hour
chat:{conversation_id}                       cached messages, TTL 30s
report_rate:{reporter_id}                    integer, TTL 1 hour
```

---

## Security model

Non-negotiable rules enforced across the codebase:

1. Seller contact info is **never** returned in any API response.
2. Supabase session lives in **httpOnly cookies**, never localStorage.
3. Ownership is validated before every mutation (`listing.seller_id == user["sub"]`).
4. Images upload **directly** to Cloudinary, never through FastAPI.
5. Parameterized queries only (SQLAlchemy ORM) — never string-interpolate user input.
6. CORS allows only `FRONTEND_URL` in production — never `*`.
7. `SUPABASE_SERVICE_ROLE_KEY` is used only in server-internal contexts (background jobs and post-response notification tasks: the chat first-message and sale-complete emails) — never in user-facing request logic.
8. `PASSKEY_HMAC_SECRET` is never logged or returned; passkeys are compared with `hmac.compare_digest`, never `==`.
9. Listing completion is atomic and one-way (`UPDATE ... WHERE is_available = TRUE` picks one winner); a sold listing is never reopened.
10. Only the buyer can rate, only after a verified passkey, once per transaction (DB-enforced).
11. Listings are hidden immediately on piracy/copyright reports.

**Logging:** every request, transaction completion, JWT failure, scheduler run, email send, and Redis failure is logged. Passkey plaintext/hash, JWT strings, `PASSKEY_HMAC_SECRET`, and PII beyond UUID are **never** logged.

**Moderation (v1):** manual, via the Supabase dashboard (hide/remove listings with SQL, disable users in Supabase Auth). No admin panel.

---

## Testing

Backend tests live in `backend/tests/` as per-feature pytest suites (content policy, notifications, schema, auth, transactions, chat, API contracts, listings CRUD). They emphasise atomicity guarantees, rate limiting, the one-rating-per-transaction rule, and that no endpoint leaks PII.

```bash
.venv\Scripts\activate
cd backend
..\.venv\Scripts\pytest                            # full suite
..\.venv\Scripts\pytest tests/test_09-transactions.py   # one feature
```

---

## Deployment

- **Frontend → Vercel**, **Backend + Redis → Railway**, **Postgres → Supabase**, **Images → Cloudinary**, **Email → Resend**.
- Run `alembic upgrade head` on deploy; never make raw schema changes.
- The Supabase JWKS endpoint must be reachable from the backend at all times (no JWKS caching in v1).

---

## Out of scope (v1)

Payments / payment processing · shipping/courier · delivery tracking · email-password or phone/Aadhaar auth · separate buyer/seller accounts · buyer ratings · admin panel · automated moderation & disputes · WebSockets · mobile app · multi-language · referrals · Celery · JWKS caching · platform fee · featured/sponsored listings · vector/ML search.

---

## License

**Proprietary — All rights reserved.** Copyright © 2026 Daksh Kapoor and Aryan.

This is **not** open-source software. No license is granted to use, copy, modify, deploy, or distribute any part of this project without the prior **written permission** of the owners. See [`LICENSE`](LICENSE) for the full terms.

---

*Built by a two-person team (one frontend, one backend). The full source of truth for conventions and constraints is [`.claude/CLAUDE.md`](.claude/CLAUDE.md), with deeper detail in `.claude/docs/` and `.claude/specs/`.*

# NextPrep — Study Material Exchange India (SMEI)

India's peer-to-peer marketplace for exam books, notes, and coaching modules. Students buy and sell **physical** study material via **in-person meetup** — like OLX, but structured for JEE, NEET, UPSC, CA, GATE, and school exams.

> **Exchange model:** in-person meetup only. No shipping, no courier, no delivery tracking.
> **Market:** India only · **Currency:** INR whole rupees (paise only at the Razorpay boundary).
> **Accounts:** one account per user — same account buys and sells.

---

## Table of contents

- [What makes it different](#what-makes-it-different)
- [The passkey escrow-free payment flow](#the-passkey-escrow-free-payment-flow)
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
2. **Trust without shipping** — an 8-digit **passkey** proves the buyer and seller actually met in person and the buyer inspected the goods *before* any money moves.
3. **Focused scope** — study materials only. No pirated scans, no bulk photocopies, no off-topic spam.
4. **One unified search stream** — books, notes, and modules appear together; material type is a *filter*, not a separate section.

**Allowed:** published books (HC Verma, NCERT, RD Sharma), handwritten/self-made notes, original coaching modules (Allen, FIITJEE, PW, Aakash), formula sheets, test series, bundles.
**Not allowed:** pirated scans, bulk photocopies, unauthorized PDF reproductions.

---

## The passkey escrow-free payment flow

The platform **never holds funds**. Razorpay Route disburses 100% of the payment directly to the seller's linked account. The passkey replaces escrow as the trust mechanism.

```
1. LIST       Seller creates a listing → system generates an 8-digit passkey.
              Only the HMAC-SHA256 hash is stored. Plaintext is shown ONCE.

2. MEET       Buyer taps "Buy Now" (no DB write yet) and messages the seller.
              They meet in person. Buyer inspects the material.

3. PASSKEY    Satisfied buyer asks for the passkey. Seller shares it verbally.
              Buyer enters it in the app → POST /payments/verify-passkey
              (max 3 attempts per buyer per listing over 7 days, Redis-tracked).

4. PAY        On a correct passkey, the backend creates a transaction
              (status=initiated) and a Razorpay payment link (15-min expiry).
              Buyer is redirected to Razorpay (UPI / card / net banking / wallet).

5. CONFIRM    Razorpay calls POST /payments/webhook (HMAC-verified, authoritative).
              Atomic update: transaction → released, listing → sold,
              passkey invalidated. Razorpay Route pays the seller 100%.
              Seller gets a "sold for ₹X" email.

6. ABANDON    A buyer who never pays? APScheduler cancels the transaction after
              15 minutes. The listing stays available; the passkey is reusable.
```

**Race safety:** if two buyers pay near-simultaneously, the webhook's atomic `UPDATE listings ... WHERE is_available = TRUE` lets exactly one win. The losing payment is refunded immediately. Late webhooks for already-cancelled transactions are also refunded — cancelled transactions are never reopened.

The status page (`/transactions/[id]/status`) polls every 2 seconds while a payment is `initiated` and the callback itself performs **no** database writes — the webhook is the single source of truth.

---

## Tech stack

### Frontend
- **Next.js 16** (App Router, React Server Components) — JavaScript only (`.js` / `.jsx`, no TypeScript)
- **React 19**, **TanStack Query v5** for client state, mutations, and polling
- **Supabase Auth** via `@supabase/ssr` — Google OAuth only, session in httpOnly cookies
- **Tailwind CSS v3** + Radix UI primitives — a warm "paper & ink" theme (Fraunces / Hanken Grotesk / JetBrains Mono)
- **Cloudinary** for direct browser-to-CDN image upload
- **Axios** API client with Bearer-token interceptor; **Framer Motion**; **Sonner** toasts
- Deploys to **Vercel**

### Backend
- **FastAPI** (async, Python 3.11+) with **Pydantic v2**
- **SQLAlchemy 2.0** async ORM over **psycopg3** (`postgresql+psycopg://`)
- **Supabase** managed Postgres; **Alembic** migrations (never raw schema changes)
- **Supabase JWKS** ES256 JWT verification — no custom auth, no FastAPI auth endpoints
- **Redis** (Railway) for rate limiting, passkey attempts, message cache, notification cooldowns
- **APScheduler** in-process jobs (no Celery), **Razorpay SDK + Route**, **Resend** email
- **Cloudinary** image storage; Python `logging` (no `print`)
- Deploys to **Railway**

---

## Repository layout

```
NextPrep/
├── .claude/                 # Project instructions, specs, and feature docs
│   ├── CLAUDE.md            # Single source of truth — read before writing code
│   ├── docs/                # AUTH.md · PAYMENT.md · SCHEMA.md
│   └── specs/               # product / technical / infrastructure / decisions
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app, CORS, lifespan (Redis + scheduler)
│   │   ├── core/            # config, database, security (JWT/passkey), redis, supabase_admin
│   │   ├── models/          # SQLAlchemy models (users, listings, transactions, ...)
│   │   ├── schemas/         # Pydantic request/response models
│   │   ├── routers/         # listings, payments, users, chat, reports
│   │   ├── services/        # business logic (routers stay HTTP-only)
│   │   └── jobs/            # APScheduler — cancel_abandoned_transactions
│   ├── alembic/             # migrations (initial schema → reports table)
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
| `/listings/[id]` | SSR | Listing detail, gallery, seller card, Buy Now / Message / Report |
| `/listings/new` | Client | Create-listing form (auth + onboarding gated) |
| `/sell/onboard` | Client | Razorpay Route KYC, 2-step stepper |
| `/users/[id]` | SSR | Public seller profile + their active listings |
| `/dashboard` | Client | Selling / Buying / Transactions tabs |
| `/chat/[id]` | Client | Conversation thread, 4s polling, auto-read |
| `/transactions/[id]/status` | Client | Payment status polling (2s while initiated) |
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
RAZORPAY_KEY_ID=rzp_live_xxx
RAZORPAY_KEY_SECRET=xxx
RAZORPAY_WEBHOOK_SECRET=xxx
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

> `RAZORPAY_KEY_SECRET`, `SUPABASE_SERVICE_ROLE_KEY`, and `PASSKEY_HMAC_SECRET` are **backend only** and must never be exposed to the client or committed.

---

## API reference

Base URL: `http://localhost:8000/v1` (prod: `https://api.yourdomain.com/v1`).
Auth header: `Authorization: Bearer <supabase_access_token>`. No auth endpoints live on FastAPI — all auth goes directly to Supabase.

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/listings` | Public | Search available listings (`?q=&exam_category=&subject=&city=&condition=&listing_type=&seller_id=`) |
| `POST` | `/listings` | Protected (onboarded sellers) | Create listing; returns passkey **once** |
| `GET` | `/listings/mine` | Protected | Caller's own listings (all states) |
| `GET` | `/listings/{id}` | Public | Detail; increments view counter |
| `PATCH` | `/listings/{id}` | Owner | Update fields |
| `DELETE` | `/listings/{id}` | Owner | Soft-delete |
| `PATCH` | `/listings/{id}/passkey` | Owner | Regenerate passkey |
| `GET` | `/users/me` | Protected | Caller's profile (includes `razorpay_account_id`) |
| `PATCH` | `/users/me` | Protected | Update name / city / avatar |
| `GET` | `/users/{id}` | Public | Public profile (no payment data) |
| `GET` | `/conversations` | Protected | Caller's conversations |
| `POST` | `/conversations` | Protected | Get-or-create conversation for a listing |
| `GET` | `/conversations/{id}/messages` | Participant | Messages (30s Redis cache) |
| `POST` | `/conversations/{id}/messages` | Participant | Send message (100/hour limit) |
| `PATCH` | `/conversations/{id}/messages/read` | Participant | Mark other party's messages read |
| `POST` | `/payments/onboard` | Protected | Start Razorpay Route KYC, returns onboarding URL |
| `POST` | `/payments/onboard/complete` | Protected | Verify KYC, persist `razorpay_account_id` |
| `POST` | `/payments/verify-passkey` | Protected | Verify passkey → payment link |
| `POST` | `/payments/webhook` | HMAC-verified | Razorpay confirmation (no user auth) |
| `GET` | `/transactions` | Protected | Caller's transactions (buyer + seller) |
| `GET` | `/transactions/{id}/status` | Buyer-scoped | Poll payment/passkey status |
| `POST` | `/reports` | Protected | Report a listing (20/hour limit) |

### Canonical constants

```
Exam categories  JEE_MAINS · JEE_ADVANCED · NEET_UG · NEET_PG · UPSC_CSE · UPSC_OTHER ·
                 CA_FOUNDATION · CA_INTERMEDIATE · CA_FINAL · GATE · GMAT · GRE · IELTS ·
                 CUET · CLASS_9 · CLASS_10 · CLASS_11 · CLASS_12 · OTHER
Listing types    BOOK · NOTES · MODULE · BUNDLE          (DB CHECK enforced)
Conditions       A (like new) · B (good) · C (acceptable) (DB CHECK enforced)
Transactions     initiated → released | cancelled         (terminal states)
Report reasons   PIRACY · CONTACT_INFO · SPAM · NOT_STUDY_MATERIAL · PROHIBITED · ABUSIVE · OTHER
```

---

## Data model

Seven tables, SQLAlchemy 2.0 async ORM, Alembic-managed. Prices are whole rupees.

| Table | Key columns | Notes |
|-------|-------------|-------|
| `users` | `id` (= Supabase auth UUID), `full_name`, `city`, `avatar_url`, `is_verified`, `seller_rating`, `razorpay_account_id` | Created by an `auth.users` trigger on first Google sign-in. No email column — Supabase Auth owns identity. `total_sales` is computed live from released transactions. |
| `listings` | `seller_id`, `title`, `exam_category`, `subject`, `listing_type`, `condition`, `asking_price`, `original_price`, `city`, `images[]`, `is_available`, `sold_at`, `passkey_hash`, `passkey_invalidated`, `views`, `deleted_at` | Soft-delete via `deleted_at`. CHECK constraints on type/condition/prices and `is_available` vs `sold_at`/`deleted_at`. |
| `transactions` | `listing_id`, `buyer_id`, `seller_id`, `amount_rupees`, `platform_fee_rupees` (0 in v1), `seller_payout_rupees`, `razorpay_*`, `status`, `released_at`, `refunded_at` | Partial unique index: one `initiated` transaction per (listing, buyer). |
| `conversations` | `listing_id` (SET NULL on delete), `buyer_id`, `seller_id`, `first_message_notified` | Unique (listing, buyer). Archived on listing delete, never removed. |
| `messages` | `conversation_id`, `sender_id`, `body`, `is_read` | Body ≤ 2000 chars (app-enforced). |
| `reports` | `listing_id`, `reporter_id`, `reason`, `note`, `status` | Unique (listing, reporter); idempotent. Indexed on `(status, created_at DESC)`. |
| `seller_ratings` | `transaction_id`, `rated_by`, `seller_id`, `rating` (1–5) | Unique (transaction, rater). |

Search is `WHERE` + `ILIKE` only — no vector search, no `pg_trgm`, no full-text engine.

---

## Background jobs

A single **APScheduler** `AsyncIOScheduler` runs inside the FastAPI process (started/stopped via the app lifespan):

- **`cancel_abandoned_transactions`** — every 5 minutes. Finds `initiated` transactions older than 15 minutes and atomically cancels them (the `WHERE status='initiated'` guard avoids racing the webhook). For each, it sends the seller an "abandoned checkout" email, throttled to once per listing per 6 hours via a Redis cooldown key. The listing stays available and the passkey remains reusable.

### Redis keys
```
passkey_attempts:{listing_id}:{buyer_id}    integer, TTL 7 days
abandoned_notified:{listing_id}             integer, TTL 6 hours
chat_rate:{conversation_id}:{sender_id}     integer, TTL 1 hour
chat:{conversation_id}                       cached messages, TTL 30s
report_rate:{reporter_id}                    integer, TTL 1 hour
```

---

## Security model

Non-negotiable rules enforced across the codebase:

1. Seller contact info is **never** returned in any API response.
2. Razorpay webhook HMAC signature is verified before processing; unrecognised events return **200** (no retry storms).
3. Supabase session lives in **httpOnly cookies**, never localStorage.
4. Ownership is validated before every mutation (`listing.seller_id == user["sub"]`).
5. Images upload **directly** to Cloudinary, never through FastAPI.
6. Parameterized queries only (SQLAlchemy ORM) — never string-interpolate user input.
7. CORS allows only `FRONTEND_URL` in production — never `*`.
8. `SUPABASE_SERVICE_ROLE_KEY` is used only in server-internal contexts (webhook handler, scheduler, and the post-response chat email lookup) — never in user-facing request logic.
9. `PASSKEY_HMAC_SECRET` is never logged or returned; passkeys are compared with `hmac.compare_digest`, never `==`.
10. Cancelled transactions are never reopened — late webhooks always refund.
11. Listings are hidden immediately on piracy/copyright reports.

**Logging:** every request, payment event, JWT failure, scheduler run, email send, and Redis failure is logged. Passkey plaintext, JWT strings, Razorpay secrets, and PII beyond UUID are **never** logged.

**Moderation (v1):** manual, via the Supabase dashboard (hide/remove listings with SQL, disable users in Supabase Auth). No admin panel.

---

## Testing

Backend tests live in `backend/tests/` as per-feature pytest suites (content policy, notifications, schema, auth, payment, chat, API contracts, listings CRUD). They emphasise atomicity guarantees, rate limiting, idempotency, and the rule that no endpoint leaks PII.

```bash
.venv\Scripts\activate
cd backend
..\.venv\Scripts\pytest                       # full suite
..\.venv\Scripts\pytest tests/test_09-payment.py   # one feature
```

---

## Deployment

- **Frontend → Vercel**, **Backend + Redis → Railway**, **Postgres → Supabase**, **Images → Cloudinary**, **Email → Resend**.
- Run `alembic upgrade head` on deploy; never make raw schema changes.
- The Razorpay webhook must point at `POST /v1/payments/webhook` with the matching `RAZORPAY_WEBHOOK_SECRET`.
- The Supabase JWKS endpoint must be reachable from the backend at all times (no JWKS caching in v1).

---

## Out of scope (v1)

Shipping/courier · delivery tracking · email-password or phone/Aadhaar auth · separate buyer/seller accounts · buyer ratings · admin panel · automated moderation & disputes · WebSockets · mobile app · multi-language · referrals · Celery · JWKS caching · platform fee · featured/sponsored listings · vector/ML search.

---

## License

**Proprietary — All rights reserved.** Copyright © 2026 Daksh Kapoor and Aryan.

This is **not** open-source software. No license is granted to use, copy, modify, deploy, or distribute any part of this project without the prior **written permission** of the owners. See [`LICENSE`](LICENSE) for the full terms.

---

*Built by a two-person team (one frontend, one backend). The full source of truth for conventions and constraints is [`.claude/CLAUDE.md`](.claude/CLAUDE.md), with deeper detail in `.claude/docs/` and `.claude/specs/`.*

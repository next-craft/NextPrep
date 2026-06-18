# CLAUDE.md — Study Material Exchange India

Single source of truth. Read before writing any code.
Detail files: `.claude/docs/AUTH.md` | `.claude/docs/SCHEMA.md` | `.claude/docs/TRANSACTIONS.md`
Specs: `.claude/specs/product/` | `.claude/specs/technical/` | `.claude/specs/infrastructure/` | `.claude/specs/decisions/`

---

## Project overview

India's peer-to-peer marketplace for exam books, notes, and coaching materials.
Students buy and sell physical study material via in-person meetup — like OLX, but structured.

**Exchange model:** In-person meetup only. No shipping. No courier. No delivery tracking.
**Payments:** The platform does NOT process payments. Buyers and sellers settle money directly, offline, at the meetup. A buyer-entered 8-digit passkey is the sole record of a completed transaction.
**Accounts:** One account per user. Same account for buying and selling.
**Prices:** INR rupees only, whole rupees. Prices are displayed only — never collected or transferred.
**Market:** India only.

**Allowed listings:** Physical books, handwritten notes, self-created notes, original coaching modules (Allen, FIITJEE, PW, Aakash), formula sheets, test series, bundles.

**Not allowed:** Pirated scans, photocopied books sold in bulk, unauthorized PDF reproductions.

**Search:** One unified stream. Books, notes, and modules appear together. Material type is a filter, not a section.

---

## Team

Two developers. No DevOps, no designer, no PM.
- Dev 1: Frontend (Next.js 16, TanStack Query, Tailwind, Shadcn/ui, Cloudinary)
- Dev 2: Backend (FastAPI, SQLAlchemy 2.0, Supabase Postgres, Redis, Resend)

Do not suggest architectures requiring a third person to maintain.

---

## Tech stack

### Frontend
- **Framework:** Next.js 16 (App Router, React Server Components)
- **Language:** JavaScript only — `.js` and `.jsx`. No TypeScript.
- **Auth:** Supabase Auth via `@supabase/ssr` — Google OAuth only. No email/password. Session in httpOnly cookies.
- **Data fetching:** SSR for public/SEO pages + TanStack Query v5 for client state, mutations, chat polling
- **Styling:** Tailwind CSS v3 + Shadcn/ui
- **Image upload:** Cloudinary upload widget (direct browser-to-Cloudinary)
- **Payments:** None — no payment integration. Transactions are confirmed by passkey only.
- **Deployment:** Vercel
- **Dev URL:** `http://localhost:3000`

### Backend
- **Framework:** FastAPI (async, Python 3.11+)
- **Auth:** Supabase JWKS — ES256 JWT verification. No custom JWT. See `.claude/docs/AUTH.md`.
- **ORM:** SQLAlchemy 2.0 async (`AsyncSession`)
- **Driver:** psycopg3 (`psycopg[binary]`) — prefix: `postgresql+psycopg://`
- **Migrations:** Alembic — always create a migration, never raw schema changes
- **DB:** Supabase managed Postgres
- **Cache:** Redis (Railway) — rate limiting, passkey attempts, notification cooldowns
- **Jobs:** APScheduler inside FastAPI — do NOT introduce Celery
- **Email:** Resend (free tier)
- **Payments:** None — no payment SDK, no payouts, no webhooks. The platform processes no money.
- **Storage:** Cloudinary (images only)
- **Logging:** Python `logging` module. No `print()`. See logging rules below.
- **Deployment:** Railway
- **Dev URL:** `http://localhost:8000`

### Database rules
- Parameterized queries only via SQLAlchemy ORM. Never string-interpolate user input.
- Search via WHERE + ILIKE. No vector search, no pg_trgm, no full-text engine.
- Never make raw schema changes — always Alembic migration.

---

## Project structure

```
textbook-exchange/
├── .claude/
│   ├── CLAUDE.md
│   ├── docs/
│   │   ├── AUTH.md          # verify_token, Supabase setup, DB trigger, passkey hashing
│   │   ├── TRANSACTIONS.md   # Passkey verification, transaction completion, ratings, reputation
│   │   └── SCHEMA.md         # Full table definitions, constraints, debug queries
│   └── specs/
│       ├── decisions/
│       │   └── DECISIONS.md
│       ├── infrastructure/
│       │   ├── environments.md
│       │   ├── deployment.md
│       │   ├── logging.md
│       │   └── jobs.md
│       ├── product/
│       │   ├── overview.md
│       │   ├── user-flows.md
│       │   ├── content-policy.md
│       │   └── notifications.md
│       └── technical/
│           ├── auth.md
│           ├── schema.md
│           ├── payment.md
│           ├── chat.md
│           ├── search.md
│           ├── image-upload.md
│           ├── passkey.md
│           └── api.md
├── frontend/
│   ├── app/
│   │   ├── (auth)/
│   │   ├── (marketplace)/
│   │   │   ├── listings/page.jsx          # SSR
│   │   │   └── listings/[id]/page.jsx     # SSR
│   │   ├── dashboard/                     # Client — buyer+seller unified
│   │   ├── chat/[id]/page.jsx             # Client — polling
│   │   └── api/
│   ├── components/
│   │   ├── ui/                            # Shadcn/ui — do not edit
│   │   ├── listings/
│   │   ├── chat/
│   │   └── shared/
│   ├── lib/
│   │   ├── supabase/
│   │   │   ├── client.js
│   │   │   └── server.js
│   │   ├── api.js
│   │   ├── queries.js
│   │   └── utils.js
│   ├── middleware.js
│   └── constants/
│       ├── examCategories.js
│       ├── listingTypes.js
│       ├── subjects.js
│       └── conditions.js
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   ├── security.py
│   │   │   ├── redis.py
│   │   │   └── logging.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── routers/
│   │   ├── services/
│   │   └── jobs/
│   │       └── scheduler.py
│   ├── alembic/
│   ├── tests/
│   └── pyproject.toml
└── docker-compose.yml
```

---

## SSR vs TanStack Query

**SSR (Server Components):** `/listings`, `/listings/[id]`, `/users/[id]`, marketing pages — SEO, Google indexing.

**TanStack Query (Client Components):** Chat polling (`refetchInterval: 4000`), passkey submission, dashboard, listing availability status.

---

## API endpoints

**Base URL dev:** `http://localhost:8000/v1`
**Base URL prod:** `https://api.yourdomain.com/v1`
**Auth header:** `Authorization: Bearer <supabase_access_token>`

No auth endpoints on FastAPI. All auth goes directly to Supabase.

```
GET    /listings                  public, ?q=&exam_category=&subject=&city=&condition=&listing_type=
POST   /listings                  protected
GET    /listings/{id}             public
PATCH  /listings/{id}             protected, owner only
DELETE /listings/{id}             protected, owner only (soft delete)
PATCH  /listings/{id}/passkey     protected, owner only — regenerate passkey hash

POST   /reports                   protected — report a listing (content policy)

GET    /conversations             protected
POST   /conversations             protected
GET    /conversations/{id}/messages   protected, polling
POST   /conversations/{id}/messages   protected
PATCH  /conversations/{id}/messages/read  protected

POST   /transactions/verify-passkey   protected — buyer enters 8-digit code; marks listing SOLD, records verified transaction
GET    /transactions                  protected — caller's transactions as buyer and seller
POST   /transactions/{id}/rating       protected, buyer only, once — 1-5 stars + optional review

GET    /users/me                  protected
PATCH  /users/me                  protected
GET    /users/{id}                public
```

---

## Chat

- Polling only — 4 seconds. No WebSockets ever.
- Rate limit: 100 messages/user/conversation/hour (Redis)
- Email: first message in new conversation only
- Never return contact info in chat responses
- Archive conversations on listing delete — never delete

---

## Canonical constants

### Exam categories
```
JEE_MAINS | JEE_ADVANCED | NEET_UG | NEET_PG
UPSC_CSE | UPSC_OTHER
CA_FOUNDATION | CA_INTERMEDIATE | CA_FINAL
GATE | GMAT | GRE | IELTS | CUET
CLASS_9 | CLASS_10 | CLASS_11 | CLASS_12
OTHER
```

### Listing types (DB CHECK enforced)
```
BOOK    — Published books (HC Verma, NCERT, RD Sharma)
NOTES   — Handwritten or self-created notes, revision sheets
MODULE  — Coaching modules, DPPs, test series (Allen, Aakash, FIITJEE, PW)
BUNDLE  — Multiple items sold together
```

### Conditions
```
A — Like new (no markings, no wear)
B — Good (light use, minimal highlighting, pages intact)
C — Acceptable (heavy use, highlighting, fully readable)
```

### Transactions
```
No statuses. A `transactions` row exists only when a buyer enters the correct passkey
at the meetup — it IS the record of a completed, verified exchange (one row per sold
listing). No pending/initiated/payment state. Verification is atomic: the listing is
marked SOLD, books_sold/books_bought increment, and the buyer may then rate the seller.
```

### Reputation
```
books_sold     — seller's verified completed sales (== verified transactions)
books_bought   — buyer's verified completed purchases
seller_rating  — NUMERIC(3,2) average of 1-5 ratings, recomputed on each rating insert
is_verified    — blue badge, auto-set TRUE once books_sold >= 10 (no longer OAuth-email based)
```

### Redis keys
```
passkey_attempts:{listing_id}:{buyer_id}    integer, TTL 7 days (3 attempts max)
chat_rate:{conversation_id}:{sender_id}     integer, TTL 1 hour
chat:{conversation_id}                      cached messages, TTL 30s
report_rate:{reporter_id}                   integer, TTL 1 hour
```

---

## Code conventions

### JavaScript (frontend)
- `.js` and `.jsx` only — no TypeScript
- TanStack Query for all client server-state
- `formatPrice(rupees)` always — never raw price values in JSX
- No `console.log` in committed code

### Python (backend)
- Python 3.11+, Pydantic v2
- All DB ops async — no sync SQLAlchemy in routes
- Logic in `services/` — routers handle HTTP only
- Parameterized queries only — never f-string SQL
- Prices in whole rupees, display-only — the platform never collects or transfers money
- `user["sub"]` is always the user UUID from JWT
- `logging.getLogger(__name__)` at top of every module

---

## Logging rules

**Log:** every request, every transaction completion, every JWT failure, every APScheduler run, every email send, every Redis failure.

**Never log:** passkey plaintext, passkey hash, JWT strings, `PASSKEY_HMAC_SECRET`, user PII beyond UUID.

---

## Environment variables

### Backend (.env)
```
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db
REDIS_URL=redis://default:pass@host:6379
PASSKEY_HMAC_SECRET=<32+ random bytes hex>
CLOUDINARY_CLOUD_NAME=xxx
CLOUDINARY_API_KEY=xxx
CLOUDINARY_API_SECRET=xxx
RESEND_API_KEY=re_xxx
FRONTEND_URL=http://localhost:3000
ENVIRONMENT=development
```

### Frontend (.env.local)
```
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
NEXT_PUBLIC_API_URL=http://localhost:8000/v1
API_URL=http://localhost:8000/v1
```

**Hard rules:** `SUPABASE_SERVICE_ROLE_KEY`, `PASSKEY_HMAC_SECRET` — backend only, never exposed. Never commit `.env`.

---

## Security rules (non-negotiable)

1. Never expose seller contact info in any API response
2. Supabase session in httpOnly cookies — never localStorage
3. Validate ownership before every mutation: `listing.seller_id == user["sub"]`
4. Image uploads direct to Cloudinary — never through FastAPI
5. Parameterized queries only — never string-interpolate user input
6. CORS: allow only `FRONTEND_URL` in production — never `*`
7. `SUPABASE_SERVICE_ROLE_KEY` — background jobs only, never in user-facing request logic. Approved exceptions are limited to server-internal email resolution via `fetch_user_email` (needed because `public.users` has no email column — Supabase Auth owns identity), each dispatched as a post-response `BackgroundTask` so the lookup never runs inside the request/response path: (a) the chat first-message seller notification; (b) the sale-complete notification after a passkey is verified. The service-role value is never logged, returned, or exposed to the client. See DECISIONS.md.
8. `PASSKEY_HMAC_SECRET` — never logged, never in responses
9. `hmac.compare_digest` for all hash comparisons — never `==`
10. Listing completion is atomic and one-way: `UPDATE ... WHERE is_available = TRUE` selects the single winning buyer; a sold listing can never be reopened
11. Only the buyer can rate, only after a verified passkey, once per transaction (DB-enforced)
12. Hide listing immediately on piracy/copyright report

---

## Moderation (v1 — manual via Supabase dashboard)

```sql
-- Hide listing
UPDATE listings SET is_available = FALSE WHERE id = '<id>';

-- Permanently remove
UPDATE listings SET is_available = FALSE, sold_at = now() WHERE id = '<id>';
```

Block user: Supabase Auth dashboard → Users → Disable.

Remove immediately: pirated scans, contact info in listing text, abusive content.

---

## What NOT to build in v1

Admin panel · automated moderation · shipping/courier · mobile app · WebSockets ·
email/password auth · automated disputes · Aadhaar verification · buyer ratings ·
ML/vector search · multi-language · referrals · Celery · JWKS caching ·
platform fee · featured listings · anything not in this file or .claude/

---

## Python environment

**Single shared venv at project root — always use it, never global Python.**

```
Location:   .venv/                         (project root)
Python:     3.11
Activate:   .venv\Scripts\activate         (Windows PowerShell)
Python bin: .venv\Scripts\python.exe
Pip:        .venv\Scripts\pip
Alembic:    .venv\Scripts\alembic
Uvicorn:    .venv\Scripts\uvicorn
```

- `requirements.txt` at project root — source of truth for all backend packages.
- When running any backend command (alembic, uvicorn, pytest, python -c ...) always use `.venv\Scripts\<cmd>` or activate first.
- When adding a new dependency: add to `requirements.txt` **and** `backend/pyproject.toml`, then run `.venv\Scripts\pip install -r requirements.txt`.

---

## Local development

```bash
docker-compose up -d

# Backend — use project-root venv, not a separate one
# Activate first:  .venv\Scripts\activate  (PowerShell)
.venv\Scripts\pip install -r requirements.txt
cd backend && ..\\.venv\Scripts\alembic upgrade head
..\\.venv\Scripts\uvicorn app.main:app --reload --port 8000

cd frontend && npm install && npm run dev
```

Use real Supabase project for local auth — JWKS endpoint must be reachable.

---

## Before adding any feature

1. In v1 scope? 2. New dependency? 3. Touches the passkey/transaction flow? 4. Exposes PII? 5. One person, one day?

If any answer is concerning — discuss first.
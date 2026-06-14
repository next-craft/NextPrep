# Spec 03: Content Policy

## Purpose

This spec is the single source of truth for **what may be sold** on the marketplace,
**what is prohibited**, **how the two-person team moderates** listings manually, and
**how any signed-in user reports** a violating listing. The platform is India's
peer-to-peer marketplace for physical exam books, notes, and coaching modules exchanged
via in-person meetup. Because listings are user-generated and the exam-prep space is rife
with pirated scans, bulk photocopies, and bound PDF reproductions, the platform carries
real copyright-liability exposure. The allowed/prohibited catalogue is referenced piecemeal
across Spec 01 (Overview) and `CLAUDE.md`, but no consolidated content policy exists, and —
critically — there is **no in-app way for a user to flag a bad listing** even though
security rule 13 requires "hide listing immediately on piracy/copyright report." This spec
closes that gap: it consolidates the catalogue, defines the manual moderation workflow
against the existing `is_available` / `deleted_at` soft-delete columns, and specifies a
lightweight reporting mechanism (a new `reports` table, a single `POST /v1/reports`
endpoint, and a report button on the listing page) that feeds a manual triage queue the
team works from the Supabase dashboard. No admin panel and no automated moderation are
introduced — both are explicitly out of v1 scope.

## Depends on

- **Spec 01 — Overview**: seeds the allowed/prohibited catalogue; this spec consolidates it.
- **Schema implementation (`06-schema`)**: the `listings` table and its `is_available`,
  `sold_at`, and `deleted_at` columns plus the
  `CHECK (NOT (is_available = TRUE AND (sold_at IS NOT NULL OR deleted_at IS NOT NULL)))`
  constraint. The new `reports` table references `listings.id` and `users.id`.
- **Auth (`07-auth`)**: the `verify_token` dependency and `user["sub"]` (reporter UUID).
- **Listings CRUD (`14-listings-crud`)**: the existing soft-delete service pattern
  (`is_available = False`, `deleted_at = now()`) reused for moderation removal.

## Scope

**In scope**
- The canonical list of allowed listing categories with concrete India-exam examples.
- The canonical list of prohibited listings and the rationale for each.
- The canonical `reports` report-reason constant (DB CHECK + frontend mirror).
- A new `reports` table (Alembic migration) for tracking submitted reports.
- A single protected `POST /v1/reports` endpoint, its validation, idempotency, rate
  limiting, and logging.
- The manual moderation workflow run from the Supabase dashboard (triage, temporary hide,
  permanent removal, report close-out, user block).
- The in-app report UX (button + dialog) on the listing detail page.

**Out of scope (explicitly)**
- Admin panel of any kind — moderation is dashboard-only (DECISIONS.md).
- Automated moderation, keyword auto-detection, or auto-hide on a report threshold —
  listed under "What NOT to build in v1" in `CLAUDE.md`.
- The actual seller-notification email on removal — **deferred** to the future
  `notifications.md` spec; only the policy is stated here.
- Buyer ratings, appeals UI, or dispute automation — not in v1.

## Allowed listings (canonical)

Only **physical** study material exchanged via in-person meetup. India market only,
INR (whole rupees) only. The `listing_type` is one of four DB-CHECK-enforced values:

| `listing_type` | What it covers | Examples |
| -------------- | -------------- | -------- |
| `BOOK` | Published, original study books | HC Verma, NCERT, RD Sharma, Arihant, MTG, Cengage |
| `NOTES` | Handwritten or self-created notes, revision sheets, formula sheets | Personal class notes, self-made formula sheets |
| `MODULE` | Original coaching modules, DPPs, printed test series | Allen DLPs, Aakash modules, FIITJEE RSM, PW printed material |
| `BUNDLE` | Multiple original items sold together | A full JEE-prep set: book + notes + module bundle |

Material type is a **filter**, not a separate section — books, notes, and modules appear
together in one unified search stream.

## Prohibited listings

The following must never be listed, and are removed immediately on detection or report:

| Prohibited | Why |
| ---------- | --- |
| Pirated scans printed and sold as physical material | Copyright infringement, legal exposure |
| Photocopied books sold in bulk | Copyright infringement; common but illegal |
| Unauthorized PDF reproductions printed/bound | Copyright infringement |
| Digital files of any kind (PDF, e-book, drive link) | Platform is physical-only, in-person meetup |
| Non-study-material items | Out of marketplace scope |
| Contact info embedded in listing text (phone, email, social handle) | Violates security rule 1; contact is chat-only |
| Abusive, harassing, or otherwise illegal content | Trust & safety |

## Report reasons (canonical constant)

A submitted report carries exactly one reason from this fixed set. It is enforced by a DB
`CHECK` constraint and mirrored verbatim in `frontend/constants/reportReasons.js`:

```
PIRACY               — pirated scan, photocopy, or unauthorized PDF reproduction
CONTACT_INFO         — phone/email/social handle in the listing text
SPAM                 — duplicate, irrelevant, or misleading listing
NOT_STUDY_MATERIAL   — item is not study material
PROHIBITED           — other disallowed content
ABUSIVE              — abusive, harassing, or illegal content
OTHER                — anything else (free-text note encouraged)
```

## The `reports` table (new)

Created via Alembic migration — never a raw schema change. Prices/PII are not stored here;
only UUIDs and the chosen reason.

```sql
CREATE TABLE public.reports (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id  UUID NOT NULL REFERENCES public.listings(id) ON DELETE CASCADE,
    reporter_id UUID NOT NULL REFERENCES public.users(id)    ON DELETE CASCADE,
    reason      TEXT NOT NULL CHECK (reason IN (
                    'PIRACY', 'CONTACT_INFO', 'SPAM', 'NOT_STUDY_MATERIAL',
                    'PROHIBITED', 'ABUSIVE', 'OTHER')),
    note        TEXT,
    status      TEXT NOT NULL DEFAULT 'open' CHECK (status IN (
                    'open', 'actioned', 'dismissed')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_report_once UNIQUE (listing_id, reporter_id)
);

CREATE INDEX ix_reports_status ON public.reports (status, created_at DESC);
```

- `uq_report_once` — one report per (listing, reporter); prevents a single user from
  inflating a queue against one listing.
- `status` — the moderator's triage state: `open` (untriaged), `actioned` (listing
  hidden/removed), `dismissed` (no violation found).
- `ix_reports_status` — supports the moderator's "open reports, newest first" query.

### SQLAlchemy model

```python
# backend/app/models/report.py
import uuid
from sqlalchemy import (
    Column, String, ForeignKey, TIMESTAMP, CheckConstraint, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base  # match the Base import used by listing.py


class Report(Base):
    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    listing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("public.listings.id", ondelete="CASCADE"),
        nullable=False,
    )
    reporter_id = Column(
        UUID(as_uuid=True),
        ForeignKey("public.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    reason = Column(String, nullable=False)
    note = Column(String)
    status = Column(String, nullable=False, server_default="open")
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (
        CheckConstraint(
            "reason IN ('PIRACY','CONTACT_INFO','SPAM','NOT_STUDY_MATERIAL',"
            "'PROHIBITED','ABUSIVE','OTHER')",
            name="ck_report_reason",
        ),
        CheckConstraint(
            "status IN ('open','actioned','dismissed')",
            name="ck_report_status",
        ),
        UniqueConstraint("listing_id", "reporter_id", name="uq_report_once"),
    )
```

## `POST /v1/reports` endpoint

Protected. Any signed-in user may report any listing (a user does **not** need to own the
listing to report it — ownership checks apply only to mutations of the listing itself).

### Request / response schema

```python
# backend/app/schemas/report.py
import uuid
from typing import Optional, Literal
from pydantic import BaseModel, Field

ReportReason = Literal[
    "PIRACY", "CONTACT_INFO", "SPAM", "NOT_STUDY_MATERIAL",
    "PROHIBITED", "ABUSIVE", "OTHER",
]


class ReportCreate(BaseModel):
    listing_id: uuid.UUID
    reason: ReportReason
    note: Optional[str] = Field(default=None, max_length=1000)


class ReportAck(BaseModel):
    # Deliberately minimal — never expose report counts, status, or other reporters.
    received: bool = True
```

### Router (HTTP only)

```python
# backend/app/routers/reports.py
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.core.security import verify_token
from app.schemas.report import ReportCreate, ReportAck
from app.services import report_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", response_model=ReportAck, status_code=201)
async def create_report(
    data: ReportCreate,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    user=Depends(verify_token),
):
    return await report_service.create_report(
        db, redis, reporter_id=user["sub"], data=data
    )
```

### Service (logic)

```python
# backend/app/services/report_service.py
import logging
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listing import Listing
from app.models.report import Report
from app.schemas.report import ReportCreate, ReportAck

logger = logging.getLogger(__name__)

REPORT_RATE_LIMIT = 20          # reports per reporter per hour
REPORT_RATE_TTL = 3600          # seconds


async def create_report(
    db: AsyncSession, redis, reporter_id: str, data: ReportCreate
) -> ReportAck:
    # 1. Rate limit per reporter (anti-abuse / anti-DoS).
    key = f"report_rate:{reporter_id}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, REPORT_RATE_TTL)
    if count > REPORT_RATE_LIMIT:
        logger.warning("report_rate_limited reporter=%s", reporter_id)
        raise HTTPException(status_code=429, detail="Too many reports. Try again later.")

    # 2. Listing must exist and not already be removed/sold.
    listing = await db.scalar(
        select(Listing).where(
            Listing.id == data.listing_id,
            Listing.deleted_at.is_(None),
        )
    )
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")

    # 3. Idempotent: a duplicate (listing, reporter) is silently accepted.
    #    Never reveal whether a prior report exists.
    existing = await db.scalar(
        select(Report).where(
            Report.listing_id == data.listing_id,
            Report.reporter_id == UUID(reporter_id),
        )
    )
    if existing:
        logger.info("report_duplicate listing=%s", data.listing_id)
        return ReportAck()

    report = Report(
        listing_id=data.listing_id,
        reporter_id=UUID(reporter_id),
        reason=data.reason,
        note=data.note,
    )
    db.add(report)
    await db.commit()

    # No PII beyond UUIDs; never log the note (may contain free text).
    logger.info("report_created listing=%s reason=%s", data.listing_id, data.reason)
    return ReportAck()
```

**Guarantees:**
- Never auto-hides the listing — moderation is a human decision (no automated moderation).
- Never returns or leaks report counts, status, or other reporters' identities.
- Idempotent on duplicate `(listing_id, reporter_id)` — returns the same minimal ack.
- Rate-limited via Redis so reporting cannot be used to enumerate listings or DoS the queue.

## Moderation workflow (manual, Supabase dashboard)

V1 volume is low enough for manual moderation; an admin panel is premature (DECISIONS.md).
The team works the queue directly in the Supabase SQL editor / table view.

**1. Triage queue — open reports, newest first:**

```sql
SELECT r.id, r.listing_id, r.reason, r.note, r.created_at, l.title, l.seller_id
FROM reports r
JOIN listings l ON l.id = r.listing_id
WHERE r.status = 'open'
ORDER BY r.created_at DESC;
```

**2. Temporary hide** (under review, or a borderline case the seller may correct) — the
listing leaves search but is not deleted:

```sql
UPDATE listings SET is_available = FALSE WHERE id = '<id>';
```

**3. Permanent removal** (confirmed violation) — soft-delete using `deleted_at`:

```sql
UPDATE listings SET is_available = FALSE, deleted_at = now() WHERE id = '<id>';
```

> **Note — use `deleted_at`, not `sold_at`, for moderation removal.** An older moderation
> snippet in `CLAUDE.md` uses `sold_at = now()` for permanent removal. That predates the
> `deleted_at` column added in the schema implementation. Per DECISIONS.md, a removed
> listing is **not** a sold listing (`sold_at` stays `NULL`, `total_sales` is never
> incremented). The public listings query already filters on
> `is_available = TRUE AND deleted_at IS NULL`, so `deleted_at` cleanly hides the listing
> while keeping sale semantics intact. The `CLAUDE.md` snippet should be read as
> `deleted_at` now that the column exists — a candidate entry for DECISIONS.md.

**4. Close out the report(s) for that listing:**

```sql
-- Confirmed violation, listing removed/hidden:
UPDATE reports SET status = 'actioned'   WHERE listing_id = '<id>' AND status = 'open';

-- No violation found:
UPDATE reports SET status = 'dismissed'  WHERE listing_id = '<id>' AND status = 'open';
```

**5. Block a repeat-offender user** — Supabase Auth dashboard → Users → Disable. A disabled
user can no longer obtain a valid Supabase session, so every protected endpoint rejects them.

**Immediate-removal categories (no waiting, per security rule 13):** pirated scans
(`PIRACY`), contact info embedded in listing text (`CONTACT_INFO`), and abusive/illegal
content (`ABUSIVE`) are removed on detection or first credible report.

## Seller notification on removal

**Policy:** when a seller's listing is hidden or removed by moderation, the seller is
informed that their listing was removed and why (category, not reporter identity). The
seller also sees the listing disappear from their dashboard.

**Mechanism: deferred.** The actual email (Resend) and its copy are out of scope for this
spec and belong to the future `notifications.md` spec. This spec only records the policy so
the notifications spec can implement it consistently. No notification code is built here.

## Frontend report UX

- A **"Report listing"** action is added to the action area of the listing detail page
  (`/listings/[id]`), which currently has no report control.
- `ReportListingDialog.jsx` is a client component (a Shadcn/ui dialog) containing:
  - a reason `<select>` populated from `frontend/constants/reportReasons.js`,
  - an optional free-text note (`<= 1000` chars),
  - a submit button wired to a **TanStack Query mutation** that calls `POST /v1/reports`
    through the existing `lib/api.js` axios client (which already injects the Supabase
    `Authorization: Bearer <token>` header).
- **Logged-out users**: the report action prompts sign-in, reusing the existing
  "Continue with Google" pattern already present on the listing page.
- **Success**: toast — `"Thanks — our team will review this listing."` No report counts,
  status, or other reporters are ever shown. A duplicate report shows the same success
  toast (idempotent).
- **Rate-limited (429)**: toast — `"You've reported too many listings. Please try again later."`

### `reportReasons.js`

```javascript
// frontend/constants/reportReasons.js
export const REPORT_REASONS = [
  { value: 'PIRACY', label: 'Pirated scan, photocopy, or unauthorized PDF' },
  { value: 'CONTACT_INFO', label: 'Phone/email/social handle in the listing' },
  { value: 'SPAM', label: 'Spam, duplicate, or misleading' },
  { value: 'NOT_STUDY_MATERIAL', label: 'Not study material' },
  { value: 'PROHIBITED', label: 'Other prohibited content' },
  { value: 'ABUSIVE', label: 'Abusive, harassing, or illegal' },
  { value: 'OTHER', label: 'Something else' },
]
```

## Files to create

- `.claude/specs/product/03-content-policy.md` — this spec.
- `backend/app/models/report.py` — `Report` SQLAlchemy model.
- `backend/app/schemas/report.py` — `ReportCreate`, `ReportAck` Pydantic v2 schemas.
- `backend/app/services/report_service.py` — `create_report` logic (rate limit, validation,
  idempotency, persist, log).
- `backend/app/routers/reports.py` — `POST /reports` router (HTTP only).
- `backend/alembic/versions/<rev>_create_reports.py` — migration creating the `reports`
  table, CHECK constraints, unique constraint, and `ix_reports_status` index.
- `frontend/constants/reportReasons.js` — report-reason options mirroring the DB CHECK.
- `frontend/components/listings/ReportListingDialog.jsx` — report dialog + mutation.

## Files to modify

- `backend/app/models/__init__.py` — add `from app.models.report import Report`.
- `backend/app/main.py` — `app.include_router(reports.router, prefix="/v1")`.
- `frontend/app/(marketplace)/listings/[id]/page.jsx` — add the "Report listing" action to
  the action area; render `ReportListingDialog`.
- `frontend/lib/api.js` (and/or `frontend/lib/queries.js`) — add the `createReport` mutation
  helper used by the dialog.
- `.claude/CLAUDE.md` — add `POST /reports   protected` to the API endpoints block, and add
  `report_rate:{reporter_id}   integer, TTL 1 hour` to the Redis keys block.

## New dependencies

No new dependencies. Reuses FastAPI, SQLAlchemy 2.0 async, Alembic, Redis, Shadcn/ui, and
TanStack Query — all already in the stack. (Resend is not used here; notifications are
deferred.)

## Security considerations

The following `CLAUDE.md` security rules apply specifically to this feature:

- **Rule 1 — never expose seller contact info**: report payloads and acks never echo seller
  contact details; the triage query exposes `seller_id` (a UUID) only inside the Supabase
  dashboard, never via the API.
- **Rule 5 — validate ownership before every mutation**: reporting does **not** require
  ownership (any signed-in user may report), but all listing-state mutations
  (hide/remove) happen server-internally via the dashboard, never through a user-facing
  mutation endpoint. The report endpoint itself creates only a `reports` row scoped to
  `reporter_id = user["sub"]`.
- **Rule 7 — parameterized queries only**: all DB access uses the SQLAlchemy ORM; no user
  input is string-interpolated.
- **Rule 13 — hide listing immediately on piracy/copyright report**: encoded in the
  immediate-removal categories (`PIRACY`, `CONTACT_INFO`, `ABUSIVE`).
- **Logging rules**: log every report (`report_created`/`report_duplicate`) and every rate
  limit (`report_rate_limited`) with the listing UUID and reason only — never the free-text
  note, never reporter PII beyond the UUID.
- **Anti-abuse**: the Redis rate limit (`report_rate:{reporter_id}`, 20/hour) plus the
  idempotent `uq_report_once` constraint prevent the report endpoint from being used to
  enumerate listings or flood the moderation queue.

## Definition of done

- [ ] Alembic migration creates `public.reports` with the `reason` CHECK, `status` CHECK,
      `uq_report_once` unique constraint, and `ix_reports_status` index; `alembic upgrade
      head` runs clean and `alembic downgrade -1` drops the table.
- [ ] `POST /v1/reports` with a valid `{listing_id, reason}` body returns `201` and a row
      appears in `reports` with `status = 'open'`.
- [ ] An invalid `reason` value returns `422` (Pydantic `Literal` rejection).
- [ ] A `listing_id` that does not exist or is soft-deleted returns `404`.
- [ ] Submitting the same `(listing_id, reporter_id)` twice returns the same minimal ack and
      does **not** create a second row (idempotent).
- [ ] Exceeding 20 reports/hour for one reporter returns `429`.
- [ ] The endpoint response body never contains report counts, status, or other reporters.
- [ ] A "Report listing" control is visible on `/listings/[id]`; submitting the dialog shows
      the success toast and creates a report; logged-out users are prompted to sign in.
- [ ] The reason options shown in the UI exactly match the DB CHECK list.
- [ ] Manual moderation SQL verified against a test listing: temporary hide
      (`is_available = FALSE`) removes it from `GET /v1/listings`; permanent removal
      (`is_available = FALSE, deleted_at = now()`) does the same and leaves `sold_at` NULL;
      closing reports sets `status` to `actioned`/`dismissed`.
- [ ] The allowed and prohibited catalogues are documented in this spec and consistent with
      Spec 01 and `CLAUDE.md`.
- [ ] `CLAUDE.md` updated with the `POST /reports` endpoint and the `report_rate` Redis key.

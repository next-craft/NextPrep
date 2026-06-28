# Spec 15: College Communities

## Purpose

This spec adds **college** as a discovery dimension to the marketplace: a seller's
campus, attached to their profile and to each listing, so buyers can find study
material from people at their own college and arrange an easier in-person meetup.
It is the natural next layer below the state → district (City) location feature
shipped in migration `0011` — district narrows to a city, college narrows to a
campus. A "College" filter joins the existing unified search stream on `/listings`
(alongside exam, type, condition, subject, state, city), and SSR `/colleges` and
`/colleges/[slug]` pages give each campus an indexable, read-only view of its active
listings — the user-facing "community" surface.

Critically, **"community" here means emergent discovery, not a social network.**
There are no members, no feed, no posts, no group chat, and no moderation queue —
each of those collides with settled v1 decisions (no admin panel, no automated
moderation, no WebSockets, no non-listing UGC). A college is a passive, filterable
piece of metadata, exactly like `city` or `exam_category`.

To keep the filter usable, college values are **canonical**: users pick from a
seeded `colleges` table via a typeahead, so 2,000 students at one campus all resolve
to the same `college_id` instead of fragmenting into "IITB" / "IIT-B" / "iit bombay".
A user whose campus isn't listed can type it once; that free text is stored as a
non-canonical `college_other` label (shown but **not** part of the filter) and
surfaces in a dashboard queue for manual promotion to a real `colleges` row — the
same "fix unmapped rows later" approach `0011` used for cities.

---

## Depends on

- **Spec 06 — Schema / migration `0011`:** `state`/`city` columns on `listings` and
  `public.users`, the `is_valid_state` / `is_valid_city` igod constants pattern, and
  the Alembic add-column + backfill migration shape this spec mirrors.
- **Spec 14 — Listings CRUD:** `listings` model, `ListingCreate/Update/Out` schemas,
  `listing_service.get_listings` filter chain, `listings` router query params,
  `FILTER_KEYS`, `ListingFilters`, `CreateListingForm`, `ListingCard`, `/listings`
  and `/listings/[id]` SSR pages.
- **Spec 07 — Auth:** `verify_token`, `optional_user`, `user["sub"]` UUID, the
  `public.users` row + `handle_new_user` trigger.
- **Users endpoints:** existing `GET/PATCH /users/me`, `GET /users/{id}`,
  `user_service.update_user` (`model_dump(exclude_unset=True)` setattr loop).

---

## Scope

**In scope:**
- A canonical `colleges` reference table, seeded with an initial campus list.
- Nullable `college_id` FK + nullable `college_other` text on both `listings` and
  `public.users` (a campus is always optional).
- `college_id` / `college_other` accepted on listing create/edit and on the user
  profile (`PATCH /users/me`); profile college auto-fills the new-listing form but
  is fully overridable per listing.
- A `college` filter on `GET /listings` (by college **slug**), wired through
  `FILTER_KEYS` so the SSR page + desktop + mobile filters pick it up.
- `GET /colleges?q=` typeahead search and `GET /colleges/{slug}` (college + its
  active listings) endpoints.
- SSR `/colleges` index (campuses with ≥1 active listing) and `/colleges/[slug]`
  campus page (read-only scoped listing stream, cloning the `/users/[id]` pattern).
- A reusable `CollegeCombobox` typeahead component with a "my college isn't listed"
  free-text fallback; a college chip on listing cards, listing detail, and profiles.
- A documented manual promotion workflow (Supabase dashboard SQL) for turning
  `college_other` submissions into canonical `colleges` rows + backfilling.

**Explicitly out of scope (collides with v1 — do NOT build):**
- College membership / join-leave, roles, or any `college_members` table.
- A per-college feed, board, posts, comments, likes, or follows (no non-listing UGC).
- Group chat or any change to the 1:1 listing-scoped polling chat.
- College-scoped notifications (in-app notifications are deferred; email is reserved
  for the two transactional cases).
- Any verification of college affiliation (it is self-asserted, like `city`). College
  is **never** tied to `is_verified` (that is the `books_sold >= 10` sales badge).
- An admin panel for promoting suggestions — promotion is manual dashboard SQL.

---

## Data model

### New table: `colleges` (canonical campus list)

```sql
id          UUID PRIMARY KEY DEFAULT gen_random_uuid()
slug        TEXT NOT NULL UNIQUE        -- URL/filter key, e.g. "iit-bombay"
name        TEXT NOT NULL UNIQUE        -- display name, e.g. "IIT Bombay"
state       TEXT                        -- igod state/UT for disambiguation (nullable)
city        TEXT                        -- igod district for disambiguation (nullable)
is_active   BOOLEAN NOT NULL DEFAULT TRUE   -- soft-hide a college without deleting rows
created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
```

- `slug` and `name` are unique — the whole point is one canonical value per campus.
- `is_active = FALSE` hides a college from search/typeahead without breaking existing
  `listings.college_id` references (mirrors how listings are hidden, not deleted).

### Changes to `listings`

```sql
college_id     UUID REFERENCES colleges(id) ON DELETE SET NULL   -- nullable
college_other  TEXT                                              -- nullable, free text
```

### Changes to `public.users`

```sql
college_id     UUID REFERENCES colleges(id) ON DELETE SET NULL   -- nullable
college_other  TEXT                                              -- nullable, free text
```

**Invariant (enforced app-side, see validators):** for any row, **at most one** of
`college_id` / `college_other` is set. `college_id` is the canonical, filterable
campus; `college_other` is an un-promoted free-text label that is displayed but never
matches the filter. `ON DELETE SET NULL` means retiring a college never deletes a
user or listing.

### No separate suggestions table — the holding pen is `college_other`

Rather than a `college_suggestions` table, the "not listed" queue is simply the set
of rows with `college_id IS NULL AND college_other IS NOT NULL`. A dashboard GROUP BY
(see Promotion workflow) surfaces the most-requested campuses. This keeps the feature
to one new table and avoids a second thing to keep in sync — consistent with the
project's minimalism.

### Deliberate deviation from the `state`/`city` pattern

`state`/`city` are denormalized **TEXT** validated app-side against the igod
constants. College instead uses a **table + FK**, because (a) `/colleges/[slug]`
needs stable slugs and (b) the campus list must grow via the Supabase dashboard
**without a code deploy**, which a hardcoded constant file cannot do. This deviation
must be recorded in `DECISIONS.md` (see Files to modify).

### Migration `0012`

```python
# backend/alembic/versions/0012_add_colleges.py
"""Add colleges table + college_id/college_other on listings & users

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

# (slug, name, state, district) — seed list. Source/curation: see spec §"Seeding".
COLLEGES_SEED = [
    ("iit-bombay", "IIT Bombay", "Maharashtra", "Mumbai Suburban"),
    ("iit-delhi", "IIT Delhi", "Delhi", "South"),
    # ... full seed list ...
]


def upgrade() -> None:
    op.create_table(
        "colleges",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("state", sa.String()),
        sa.Column("city", sa.String()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("slug", name="uq_college_slug"),
        sa.UniqueConstraint("name", name="uq_college_name"),
    )
    # Typeahead search hits name; filter resolves by slug.
    op.create_index("ix_colleges_name", "colleges", ["name"])

    # Nullable FK + free-text fallback on listings
    op.add_column("listings", sa.Column("college_id", UUID(as_uuid=True), nullable=True))
    op.add_column("listings", sa.Column("college_other", sa.String(), nullable=True))
    op.create_foreign_key("fk_listings_college", "listings", "colleges",
                          ["college_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_listings_college_id", "listings", ["college_id"])

    # Same on public.users (schema='public' — the one-table gotcha from 0011)
    op.add_column("users", sa.Column("college_id", UUID(as_uuid=True), nullable=True),
                  schema="public")
    op.add_column("users", sa.Column("college_other", sa.String(), nullable=True),
                  schema="public")
    op.create_foreign_key("fk_users_college", "users", "colleges",
                          ["college_id"], ["id"],
                          source_schema="public", ondelete="SET NULL")

    # Seed canonical colleges
    conn = op.get_bind()
    for slug, name, state, city in COLLEGES_SEED:
        conn.execute(
            sa.text("INSERT INTO colleges (slug, name, state, city) "
                    "VALUES (:slug, :name, :state, :city) ON CONFLICT (slug) DO NOTHING"),
            {"slug": slug, "name": name, "state": state, "city": city},
        )


def downgrade() -> None:
    op.drop_constraint("fk_users_college", "users", schema="public", type_="foreignkey")
    op.drop_column("users", "college_other", schema="public")
    op.drop_column("users", "college_id", schema="public")
    op.drop_constraint("fk_listings_college", "listings", type_="foreignkey")
    op.drop_index("ix_listings_college_id", table_name="listings")
    op.drop_column("listings", "college_other")
    op.drop_column("listings", "college_id")
    op.drop_index("ix_colleges_name", table_name="colleges")
    op.drop_table("colleges")
```

No backfill of existing `listings`/`users` — college is new and optional; legacy rows
stay NULL until the owner edits them (same as `state` in `0011`).

---

## Backend implementation

### Model: `backend/app/models/college.py` (new)

```python
import logging
from sqlalchemy import Boolean, Column, String, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

logger = logging.getLogger(__name__)


class College(Base):
    __tablename__ = "colleges"

    id         = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    slug       = Column(String, nullable=False, unique=True)
    name       = Column(String, nullable=False, unique=True)
    state      = Column(String)   # igod state/UT, for disambiguation
    city       = Column(String)   # igod district, for disambiguation
    is_active  = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    # No explicit schema — public default search_path, matching Listing.
```

### Model changes: `listings` and `users`

```python
# backend/app/models/listing.py — add after `city`
college_id    = Column(UUID(as_uuid=True), ForeignKey("colleges.id", ondelete="SET NULL"))
college_other = Column(String)   # free-text campus not yet in `colleges`; display-only, never filtered

# backend/app/models/user.py — add after `city`
college_id    = Column(UUID(as_uuid=True), ForeignKey("colleges.id", ondelete="SET NULL"))
college_other = Column(String)
```

### Schemas: `backend/app/schemas/college.py` (new)

```python
import uuid
from typing import Optional
from pydantic import BaseModel, ConfigDict


class CollegeBrief(BaseModel):
    """Embedded in listing/user responses for display + linking."""
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    slug: str
    name: str


class CollegeOut(CollegeBrief):
    state: Optional[str] = None
    city: Optional[str] = None
```

### Schema changes: listings (`backend/app/schemas/listing.py`)

Add to **both** `ListingCreate` and `ListingUpdate`:

```python
college_id: Optional[uuid.UUID] = None
college_other: Optional[str] = Field(None, max_length=120)

@field_validator("college_other")
@classmethod
def clean_college_other(cls, v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    v = v.strip()
    return v or None

@model_validator(mode="after")
def one_college_source(self):
    if self.college_id is not None and self.college_other:
        raise ValueError("Provide either college_id or college_other, not both.")
    return self
```

Add to `ListingOut` (replace nothing; `college_id` itself is **not** exposed as a raw
UUID — the embedded brief is friendlier and the slug drives the filter link):

```python
college: Optional[CollegeBrief] = None       # populated from the ORM relationship/lookup
college_other: Optional[str] = None
```

> Note: existence/`is_active` of `college_id` cannot be checked in a Pydantic
> validator (no DB access). That check lives in the service layer (below).

### Schema changes: users (`backend/app/schemas/user.py`)

- `UserUpdate`: add `college_id: Optional[uuid.UUID] = None`,
  `college_other: Optional[str] = Field(None, max_length=120)`, plus the same
  `clean_college_other` validator and `one_college_source` model validator.
- `UserMe` and `UserPublic`: add `college: Optional[CollegeBrief] = None` and
  `college_other: Optional[str] = None`.

### Service: `backend/app/services/college_service.py` (new)

```python
import logging
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.college import College
from app.models.listing import Listing

logger = logging.getLogger(__name__)


async def search_colleges(db: AsyncSession, q: str | None, limit: int = 20) -> list[College]:
    stmt = select(College).where(College.is_active == True)  # noqa: E712
    if q:
        stmt = stmt.where(College.name.ilike(f"%{q}%"))
    stmt = stmt.order_by(College.name.asc()).limit(limit)
    return (await db.execute(stmt)).scalars().all()


async def get_by_slug(db: AsyncSession, slug: str) -> College | None:
    stmt = select(College).where(College.slug == slug, College.is_active == True)  # noqa: E712
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_active_by_id(db: AsyncSession, college_id: UUID) -> College | None:
    stmt = select(College).where(College.id == college_id, College.is_active == True)  # noqa: E712
    return (await db.execute(stmt)).scalar_one_or_none()


async def colleges_with_active_listings(db: AsyncSession) -> list[tuple[College, int]]:
    """For the /colleges index — only campuses that have at least one active listing."""
    stmt = (
        select(College, func.count(Listing.id).label("n"))
        .join(Listing, Listing.college_id == College.id)
        .where(College.is_active == True,            # noqa: E712
               Listing.is_available == True,         # noqa: E712
               Listing.deleted_at == None)           # noqa: E711
        .group_by(College.id)
        .order_by(func.count(Listing.id).desc(), College.name.asc())
    )
    return [(row[0], row[1]) for row in (await db.execute(stmt)).all()]
```

### Service changes: `listing_service.py`

1. **Validate + set college on create.** In `create_listing`, before constructing the
   `Listing`, if `data.college_id` is provided, confirm it resolves to an active
   college (else `raise ValueError("Unknown or inactive college.")` → router maps to
   400). Set both `college_id=data.college_id` and `college_other=data.college_other`
   on the new `Listing`.

2. **Validate on update.** `update_listing` already applies
   `model_dump(exclude_unset=True)` via setattr — add a guard before the loop: if
   `"college_id" in update_data and update_data["college_id"] is not None`, verify it
   is an active college (reuse `college_service.get_active_by_id`); raise `ValueError`
   if not. When `college_id` is set, also ensure `college_other` is cleared, and vice
   versa, so the invariant holds after partial updates.

3. **Filter by slug.** Add `college: str | None = None` param to `get_listings`
   (the slug). Resolve once to an id and filter:

   ```python
   if college:
       col = await college_service.get_by_slug(db, college)
       if col is None:
           return []          # unknown slug → no results (consistent with other filters)
       stmt = stmt.where(Listing.college_id == col.id)
   ```

   `college_other` rows have `college_id IS NULL` and therefore never match — correct.

4. **Embed the college in responses.** `ListingOut.college` needs the campus name/slug.
   Add a SQLAlchemy `relationship("College", lazy="selectin")` named `college` on the
   `Listing` model so it loads with the listing, and `ListingOut` (with
   `from_attributes=True`) maps it to `CollegeBrief` automatically.

### Service changes: `user_service.update_user`

Same college validation as listings: if `college_id` is being set, confirm it's an
active college (raise `ValueError` → 404/400 in router); enforce the
`college_id` XOR `college_other` invariant on partial updates. Add a `college`
`selectin` relationship on the `User` model so `UserMe`/`UserPublic` can embed
`CollegeBrief`.

### Router: `backend/app/routers/colleges.py` (new)

```python
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.college import CollegeOut
from app.schemas.listing import ListingOut
from app.services import college_service, listing_service

router = APIRouter(prefix="/colleges", tags=["colleges"])
logger = logging.getLogger(__name__)


@router.get("", response_model=list[CollegeOut])
async def list_colleges(q: str | None = Query(None), db: AsyncSession = Depends(get_db)):
    return await college_service.search_colleges(db, q)


@router.get("/{slug}")
async def get_college(slug: str, db: AsyncSession = Depends(get_db)):
    college = await college_service.get_by_slug(db, slug)
    if not college:
        raise HTTPException(404, "College not found.")
    listings = await listing_service.get_listings(db, college=slug)
    return {
        "college": CollegeOut.model_validate(college),
        "listings": [ListingOut.model_validate(l) for l in listings],
    }
```

### Router changes: `backend/app/routers/listings.py`

Add `college: str | None = Query(None)` to `list_listings` and forward it by keyword
to `listing_service.get_listings(..., college=college)`.

### Router registration: `backend/app/main.py`

```python
from app.routers import colleges
app.include_router(colleges.router, prefix="/v1")
```

---

## Frontend implementation

### `frontend/constants/filters.js` — register the filter

```js
export const FILTER_KEYS = ['q', 'exam_category', 'listing_type', 'condition', 'state', 'city', 'subject', 'college']
```

This single change makes the SSR `/listings` page forward `?college=<slug>` and both
`ListingFilters` / `MobileFilters` render the control. (Keep it a plain, non-`'use
client'` module — see the comment already in `filters.js`.)

### `frontend/components/listings/CollegeCombobox.jsx` (new, reusable)

A client typeahead used in the listing form, edit dialog, settings, and filters.
Unlike `STATES`/`SUBJECTS` (static constants), colleges live in the DB, so this
component queries the API rather than importing a constant list:

- Debounced text input → TanStack Query `GET /v1/colleges?q=<text>` → renders matching
  options; selecting one sets `{ college_id, college: {slug, name} }`.
- A persistent **"My college isn't listed → add it"** row at the bottom. Choosing it
  switches the control to a free-text input bound to `college_other` (and clears any
  `college_id`). Helper copy: *"We'll review and add it — it won't appear in filters
  until then."*
- Controlled: takes `value` (`{college_id, college_other, college}`) + `onChange`.
- Styling reuses the `.select`/`.input` classes already in the form/filter UI.

### `frontend/components/listings/ListingFilters.jsx`

Add a **College** block after City/District, using `CollegeCombobox` in single-select
filter mode: selecting a college calls `handleChange('college', slug)`; clearing
removes the param. When `current.college` (a slug) is present on load, resolve it to a
display name via `GET /v1/colleges/{slug}` (or a cached `?q=` hit) so the chosen
campus shows by name. Mirror the same block in `MobileFilters`.

### `frontend/components/listings/CreateListingForm.jsx` — field + autofill

- Add an optional **College** field using `CollegeCombobox`.
- **Autofill:** on mount, read the signed-in user's profile (the `['me']` TanStack
  query / `GET /v1/users/me`) and pre-select their `college` if set — but the field is
  fully editable and clearable, so the listing can carry a different campus than the
  profile.
- Include `college_id` / `college_other` in the create mutation payload.

### `frontend/components/dashboard/EditListingDialog.jsx`

Add `college_id` / `college_other` to the edit form state (seeded from the listing's
embedded `college`) and the `PATCH /listings/{id}` payload. College is freely editable
(no bait-and-switch concern, unlike `exam_category`/`listing_type`).

### `frontend/app/settings/page.jsx`

Add an optional **College** field (`CollegeCombobox`) to the profile form; include
`college_id` / `college_other` in the `PATCH /users/me` payload and update the `['me']`
cache on success.

### College chip — `ListingCard.jsx`, `/listings/[id]`, profile page

Render a campus chip reusing the existing city/state badge styling:
- If `listing.college` (canonical) → show `college.name`, linked to
  `/colleges/{college.slug}`.
- Else if `listing.college_other` → show the raw text as a plain, **unlinked** muted
  chip (it is not a real community page yet).
- Else render nothing.

### SSR pages

```
frontend/app/(marketplace)/colleges/page.jsx          # index: campuses with active listings
frontend/app/(marketplace)/colleges/[slug]/page.jsx   # one campus + its active listings
```

- **Index** (`/colleges`): SSR `GET /v1/colleges` is not enough (it lists all) — call a
  lightweight index endpoint or filter client-side to campuses with listings. Simplest:
  render links to each `/colleges/[slug]` for colleges returned by
  `colleges_with_active_listings`. (Add a tiny `GET /v1/colleges?has_listings=1` variant
  if preferred; otherwise reuse the data the page already needs.)
- **Campus page** (`/colleges/[slug]`): SSR `GET /v1/colleges/{slug}` → render the
  college name + a `ListingGrid` of its active listings, cloning the existing
  `/users/[id]` SSR-with-grid layout. 404 → `notFound()`. This is the read-only
  "community" surface; no posting, no membership UI.

---

## Promotion workflow (manual, Supabase dashboard — no admin panel)

The "not listed" queue is rows with a free-text campus and no canonical link. Review
periodically in the SQL editor:

```sql
-- Most-requested un-promoted campuses (across listings + profiles)
SELECT college_other, COUNT(*) AS requests
FROM (
  SELECT college_other FROM listings
  WHERE college_id IS NULL AND college_other IS NOT NULL
  UNION ALL
  SELECT college_other FROM public.users
  WHERE college_id IS NULL AND college_other IS NOT NULL
) s
GROUP BY college_other
ORDER BY requests DESC;
```

To promote one (e.g. "BITS Goa"):

```sql
-- 1. Add the canonical row
INSERT INTO colleges (slug, name, state, city)
VALUES ('bits-goa', 'BITS Pilani (Goa Campus)', 'Goa', 'South Goa');

-- 2. Backfill listings that typed it (case-insensitive), then clear the free text
UPDATE listings
SET college_id = (SELECT id FROM colleges WHERE slug = 'bits-goa'),
    college_other = NULL
WHERE college_id IS NULL AND college_other ILIKE 'bits goa';

-- 3. Same for user profiles
UPDATE public.users
SET college_id = (SELECT id FROM colleges WHERE slug = 'bits-goa'),
    college_other = NULL
WHERE college_id IS NULL AND college_other ILIKE 'bits goa';
```

To retire a bad/duplicate college without deleting references:
`UPDATE colleges SET is_active = FALSE WHERE slug = '<slug>';`

This is the same manual-moderation model already documented in CLAUDE.md (hide
listings via dashboard `UPDATE`) — no new tooling, no third maintainer.

---

## Files to create

```
backend/app/models/college.py
backend/app/schemas/college.py
backend/app/services/college_service.py
backend/app/routers/colleges.py
backend/alembic/versions/0012_add_colleges.py

frontend/components/listings/CollegeCombobox.jsx
frontend/app/(marketplace)/colleges/page.jsx
frontend/app/(marketplace)/colleges/[slug]/page.jsx
```

## Files to modify

```
backend/app/models/listing.py        — college_id FK, college_other, `college` relationship
backend/app/models/user.py           — college_id FK, college_other, `college` relationship
backend/app/schemas/listing.py       — college_id/college_other on Create+Update; college (brief)+college_other on Out; validators
backend/app/schemas/user.py          — same fields on UserUpdate; college brief on UserMe/UserPublic
backend/app/services/listing_service.py — validate college_id, set fields, `college` slug filter, embed
backend/app/services/user_service.py    — validate college_id + XOR invariant on update
backend/app/routers/listings.py      — add `college` query param, forward to service
backend/app/main.py                  — register colleges router under /v1

frontend/constants/filters.js        — add 'college' to FILTER_KEYS
frontend/components/listings/ListingFilters.jsx     — College filter block (+ MobileFilters mirror)
frontend/components/listings/CreateListingForm.jsx  — College field + profile autofill
frontend/components/dashboard/EditListingDialog.jsx — College field in edit form + PATCH payload
frontend/app/settings/page.jsx       — College field on profile + PATCH /users/me
frontend/components/listings/ListingCard.jsx        — college chip
frontend/app/(marketplace)/listings/[id]/page.jsx   — college chip on detail
(frontend public profile page)       — college chip on /users/[id]

.claude/docs/SCHEMA.md               — colleges table + college_id/college_other on users & listings
.claude/specs/decisions/DECISIONS.md — row: college = table+FK discovery dimension (deviates from city/state TEXT), discovery-only (no members/feed), college_other holding pen + manual promotion
```

> The `MobileFilters` component (sibling of `ListingFilters`) and the public profile
> page should be confirmed by path during implementation and added to the modify list.

## New dependencies

No new dependencies. Typeahead uses the existing TanStack Query + native styled
`<select>`/`<input>` pattern. No combobox library is introduced.

---

## Security considerations

- **Rule 1 (no contact info in responses):** `CollegeBrief`/`CollegeOut` expose only
  campus metadata. `college_other` is free text shown publicly — it can contain
  contact info or abuse, so it is covered by the existing listing `/reports` flow and
  manual dashboard takedown, exactly like listing title/description. No new PII path.
- **Rule 3 / Rule 5 (ownership on mutations):** college edits ride the existing
  owner-checked `PATCH /listings/{id}` and self-only `PATCH /users/me`. No new
  mutation surface or ownership rule.
- **Rule 5 (parameterized queries):** all college lookups/filters use SQLAlchemy ORM
  (`ilike`, `==` on columns) — no string-interpolated SQL. The slug filter resolves
  via a parameterized `SELECT`, never by interpolating the slug into SQL.
- **Input validation:** `college_other` is length-capped (≤120) and stripped;
  `college_id` is validated to reference an **active** college in the service layer
  (a forged/inactive id is rejected, not silently stored). The `college_id` XOR
  `college_other` invariant prevents a canonical+freetext mismatch.
- **Trust model:** college is self-asserted and unverified (Google-OAuth-only, no
  `.edu`, no email column). It is **never** linked to `is_verified`. Recourse for
  abuse is manual dashboard edit (`is_active = FALSE`, clear `college_other`).
- **Moderation (DECISIONS.md — dashboard only):** promotion and cleanup are manual SQL,
  consistent with "no admin panel" and "manual moderation" for v1 volume.

---

## Definition of done

- [ ] `alembic upgrade head` creates `colleges` (seeded) and adds `college_id` +
      `college_other` to `listings` and `public.users`; `downgrade` cleanly reverses.
- [ ] `colleges.slug` and `colleges.name` reject duplicates (unique constraints).
- [ ] `GET /v1/colleges?q=iit` returns active colleges whose name matches, ≤20 rows,
      name-sorted.
- [ ] `GET /v1/colleges/{slug}` returns the college + its active listings; 404 on an
      unknown or inactive slug.
- [ ] `POST /listings` with a valid `college_id` stores it; the listing response
      embeds `college: {id, slug, name}`.
- [ ] `POST /listings` with `college_other:"Foo College"` and no `college_id` stores
      the text; response shows `college: null, college_other:"Foo College"`.
- [ ] `POST /listings` with **both** `college_id` and `college_other` → 422.
- [ ] `POST /listings` with a random/inactive `college_id` → 400 "Unknown or inactive
      college."
- [ ] `GET /listings?college=<slug>` returns only listings whose `college_id` matches
      that slug; an unknown slug returns `[]` (200, not 422).
- [ ] A `college_other` listing never appears in any `?college=<slug>` result.
- [ ] `PATCH /listings/{id}` can change/clear the college; setting `college_id` clears
      `college_other` and vice versa.
- [ ] `PATCH /users/me` with `college_id`/`college_other` updates the profile;
      `GET /users/me` and `GET /users/{id}` embed the `college` brief / `college_other`.
- [ ] `'college'` is in `FILTER_KEYS`; the `/listings` SSR page forwards
      `?college=<slug>` and renders results without hydration errors.
- [ ] `CollegeCombobox` searches as the user types, selects a canonical college, and
      its "my college isn't listed" path captures free text into `college_other`.
- [ ] `/listings/new` pre-selects the signed-in user's profile college, and the user
      can override or clear it before submitting.
- [ ] Listing cards / detail / public profile show a linked campus chip for a canonical
      college and an unlinked text chip for `college_other`; nothing when both are null.
- [ ] `/colleges` lists only campuses with ≥1 active listing, each linking to its page.
- [ ] `/colleges/[slug]` SSR-renders the campus name + a grid of its active listings;
      unknown slug → 404.
- [ ] The dashboard GROUP BY surfaces un-promoted `college_other` values; the promote +
      backfill SQL links those rows to a new canonical college and clears the free text.
- [ ] No member/feed/post/notification surface exists anywhere in the diff.
- [ ] `SCHEMA.md` and `DECISIONS.md` updated as listed.
```

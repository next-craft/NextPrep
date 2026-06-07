# Spec 14: Listings CRUD

## Purpose

This spec covers the complete backend and frontend implementation of all listing endpoints for Study Material Exchange India. Listings are the core entity of the marketplace — a seller's offer to sell physical study material. This spec defines exactly how listings are created, read (searched and fetched individually), updated, soft-deleted, and how the seller's passkey is regenerated. It covers all Pydantic schemas, SQLAlchemy model, service logic, router wiring, frontend pages and components, and every edge case including ownership enforcement, passkey generation/reveal, field-level update restrictions, soft-delete semantics, and the views counter. Everything is grounded in the DB schema in SCHEMA.md, the endpoint contracts in Spec 13 (API), and the user flows in Spec 02.

---

## Depends on

- **Spec 06 — Schema:** `listings` table definition, column types, constraints, valid states
- **Spec 07 — Auth:** `verify_token`, `user["sub"]` UUID, `@supabase/ssr` frontend session
- **Spec 13 — API:** Authoritative endpoint contracts for all listings routes (request/response shapes, status codes, error details)

---

## Scope

**In scope:**
- Backend: `Listing` SQLAlchemy model, Pydantic request/response schemas, `listing_service.py`, `listings` router
- Backend: `GET /listings`, `POST /listings`, `GET /listings/{id}`, `PATCH /listings/{id}`, `DELETE /listings/{id}`, `PATCH /listings/{id}/passkey`
- Frontend: `/listings` SSR page, `/listings/[id]` SSR page, `/listings/new` protected page, listing edit form (dashboard), passkey reveal screen
- Frontend: `ListingCard`, `ListingGrid`, `ListingFilters`, `BuyNowButton`, `PasskeyInput` components
- Alembic migration for `listings` table (if not already applied by Spec 06)
- View counter increment on `GET /listings/{id}`
- Ownership check on all mutations

**Out of scope:**
- Payment passkey verification (`POST /payments/verify-passkey`) — Spec 09
- Conversations triggered by listing — Spec 10
- Image uploads (Cloudinary widget wiring) — separate image-upload spec
- Seller Razorpay onboarding — Spec 09
- User profile endpoints — separate users spec

---

## Database model

The `listings` table is fully defined in SCHEMA.md. Reproduced here for implementation reference:

```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
seller_id       UUID REFERENCES public.users(id) ON DELETE CASCADE
title           TEXT NOT NULL
description     TEXT
exam_category   TEXT NOT NULL
subject         TEXT
listing_type    TEXT NOT NULL
  CHECK (listing_type IN ('BOOK', 'NOTES', 'MODULE', 'BUNDLE'))
condition       TEXT NOT NULL   -- A / B / C
asking_price    INTEGER NOT NULL
original_price  INTEGER
city            TEXT NOT NULL
images          TEXT[]
is_available    BOOLEAN DEFAULT TRUE
sold_at         TIMESTAMPTZ DEFAULT NULL
passkey_hash    TEXT NOT NULL
passkey_invalidated      BOOLEAN DEFAULT FALSE
passkey_invalidated_at   TIMESTAMPTZ DEFAULT NULL
views           INTEGER DEFAULT 0
created_at      TIMESTAMPTZ DEFAULT now()

CONSTRAINT no_available_sold_listing CHECK (
    NOT (is_available = TRUE AND sold_at IS NOT NULL)
)
```

Valid listing states:
- `is_available=TRUE, sold_at=NULL` — active, appears in search
- `is_available=FALSE, sold_at=NULL` — paused (seller-paused) or suspended (admin) or soft-deleted (`deleted_at IS NOT NULL`)
- `is_available=FALSE, sold_at NOT NULL` — sold (set by webhook only)

`deleted_at` column does **not** exist in the schema above — soft delete is represented by `is_available=FALSE` and a separate `deleted_at` field. Add `deleted_at TIMESTAMPTZ DEFAULT NULL` to the model. This column requires an Alembic migration if Spec 06 did not include it.

> **Check first:** Run `\d listings` in Supabase SQL editor or inspect `alembic/versions/` to confirm whether `deleted_at` was already added. If it exists, skip the migration step below.

---

## Backend implementation

### SQLAlchemy model

```python
# backend/app/models/listing.py
import uuid
from sqlalchemy import (
    UUID, Boolean, Integer, String, Text, TIMESTAMP, CheckConstraint
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from datetime import datetime


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    seller_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    exam_category: Mapped[str] = mapped_column(String, nullable=False)
    subject: Mapped[str | None] = mapped_column(String, nullable=True)
    listing_type: Mapped[str] = mapped_column(String, nullable=False)
    condition: Mapped[str] = mapped_column(String(1), nullable=False)
    asking_price: Mapped[int] = mapped_column(Integer, nullable=False)
    original_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    city: Mapped[str] = mapped_column(String, nullable=False)
    images: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    sold_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    passkey_hash: Mapped[str] = mapped_column(Text, nullable=False)
    passkey_invalidated: Mapped[bool] = mapped_column(Boolean, default=False)
    passkey_invalidated_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    views: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default="now()"
    )

    __table_args__ = (
        CheckConstraint(
            "listing_type IN ('BOOK', 'NOTES', 'MODULE', 'BUNDLE')",
            name="ck_listing_type"
        ),
        CheckConstraint(
            "NOT (is_available = TRUE AND sold_at IS NOT NULL)",
            name="no_available_sold_listing"
        ),
    )
```

---

### Pydantic schemas

```python
# backend/app/schemas/listing.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
import uuid

VALID_EXAM_CATEGORIES = {
    "JEE_MAINS", "JEE_ADVANCED", "NEET_UG", "NEET_PG",
    "UPSC_CSE", "UPSC_OTHER",
    "CA_FOUNDATION", "CA_INTERMEDIATE", "CA_FINAL",
    "GATE", "GMAT", "GRE", "IELTS", "CUET",
    "CLASS_9", "CLASS_10", "CLASS_11", "CLASS_12",
    "OTHER",
}
VALID_LISTING_TYPES = {"BOOK", "NOTES", "MODULE", "BUNDLE"}
VALID_CONDITIONS = {"A", "B", "C"}


class ListingCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=1000)
    exam_category: str
    subject: Optional[str] = None
    listing_type: str
    condition: str
    asking_price: int = Field(..., gt=0)
    original_price: Optional[int] = Field(None, gt=0)
    city: str = Field(..., min_length=1)
    images: Optional[list[str]] = Field(None, max_length=5)

    @field_validator("exam_category")
    @classmethod
    def validate_exam_category(cls, v: str) -> str:
        if v not in VALID_EXAM_CATEGORIES:
            raise ValueError(f"exam_category must be one of: {sorted(VALID_EXAM_CATEGORIES)}")
        return v

    @field_validator("listing_type")
    @classmethod
    def validate_listing_type(cls, v: str) -> str:
        if v not in VALID_LISTING_TYPES:
            raise ValueError("listing_type must be BOOK, NOTES, MODULE, or BUNDLE")
        return v

    @field_validator("condition")
    @classmethod
    def validate_condition(cls, v: str) -> str:
        if v not in VALID_CONDITIONS:
            raise ValueError("condition must be A, B, or C")
        return v

    @field_validator("images")
    @classmethod
    def validate_images(cls, v: list[str] | None) -> list[str] | None:
        if v is not None and len(v) > 5:
            raise ValueError("images must have at most 5 URLs")
        return v


class ListingUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=1000)
    subject: Optional[str] = None
    condition: Optional[str] = None
    asking_price: Optional[int] = Field(None, gt=0)
    original_price: Optional[int] = Field(None, gt=0)
    city: Optional[str] = Field(None, min_length=1)
    images: Optional[list[str]] = Field(None, max_length=5)
    is_available: Optional[bool] = None

    @field_validator("condition")
    @classmethod
    def validate_condition(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_CONDITIONS:
            raise ValueError("condition must be A, B, or C")
        return v

    @field_validator("images")
    @classmethod
    def validate_images(cls, v: list[str] | None) -> list[str] | None:
        if v is not None and len(v) > 5:
            raise ValueError("images must have at most 5 URLs")
        return v


class ListingOut(BaseModel):
    id: uuid.UUID
    seller_id: uuid.UUID
    title: str
    description: Optional[str]
    exam_category: str
    subject: Optional[str]
    listing_type: str
    condition: str
    asking_price: int
    original_price: Optional[int]
    city: str
    images: Optional[list[str]]
    is_available: bool
    is_sold: bool  # computed: sold_at IS NOT NULL — never expose sold_at itself
    views: int
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj, **kwargs):
        # Inject is_sold from the ORM object before standard validation
        if hasattr(obj, "sold_at"):
            data = {c.key: getattr(obj, c.key) for c in obj.__table__.columns}
            data["is_sold"] = obj.sold_at is not None
            return cls(**data)
        return super().model_validate(obj, **kwargs)


class ListingCreateOut(BaseModel):
    listing: ListingOut
    passkey: str  # plaintext, returned once only
```

**PATCH restrictions:** `exam_category` and `listing_type` are not in `ListingUpdate`. They cannot be changed after creation — preventing bait-and-switch as stated in Spec 02 section 3.4.

---

### Service layer

```python
# backend/app/services/listing_service.py
import secrets
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listing import Listing
from app.schemas.listing import ListingCreate, ListingUpdate
from app.core.security import hash_passkey

logger = logging.getLogger(__name__)


async def create_listing(
    db: AsyncSession, seller_id: str, data: ListingCreate
) -> tuple[Listing, str]:
    passkey = str(secrets.randbelow(100_000_000)).zfill(8)
    passkey_hash = hash_passkey(passkey, "placeholder")  # listing_id unknown until insert

    listing = Listing(
        seller_id=UUID(seller_id),
        title=data.title,
        description=data.description,
        exam_category=data.exam_category,
        subject=data.subject,
        listing_type=data.listing_type,
        condition=data.condition,
        asking_price=data.asking_price,
        original_price=data.original_price,
        city=data.city,
        images=data.images or [],
        passkey_hash="placeholder",  # overwritten after insert
    )
    db.add(listing)
    await db.flush()  # generates listing.id without committing

    # Re-hash with actual listing.id
    passkey_hash = hash_passkey(passkey, str(listing.id))
    listing.passkey_hash = passkey_hash
    await db.commit()
    await db.refresh(listing)

    logger.info("listing_created seller=%s listing=%s", seller_id, listing.id)
    return listing, passkey


async def get_listings(
    db: AsyncSession,
    q: str | None = None,
    exam_category: str | None = None,
    subject: str | None = None,
    city: str | None = None,
    condition: str | None = None,
    listing_type: str | None = None,
) -> list[Listing]:
    stmt = select(Listing).where(
        Listing.is_available == True,
        Listing.deleted_at == None,
    )
    if q:
        stmt = stmt.where(
            or_(
                Listing.title.ilike(f"%{q}%"),
                Listing.description.ilike(f"%{q}%"),
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


async def get_listing_by_id(db: AsyncSession, listing_id: str) -> Listing | None:
    stmt = select(Listing).where(Listing.id == UUID(listing_id))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def increment_views(db: AsyncSession, listing: Listing) -> None:
    await db.execute(
        update(Listing)
        .where(Listing.id == listing.id)
        .values(views=Listing.views + 1)
    )
    await db.commit()


async def update_listing(
    db: AsyncSession, listing: Listing, data: ListingUpdate
) -> Listing:
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(listing, field, value)
    await db.commit()
    await db.refresh(listing)
    logger.info("listing_updated listing=%s fields=%s", listing.id, list(update_data.keys()))
    return listing


async def delete_listing(db: AsyncSession, listing: Listing) -> None:
    listing.is_available = False
    listing.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info("listing_deleted listing=%s", listing.id)


async def regenerate_passkey(db: AsyncSession, listing: Listing) -> str:
    passkey = str(secrets.randbelow(100_000_000)).zfill(8)
    passkey_hash = hash_passkey(passkey, str(listing.id))
    listing.passkey_hash = passkey_hash
    await db.commit()
    logger.info("passkey_regenerated listing=%s", listing.id)
    return passkey
```

---

### Router

```python
# backend/app/routers/listings.py
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_token
from app.schemas.listing import (
    ListingCreate, ListingCreateOut, ListingOut, ListingUpdate
)
from app.services import listing_service
from app.services import user_service  # for razorpay_account_id check

router = APIRouter(prefix="/listings", tags=["listings"])
logger = logging.getLogger(__name__)


@router.get("", response_model=list[ListingOut])
async def list_listings(
    q: str | None = Query(None),
    exam_category: str | None = Query(None),
    subject: str | None = Query(None),
    city: str | None = Query(None),
    condition: str | None = Query(None),
    listing_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await listing_service.get_listings(
        db, q=q, exam_category=exam_category, subject=subject,
        city=city, condition=condition, listing_type=listing_type
    )


@router.post("", response_model=ListingCreateOut, status_code=201)
async def create_listing(
    data: ListingCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token),
):
    seller_id = user["sub"]
    seller = await user_service.get_user_by_id(db, seller_id)
    if not seller or not seller.razorpay_account_id:
        raise HTTPException(status_code=403, detail="Complete payment setup to start selling.")

    listing, passkey = await listing_service.create_listing(db, seller_id, data)
    return ListingCreateOut(listing=ListingOut.model_validate(listing), passkey=passkey)


@router.get("/{listing_id}", response_model=ListingOut)
async def get_listing(
    listing_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    listing = await listing_service.get_listing_by_id(db, str(listing_id))
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
    await listing_service.increment_views(db, listing)
    listing.views += 1  # reflect in response without re-querying
    return listing


@router.patch("/{listing_id}", response_model=ListingOut)
async def update_listing(
    listing_id: UUID,
    data: ListingUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token),
):
    listing = await listing_service.get_listing_by_id(db, str(listing_id))
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
    if str(listing.seller_id) != user["sub"]:
        raise HTTPException(status_code=403, detail="Not authorised.")
    return await listing_service.update_listing(db, listing, data)


@router.delete("/{listing_id}", status_code=204)
async def delete_listing(
    listing_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token),
):
    listing = await listing_service.get_listing_by_id(db, str(listing_id))
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
    if str(listing.seller_id) != user["sub"]:
        raise HTTPException(status_code=403, detail="Not authorised.")
    await listing_service.delete_listing(db, listing)


@router.patch("/{listing_id}/passkey")
async def regenerate_passkey(
    listing_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token),
):
    listing = await listing_service.get_listing_by_id(db, str(listing_id))
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
    if str(listing.seller_id) != user["sub"]:
        raise HTTPException(status_code=403, detail="Not authorised.")
    if listing.passkey_invalidated:
        raise HTTPException(
            status_code=400, detail="Cannot regenerate passkey for a sold listing."
        )
    passkey = await listing_service.regenerate_passkey(db, listing)
    return {"passkey": passkey}
```

---

### User service (minimal — required by listings router)

`POST /listings` checks `razorpay_account_id` before creating a listing. The following function must exist:

```python
# backend/app/services/user_service.py
import logging
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User

logger = logging.getLogger(__name__)


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    stmt = select(User).where(User.id == UUID(user_id))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
```

`User` model must exist at `backend/app/models/user.py` matching the `public.users` table (see SCHEMA.md). If it already exists from a prior spec, skip creating it. If not, its minimum required columns for this check are `id` (UUID PK) and `razorpay_account_id` (Text, nullable).

---

### Router registration

```python
# backend/app/main.py — add this import and include_router call
from app.routers import listings

app.include_router(listings.router, prefix="/v1")
```

---

### Alembic migration (only if `deleted_at` not yet in schema)

```bash
cd backend
..\\.venv\\Scripts\\alembic revision --autogenerate -m "add deleted_at to listings"
..\\.venv\\Scripts\\alembic upgrade head
```

Confirm the generated migration adds only:
```python
op.add_column('listings', sa.Column('deleted_at', sa.TIMESTAMP(timezone=True), nullable=True))
```

---

## Frontend implementation

### `/listings` — SSR listing index

```jsx
// frontend/app/(marketplace)/listings/page.jsx
import { createServerSupabaseClient } from '@/lib/supabase/server'
import ListingGrid from '@/components/listings/ListingGrid'
import ListingFilters from '@/components/listings/ListingFilters'

export const revalidate = 0  // always fresh — ISR not needed here

export default async function ListingsPage({ searchParams }) {
  const params = new URLSearchParams()
  const keys = ['q', 'exam_category', 'subject', 'city', 'condition', 'listing_type']
  keys.forEach(k => { if (searchParams[k]) params.set(k, searchParams[k]) })

  const res = await fetch(
    `${process.env.API_URL}/v1/listings?${params.toString()}`,
    { cache: 'no-store' }
  )
  const listings = res.ok ? await res.json() : []

  return (
    <div className="flex gap-6 p-6">
      <aside className="w-64 shrink-0">
        <ListingFilters current={searchParams} />
      </aside>
      <main className="flex-1">
        <ListingGrid listings={listings} />
      </main>
    </div>
  )
}
```

### `/listings/[id]` — SSR listing detail

```jsx
// frontend/app/(marketplace)/listings/[id]/page.jsx
import { createServerSupabaseClient } from '@/lib/supabase/server'
import { formatPrice } from '@/lib/utils'
import BuyNowButton from '@/components/listings/BuyNowButton'
import { notFound } from 'next/navigation'

export default async function ListingDetailPage({ params }) {
  const res = await fetch(`${process.env.API_URL}/v1/listings/${params.id}`, {
    cache: 'no-store',
  })
  if (res.status === 404) notFound()
  const listing = await res.json()

  const supabase = createServerSupabaseClient()
  const { data: { user } } = await supabase.auth.getUser()

  const isOwner = user?.id === listing.seller_id
  const isSold = listing.is_sold === true   // computed by backend; sold_at is never in response
  const isUnavailable = !listing.is_available && !isSold

  return (
    <div className="max-w-3xl mx-auto p-6">
      {isSold && (
        <div className="mb-4 rounded-md bg-red-50 px-4 py-3 text-red-700">
          This listing has been sold.
        </div>
      )}
      {isUnavailable && (
        <div className="mb-4 rounded-md bg-yellow-50 px-4 py-3 text-yellow-700">
          This listing is temporarily unavailable.
        </div>
      )}

      {/* Image carousel */}
      {listing.images?.length > 0 && (
        <div className="mb-6 overflow-x-auto flex gap-2">
          {listing.images.map((url, i) => (
            <img key={i} src={url} alt={listing.title} className="h-64 rounded-lg object-cover" />
          ))}
        </div>
      )}

      <h1 className="text-2xl font-bold">{listing.title}</h1>
      <div className="mt-2 text-3xl font-semibold text-green-700">
        {formatPrice(listing.asking_price)}
      </div>
      {listing.original_price && (
        <div className="text-sm text-gray-500 line-through">
          Original: {formatPrice(listing.original_price)}
        </div>
      )}

      <div className="mt-4 flex gap-2 flex-wrap">
        <span className="badge">{listing.listing_type}</span>
        <span className="badge">Condition {listing.condition}</span>
        <span className="badge">{listing.exam_category}</span>
        <span className="badge">{listing.city}</span>
      </div>

      {listing.subject && (
        <p className="mt-2 text-sm text-gray-600">Subject: {listing.subject}</p>
      )}

      {listing.description && (
        <p className="mt-4 whitespace-pre-wrap text-gray-700">{listing.description}</p>
      )}

      <p className="mt-4 text-xs text-gray-400">{listing.views} views</p>

      {!isOwner && user && listing.is_available && (
        <div className="mt-6 flex gap-3">
          <BuyNowButton listingId={listing.id} />
          {/* Route defined in Spec 10 (Chat) frontend — update href when that spec is implemented */}
          <a href={`/chat?listing=${listing.id}`} className="btn-secondary">
            Chat with seller
          </a>
        </div>
      )}

      {isOwner && (
        <div className="mt-6 flex gap-3">
          {/* Edit and passkey management are in the dashboard — /listings/[id]/edit is out of scope */}
          <a href={`/dashboard`} className="btn-secondary">
            Manage listing
          </a>
        </div>
      )}
    </div>
  )
}
```

### `/listings/new` — create listing (protected)

```jsx
// frontend/app/(marketplace)/listings/new/page.jsx
import { createServerSupabaseClient } from '@/lib/supabase/server'
import { redirect } from 'next/navigation'
import CreateListingForm from '@/components/listings/CreateListingForm'

export default async function NewListingPage() {
  const supabase = createServerSupabaseClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')
  return <CreateListingForm />
}
```

```jsx
// frontend/components/listings/CreateListingForm.jsx
'use client'
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import api from '@/lib/api'
import { EXAM_CATEGORIES } from '@/constants/examCategories'
import { LISTING_TYPES } from '@/constants/listingTypes'
import { CONDITIONS } from '@/constants/conditions'
import PasskeyReveal from '@/components/listings/PasskeyReveal'

export default function CreateListingForm() {
  const router = useRouter()
  const [passkey, setPasskey] = useState(null)
  const [listingId, setListingId] = useState(null)

  const { mutate, isPending, error } = useMutation({
    mutationFn: (data) => api.post('/listings', data),
    onSuccess: ({ data }) => {
      setPasskey(data.passkey)
      setListingId(data.listing.id)
    },
  })

  if (passkey) return <PasskeyReveal passkey={passkey} listingId={listingId} />

  function handleSubmit(e) {
    e.preventDefault()
    const fd = new FormData(e.target)
    const asking_price = parseInt(fd.get('asking_price'), 10)
    const original_price = fd.get('original_price') ? parseInt(fd.get('original_price'), 10) : undefined
    mutate({
      title: fd.get('title'),
      description: fd.get('description') || undefined,
      exam_category: fd.get('exam_category'),
      subject: fd.get('subject') || undefined,
      listing_type: fd.get('listing_type'),
      condition: fd.get('condition'),
      asking_price,
      original_price,
      city: fd.get('city'),
    })
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-lg mx-auto p-6 space-y-4">
      <h1 className="text-2xl font-bold">Create Listing</h1>

      {error && (
        <div className="text-red-600 text-sm">
          {error.response?.data?.detail || 'Something went wrong.'}
        </div>
      )}

      <div>
        <label className="label">Title *</label>
        <input name="title" required maxLength={120} className="input" />
      </div>

      <div>
        <label className="label">Description</label>
        <textarea name="description" maxLength={1000} className="input" rows={4} />
      </div>

      <div>
        <label className="label">Exam Category *</label>
        <select name="exam_category" required className="input">
          {EXAM_CATEGORIES.map(c => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </select>
      </div>

      <div>
        <label className="label">Subject</label>
        <input name="subject" className="input" placeholder="e.g. Physics, Organic Chemistry" />
      </div>

      <div>
        <label className="label">Listing Type *</label>
        <select name="listing_type" required className="input">
          {LISTING_TYPES.map(t => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
      </div>

      <div>
        <label className="label">Condition *</label>
        <select name="condition" required className="input">
          {CONDITIONS.map(c => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="label">Asking Price (₹) *</label>
          <input name="asking_price" type="number" min={1} required className="input" />
        </div>
        <div>
          <label className="label">Original Price (₹)</label>
          <input name="original_price" type="number" min={1} className="input" />
        </div>
      </div>

      <div>
        <label className="label">City *</label>
        <input name="city" required className="input" placeholder="e.g. Delhi, Mumbai" />
      </div>

      <button type="submit" disabled={isPending} className="btn-primary w-full">
        {isPending ? 'Creating…' : 'Create Listing'}
      </button>
    </form>
  )
}
```

### Passkey reveal screen

```jsx
// frontend/components/listings/PasskeyReveal.jsx
'use client'
import { useState } from 'react'

export default function PasskeyReveal({ passkey, listingId }) {
  const [copied, setCopied] = useState(false)

  function handleCopy() {
    navigator.clipboard.writeText(passkey)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="max-w-md mx-auto p-8 text-center space-y-6">
      <h1 className="text-2xl font-bold">Your listing is live!</h1>

      <p className="text-gray-600">Your passkey is:</p>

      <div className="text-4xl font-mono tracking-[0.3em] bg-gray-50 rounded-xl py-6 px-4 select-all">
        {passkey.slice(0, 4)} {passkey.slice(4)}
      </div>

      <div className="text-sm text-gray-600 space-y-2 text-left bg-amber-50 rounded-lg p-4">
        <p>Give this code to the buyer <strong>only</strong> when they are ready to pay during the meetup.</p>
        <p>The order is: <strong>meet → inspect → share passkey → pay.</strong></p>
        <p>Do not share it over chat — buyers must enter it in the app.</p>
      </div>

      <p className="text-sm font-semibold text-red-600">
        ⚠️ You won't be able to see this code again. Copy or memorise it now.
      </p>

      <div className="flex gap-3 justify-center">
        <button onClick={handleCopy} className="btn-secondary">
          {copied ? 'Copied!' : 'Copy passkey'}
        </button>
        <a href={`/listings/${listingId}`} className="btn-primary">
          Go to my listing
        </a>
      </div>
    </div>
  )
}
```

### ListingCard component

```jsx
// frontend/components/listings/ListingCard.jsx
import { formatPrice } from '@/lib/utils'
import Link from 'next/link'

export default function ListingCard({ listing }) {
  return (
    <Link href={`/listings/${listing.id}`} className="block rounded-xl border hover:shadow-md transition">
      {listing.images?.[0] ? (
        <img src={listing.images[0]} alt={listing.title} className="h-48 w-full object-cover rounded-t-xl" />
      ) : (
        <div className="h-48 w-full bg-gray-100 rounded-t-xl flex items-center justify-center text-gray-400 text-sm">
          No image
        </div>
      )}
      <div className="p-4 space-y-1">
        <p className="font-semibold line-clamp-2">{listing.title}</p>
        <p className="text-lg font-bold text-green-700">{formatPrice(listing.asking_price)}</p>
        <div className="flex gap-2 flex-wrap text-xs text-gray-500">
          <span>{listing.listing_type}</span>
          <span>Cond. {listing.condition}</span>
          <span>{listing.city}</span>
        </div>
        <p className="text-xs text-gray-400">{listing.exam_category}</p>
      </div>
    </Link>
  )
}
```

### ListingGrid component

```jsx
// frontend/components/listings/ListingGrid.jsx
import ListingCard from './ListingCard'

export default function ListingGrid({ listings }) {
  if (!listings.length) {
    return (
      <p className="text-gray-500 text-center py-20">
        No listings found for your filters. Try removing a filter or broadening your search.
      </p>
    )
  }
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {listings.map(l => <ListingCard key={l.id} listing={l} />)}
    </div>
  )
}
```

### ListingFilters component

```jsx
// frontend/components/listings/ListingFilters.jsx
'use client'
import { useRouter } from 'next/navigation'
import { EXAM_CATEGORIES } from '@/constants/examCategories'
import { LISTING_TYPES } from '@/constants/listingTypes'
import { CONDITIONS } from '@/constants/conditions'

export default function ListingFilters({ current }) {
  const router = useRouter()

  function handleChange(key, value) {
    const params = new URLSearchParams(current)
    if (value) params.set(key, value)
    else params.delete(key)
    router.push(`/listings?${params.toString()}`)
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="label text-xs">Search</label>
        <input
          className="input text-sm"
          defaultValue={current.q || ''}
          placeholder="Title or description"
          onBlur={e => handleChange('q', e.target.value)}
        />
      </div>
      <div>
        <label className="label text-xs">Exam category</label>
        <select className="input text-sm" defaultValue={current.exam_category || ''} onChange={e => handleChange('exam_category', e.target.value)}>
          <option value="">All</option>
          {EXAM_CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
      </div>
      <div>
        <label className="label text-xs">Type</label>
        <select className="input text-sm" defaultValue={current.listing_type || ''} onChange={e => handleChange('listing_type', e.target.value)}>
          <option value="">All</option>
          {LISTING_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
      </div>
      <div>
        <label className="label text-xs">Condition</label>
        <select className="input text-sm" defaultValue={current.condition || ''} onChange={e => handleChange('condition', e.target.value)}>
          <option value="">All</option>
          {CONDITIONS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
      </div>
    </div>
  )
}
```

### BuyNowButton component

```jsx
// frontend/components/listings/BuyNowButton.jsx
'use client'
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import api from '@/lib/api'

export default function BuyNowButton({ listingId }) {
  const [showPasskey, setShowPasskey] = useState(false)
  const [passkey, setPasskey] = useState('')
  const [error, setError] = useState(null)

  const { mutate, isPending } = useMutation({
    mutationFn: () => api.post('/payments/verify-passkey', { listing_id: listingId, passkey }),
    onSuccess: ({ data }) => {
      window.location.href = data.payment_link_url
    },
    onError: (err) => {
      setError(err.response?.data?.detail || 'Something went wrong.')
    },
  })

  if (!showPasskey) {
    return (
      <button onClick={() => setShowPasskey(true)} className="btn-primary">
        Buy Now
      </button>
    )
  }

  return (
    <div className="mt-4 space-y-2">
      <p className="text-sm text-gray-600">Enter the 8-digit passkey the seller gives you at the meetup:</p>
      <div className="flex gap-2">
        <input
          type="text"
          inputMode="numeric"
          maxLength={8}
          value={passkey}
          onChange={e => setPasskey(e.target.value.replace(/\D/g, ''))}
          className="input font-mono tracking-widest w-36"
          placeholder="00000000"
        />
        <button
          onClick={() => mutate()}
          disabled={passkey.length !== 8 || isPending}
          className="btn-primary"
        >
          {isPending ? 'Verifying…' : 'Submit'}
        </button>
      </div>
      {error && <p className="text-red-600 text-sm">{error}</p>}
    </div>
  )
}
```

---

## `formatPrice` utility

```javascript
// frontend/lib/utils.js  (add if not already present)
export function formatPrice(rupees) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(rupees)
}
```

---

## Constants files

```javascript
// frontend/constants/examCategories.js
export const EXAM_CATEGORIES = [
  { value: 'JEE_MAINS', label: 'JEE Mains' },
  { value: 'JEE_ADVANCED', label: 'JEE Advanced' },
  { value: 'NEET_UG', label: 'NEET UG' },
  { value: 'NEET_PG', label: 'NEET PG' },
  { value: 'UPSC_CSE', label: 'UPSC CSE' },
  { value: 'UPSC_OTHER', label: 'UPSC Other' },
  { value: 'CA_FOUNDATION', label: 'CA Foundation' },
  { value: 'CA_INTERMEDIATE', label: 'CA Intermediate' },
  { value: 'CA_FINAL', label: 'CA Final' },
  { value: 'GATE', label: 'GATE' },
  { value: 'GMAT', label: 'GMAT' },
  { value: 'GRE', label: 'GRE' },
  { value: 'IELTS', label: 'IELTS' },
  { value: 'CUET', label: 'CUET' },
  { value: 'CLASS_9', label: 'Class 9' },
  { value: 'CLASS_10', label: 'Class 10' },
  { value: 'CLASS_11', label: 'Class 11' },
  { value: 'CLASS_12', label: 'Class 12' },
  { value: 'OTHER', label: 'Other' },
]
```

```javascript
// frontend/constants/listingTypes.js
export const LISTING_TYPES = [
  { value: 'BOOK', label: 'Book — Published books (HC Verma, NCERT, RD Sharma)' },
  { value: 'NOTES', label: 'Notes — Handwritten or self-created notes' },
  { value: 'MODULE', label: 'Module — Coaching modules, DPPs (Allen, Aakash, FIITJEE, PW)' },
  { value: 'BUNDLE', label: 'Bundle — Multiple items sold together' },
]
```

```javascript
// frontend/constants/conditions.js
export const CONDITIONS = [
  { value: 'A', label: 'A — Like new (no markings, no wear)' },
  { value: 'B', label: 'B — Good (light use, minimal highlighting, pages intact)' },
  { value: 'C', label: 'C — Acceptable (heavy use, highlighting, fully readable)' },
]
```

---

## Edge cases

### Creating a listing
- ~~Seller without `razorpay_account_id` → 403. Check in router before creating.~~ **Deferred to Spec 09 (seller onboarding)** — `razorpay_account_id` does not exist on the `users` table/model yet (not in SCHEMA.md or the `0001_initial_schema` migration). The gate will be added to `POST /listings` once Spec 09 lands and introduces the column. `user_service.get_user_by_id` is already scaffolded for reuse at that point.
- `images` array longer than 5 → 422 (Pydantic validator).
- `asking_price = 0` → 422 (`gt=0` constraint).
- `exam_category` not in canonical set → 422 (Pydantic validator).
- `listing_type` not in `{BOOK, NOTES, MODULE, BUNDLE}` → 422 and DB CHECK.

### Reading listings
- `GET /listings` with no filters → all `is_available=TRUE AND deleted_at IS NULL` listings, newest first.
- `GET /listings` with invalid `exam_category` → returns empty array (not 422 — query params are strings, no Pydantic enum enforcement on GET).
- `GET /listings/{id}` → returns listing even if `is_available=FALSE`. Frontend determines display state. Views counter always incremented.
- `GET /listings/{id}` on a deleted listing (`deleted_at IS NOT NULL`) → returns the row. Frontend checks `is_available=FALSE`. Treat as unavailable.

### Updating a listing
- Only fields in `ListingUpdate` can change: `title`, `description`, `subject`, `condition`, `asking_price`, `original_price`, `city`, `images`, `is_available`.
- `exam_category` and `listing_type` cannot be changed — they are absent from `ListingUpdate`.
- `is_available=True` PATCH on a sold listing (`sold_at IS NOT NULL`) is blocked by DB CHECK constraint (`no_available_sold_listing`) → DB raises IntegrityError → return 409 or let SQLAlchemy surface it as a 500; add explicit guard in service layer:
  ```python
  if listing.sold_at is not None and data.is_available is True:
      raise HTTPException(400, "Cannot reactivate a sold listing.")
  ```

### Soft delete
- `DELETE /listings/{id}` sets `is_available=FALSE, deleted_at=now()`. `sold_at` stays `NULL`.
- Conversations survive. `conversations.listing_id` FK is `ON DELETE CASCADE` in SCHEMA.md — this means if the listing *row* were hard-deleted, conversations would cascade-delete. Since we never hard-delete, all conversations remain. No cascade fires.
- `GET /listings` excludes deleted listings via `deleted_at IS NULL` filter.
- Dashboard "Selling" tab excludes deleted listings via `deleted_at IS NULL` filter.

### Passkey regeneration
- Only available when `passkey_invalidated = FALSE`.
- If listing is sold (`sold_at IS NOT NULL`, `passkey_invalidated = TRUE`) → 400.
- Regenerating passkey does not affect in-flight `initiated` transactions. If a buyer already has a payment link, they can still complete payment — that payment's webhook will reference `razorpay_payment_link_id`, not the passkey.
- New passkey shown once in the same PasskeyReveal UI as listing creation.

### Views counter
- `INCREMENT views` is a non-blocking fire-and-forget operation. Use an `UPDATE` statement rather than fetching the object and setting a field, to avoid a round-trip.
- Race: two requests hitting `GET /listings/{id}` simultaneously. Both run `UPDATE listings SET views = views + 1` — this is a safe atomic DB increment. No application-level locking needed.

---

## Files to create

```
backend/app/models/listing.py
backend/app/schemas/listing.py
backend/app/services/listing_service.py
backend/app/services/user_service.py   (get_user_by_id — if not already created by a prior spec)
backend/app/routers/listings.py
backend/alembic/versions/<hash>_add_deleted_at_to_listings.py  (only if deleted_at missing)

frontend/app/(marketplace)/listings/page.jsx
frontend/app/(marketplace)/listings/[id]/page.jsx
frontend/app/(marketplace)/listings/new/page.jsx
frontend/components/listings/CreateListingForm.jsx
frontend/components/listings/PasskeyReveal.jsx
frontend/components/listings/ListingCard.jsx
frontend/components/listings/ListingGrid.jsx
frontend/components/listings/ListingFilters.jsx
frontend/components/listings/BuyNowButton.jsx
frontend/constants/examCategories.js
frontend/constants/listingTypes.js
frontend/constants/conditions.js
```

---

## Files to modify

```
backend/app/main.py          — register listings router under /v1
frontend/lib/utils.js        — add formatPrice if not present
```

---

## New dependencies

No new dependencies. All packages are already in the stack.

---

## Security considerations

Applicable rules from CLAUDE.md:

- **Rule 1** — `ListingOut` never includes `passkey_hash`, `passkey_invalidated`, `passkey_invalidated_at`, `sold_at`, `deleted_at`. Seller contact info is never in listing responses (not present in the `listings` table — no email, phone).
- **Rule 5** — Ownership validated before every mutation: `str(listing.seller_id) != user["sub"]` → 403. Applies to `PATCH /listings/{id}`, `DELETE /listings/{id}`, `PATCH /listings/{id}/passkey`.
- **Rule 6** — Image uploads go directly to Cloudinary from the browser. The `images` field in `ListingCreate` and `ListingUpdate` accepts only already-uploaded Cloudinary URLs. FastAPI never receives image bytes.
- **Rule 7** — All DB operations use SQLAlchemy ORM. No string-interpolated SQL. The search `ilike` calls in `listing_service.py` use SQLAlchemy column methods, not f-strings — parameterized at the driver level.
- **Rule 8** — CORS restricted to `FRONTEND_URL` in production.
- **Rule 10** — `passkey_hash` never logged, never in any response. Passkey plaintext is generated in `create_listing` and returned once in the API response — never stored to DB in plaintext, never logged.

---

## Definition of done

- [ ] `GET /listings` returns 200 with all `is_available=TRUE, deleted_at=NULL` listings, ordered newest first
- [ ] `GET /listings?exam_category=JEE_MAINS` returns only JEE_MAINS listings
- [ ] `GET /listings?q=physics` returns listings with "physics" (case-insensitive) in title or description
- [ ] `GET /listings?listing_type=BOOK&condition=A` returns listings matching both filters
- [ ] `GET /listings` with no matching results returns 200 with an empty array
- [ ] `POST /listings` with valid data returns 201 with `listing` object and `passkey` (8-digit string)
- [ ] ~~`POST /listings` by a seller without `razorpay_account_id` returns 403 `"Complete payment setup to start selling."`~~ **Deferred to Spec 09** — column doesn't exist yet; gate to be added when seller onboarding lands.
- [ ] `POST /listings` with `asking_price=0` returns 422
- [ ] `POST /listings` with `exam_category="INVALID"` returns 422
- [ ] `POST /listings` with more than 5 images returns 422
- [ ] `passkey_hash` in DB matches `HMAC_SHA256(PASSKEY_HMAC_SECRET, passkey + listing_id)` — verifiable manually
- [ ] `passkey_hash`, `passkey_invalidated`, `passkey_invalidated_at`, `sold_at`, `deleted_at` never appear in any listing response
- [ ] `GET /listings/{id}` returns 200 for an existing listing (available or not); increments `views` by 1 in DB
- [ ] `GET /listings/{id}` returns 404 for a non-existent UUID
- [ ] `GET /listings/{id}` returns the listing even when `is_available=FALSE`
- [ ] `PATCH /listings/{id}` by the owner updates the supplied fields and returns 200
- [ ] `PATCH /listings/{id}` silently ignores `exam_category` and `listing_type` if sent (absent from `ListingUpdate`, Pydantic drops unknown fields; values in DB are unchanged)
- [ ] `PATCH /listings/{id}` setting `is_available=True` on a sold listing returns 400 `"Cannot reactivate a sold listing."`
- [ ] `PATCH /listings/{id}` by a non-owner returns 403 `"Not authorised."`
- [ ] `DELETE /listings/{id}` by the owner sets `is_available=FALSE, deleted_at=now()` in DB; `sold_at` remains NULL
- [ ] After `DELETE`, `GET /listings` no longer returns that listing
- [ ] After `DELETE`, `GET /listings/{id}` still returns the listing row (not 404)
- [ ] `DELETE /listings/{id}` by a non-owner returns 403 `"Not authorised."`
- [ ] `PATCH /listings/{id}/passkey` by owner returns 200 with new 8-digit `passkey`; old passkey rejected by `verify_passkey`
- [ ] `PATCH /listings/{id}/passkey` on a sold listing (`passkey_invalidated=TRUE`) returns 400 `"Cannot regenerate passkey for a sold listing."`
- [ ] `/listings` SSR page renders listing cards from API data with no hydration errors
- [ ] `/listings/[id]` SSR page shows "This listing has been sold." banner when `is_sold=true` in API response
- [ ] `/listings/[id]` SSR page shows "This listing is temporarily unavailable." banner when `is_available=false` and `is_sold=false`
- [ ] `/listings/new` redirects to `/login` when unauthenticated
- [ ] Passkey reveal screen appears after successful listing creation; passkey displayed, copy button works
- [ ] `/listings` filter changes trigger SSR re-render with filtered results via URL query params
- [ ] `formatPrice(450)` returns `"₹450"` in the UI (not `"450"` or `"INR 450"`)
- [ ] `BuyNowButton` shows passkey input only after clicking "Buy Now"; accepts only numeric input up to 8 digits

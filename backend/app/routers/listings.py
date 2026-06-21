import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis, enforce_rate_limit
from app.core.security import verify_token, optional_user
from app.schemas.listing import (
    ListingCreate, ListingCreateOut, ListingOut, ListingUpdate,
    VALID_CONDITIONS, VALID_EXAM_CATEGORIES, VALID_LISTING_TYPES,
)
from app.services import listing_service

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
    seller_id: UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    # Validate enum filters against the canonical sets — these are raw query strings,
    # so reject unknown values with 422 rather than silently returning an empty list.
    if exam_category and exam_category not in VALID_EXAM_CATEGORIES:
        raise HTTPException(status_code=422, detail="Invalid exam_category.")
    if condition and condition not in VALID_CONDITIONS:
        raise HTTPException(status_code=422, detail="Invalid condition.")
    if listing_type and listing_type not in VALID_LISTING_TYPES:
        raise HTTPException(status_code=422, detail="Invalid listing_type.")
    return await listing_service.get_listings(
        db, q=q, exam_category=exam_category, subject=subject,
        city=city, condition=condition, listing_type=listing_type,
        seller_id=str(seller_id) if seller_id else None, limit=limit, offset=offset,
    )


@router.post("", response_model=ListingCreateOut, status_code=201)
async def create_listing(
    data: ListingCreate,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    user=Depends(verify_token),
):
    seller_id = user["sub"]
    # Cap listing creation per seller to prevent unbounded row/passkey-hash flooding.
    await enforce_rate_limit(redis, f"listing_create_rate:{seller_id}", 20, 3600)
    listing, passkey = await listing_service.create_listing(db, seller_id, data)
    return ListingCreateOut(listing=ListingOut.model_validate(listing), passkey=passkey)


@router.get("/mine", response_model=list[ListingOut])
async def my_listings(
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token),
):
    # Declared BEFORE /{listing_id} so "mine" isn't parsed as a listing UUID.
    return await listing_service.get_my_listings(db, user["sub"])


@router.get("/{listing_id}", response_model=ListingOut)
async def get_listing(
    listing_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(optional_user),
):
    listing = await listing_service.get_listing_by_id(db, str(listing_id))
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
    # Don't expose deleted, paused, or moderation-hidden listings by direct ID to
    # anyone but the owner. A sold listing (sold_at set) stays visible so both parties
    # can still see the final state; a hidden/paused one (is_available FALSE, not sold)
    # is treated as not found. This is what makes a moderation takedown effective.
    is_owner = bool(user) and user["sub"] == str(listing.seller_id)
    if not is_owner and (
        listing.deleted_at is not None
        or (not listing.is_available and listing.sold_at is None)
    ):
        raise HTTPException(status_code=404, detail="Listing not found.")
    # Count a view only for a signed-in account that isn't the seller, and only
    # once per account (the service dedups). Owner views and anonymous opens
    # don't count.
    viewer_id = user["sub"] if user else None
    if viewer_id and viewer_id != str(listing.seller_id):
        await listing_service.record_unique_view(db, listing, viewer_id)
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
    try:
        return await listing_service.update_listing(db, listing, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
    if listing.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Listing not found.")
    if listing.passkey_invalidated:
        raise HTTPException(
            status_code=400, detail="Cannot regenerate passkey for a sold listing."
        )
    passkey = await listing_service.regenerate_passkey(db, listing)
    return {"passkey": passkey}

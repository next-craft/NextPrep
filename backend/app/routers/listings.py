import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_token
from app.schemas.listing import (
    ListingCreate, ListingCreateOut, ListingOut, ListingUpdate
)
from app.services import listing_service, user_service

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
    seller_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await listing_service.get_listings(
        db, q=q, exam_category=exam_category, subject=subject,
        city=city, condition=condition, listing_type=listing_type,
        seller_id=seller_id,
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
):
    listing = await listing_service.get_listing_by_id(db, str(listing_id))
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
    await listing_service.increment_views(db, listing)
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

import logging
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.college import CollegeOut
from app.schemas.listing import ListingOut
from app.services import college_service, listing_service

router = APIRouter(prefix="/colleges", tags=["colleges"])
logger = logging.getLogger(__name__)


class CollegeDetailOut(BaseModel):
    """Response for GET /colleges/{slug}: the campus plus its active listings
    (listings is empty when brief=1)."""
    model_config = ConfigDict(from_attributes=True)
    college: CollegeOut
    listings: list[ListingOut] = []


@router.get("", response_model=list[CollegeOut])
async def list_colleges(
    q: str | None = Query(None, max_length=100),
    has_listings: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    # has_listings=1 powers the /colleges index — only campuses with >=1 active
    # listing. It takes precedence over q (the index needs every campus-with-listings,
    # not a name search), so q is ignored when has_listings is set.
    if has_listings:
        rows = await college_service.colleges_with_active_listings(db)
        return [college for college, _count in rows]
    return await college_service.search_colleges(db, q)


@router.get("/{slug}", response_model=CollegeDetailOut)
async def get_college(
    slug: str = Path(..., max_length=120),
    brief: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    college = await college_service.get_by_slug(db, slug)
    if not college:
        raise HTTPException(404, "College not found.")
    # brief=1 resolves just the campus (e.g. the listings-page filter showing the
    # selected college's name) — skip the potentially large listings payload.
    if brief:
        return {"college": CollegeOut.model_validate(college), "listings": []}
    # Pass the already-resolved id so get_listings doesn't re-look-up the slug.
    listings = await listing_service.get_listings(db, college_id=college.id)
    return {
        "college": CollegeOut.model_validate(college),
        "listings": [ListingOut.model_validate(listing) for listing in listings],
    }

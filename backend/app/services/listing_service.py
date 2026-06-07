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
        passkey_hash="placeholder",  # overwritten after insert, once listing.id is known
    )
    db.add(listing)
    await db.flush()  # generates listing.id without committing

    listing.passkey_hash = hash_passkey(passkey, str(listing.id))
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

    if listing.sold_at is not None and update_data.get("is_available") is True:
        raise ValueError("Cannot reactivate a sold listing.")

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
    listing.passkey_hash = hash_passkey(passkey, str(listing.id))
    await db.commit()
    logger.info("passkey_regenerated listing=%s", listing.id)
    return passkey

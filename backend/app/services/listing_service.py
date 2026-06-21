import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, or_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listing import Listing
from app.models.listing_view import ListingView
from app.schemas.listing import ListingCreate, ListingUpdate
from app.core.security import generate_passkey, hash_passkey

logger = logging.getLogger(__name__)

# Public list bounds — keep the result set finite so a single request can't return the
# whole table.
DEFAULT_LISTINGS_LIMIT = 50
MAX_LISTINGS_LIMIT = 100


def _ilike_escape(term: str) -> str:
    """Escape LIKE/ILIKE metacharacters in user input so `%` and `_` are matched
    literally (no leading-wildcard scan abuse). Pair with ilike(..., escape='\\')."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def create_listing(
    db: AsyncSession, seller_id: str, data: ListingCreate
) -> tuple[Listing, str]:
    passkey = generate_passkey()

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
    seller_id: str | None = None,
    limit: int = DEFAULT_LISTINGS_LIMIT,
    offset: int = 0,
) -> list[Listing]:
    stmt = select(Listing).where(
        Listing.is_available == True,
        Listing.deleted_at == None,
    )
    if q:
        pattern = f"%{_ilike_escape(q)}%"
        stmt = stmt.where(
            or_(
                Listing.title.ilike(pattern, escape="\\"),
                Listing.description.ilike(pattern, escape="\\"),
            )
        )
    if exam_category:
        stmt = stmt.where(Listing.exam_category == exam_category)
    if subject:
        stmt = stmt.where(Listing.subject.ilike(f"%{_ilike_escape(subject)}%", escape="\\"))
    if city:
        stmt = stmt.where(Listing.city.ilike(f"%{_ilike_escape(city)}%", escape="\\"))
    if condition:
        stmt = stmt.where(Listing.condition == condition)
    if listing_type:
        stmt = stmt.where(Listing.listing_type == listing_type)
    if seller_id:
        stmt = stmt.where(Listing.seller_id == UUID(seller_id))

    limit = max(1, min(limit, MAX_LISTINGS_LIMIT))
    offset = max(0, offset)
    stmt = stmt.order_by(Listing.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_my_listings(db: AsyncSession, seller_id: str) -> list[Listing]:
    """The caller's own listings in all states (active/paused/sold), excluding soft-deleted."""
    stmt = (
        select(Listing)
        .where(Listing.seller_id == UUID(seller_id), Listing.deleted_at == None)  # noqa: E711
        .order_by(Listing.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_listing_by_id(db: AsyncSession, listing_id: str) -> Listing | None:
    stmt = select(Listing).where(Listing.id == UUID(listing_id))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def record_unique_view(db: AsyncSession, listing: Listing, viewer_id: str) -> None:
    """Count a view at most once per account. Caller must already have excluded
    the owner. Inserts a (listing, viewer) row idempotently; the counter only
    increments when that insert is new (a first-time viewer), so repeat opens by
    the same account never bump it."""
    insert_stmt = (
        pg_insert(ListingView)
        .values(listing_id=listing.id, viewer_id=UUID(viewer_id))
        .on_conflict_do_nothing(index_elements=["listing_id", "viewer_id"])
        .returning(ListingView.listing_id)
    )
    # RETURNING is the reliable first-time signal: a row comes back only when the row
    # was actually inserted; on conflict (already-seen viewer) nothing is returned.
    # `rowcount` is NOT reliable for ON CONFLICT DO NOTHING across drivers/poolers — it
    # could report the row as affected even on conflict, double-counting views.
    first_time = (await db.execute(insert_stmt)).first() is not None

    if first_time:
        await db.execute(
            update(Listing)
            .where(Listing.id == listing.id)
            .values(views=Listing.views + 1)
            .execution_options(synchronize_session=False)
        )
        await db.commit()
        # Load the authoritative committed count into the in-memory instance for the
        # response. A single source of truth (the DB) — avoids the previous double-write
        # where an explicit UPDATE and a manual attribute set both flushed.
        await db.refresh(listing, ["views"])
    else:
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
    passkey = generate_passkey()
    listing.passkey_hash = hash_passkey(passkey, str(listing.id))
    await db.commit()
    logger.info("passkey_regenerated listing=%s", listing.id)
    return passkey

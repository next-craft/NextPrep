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


async def colleges_with_active_listings(
    db: AsyncSession, limit: int = 500
) -> list[tuple[College, int]]:
    """For the /colleges index — only campuses with at least one active listing.
    Bounded by `limit` so the index can't run away as the campus list grows."""
    stmt = (
        select(College, func.count(Listing.id).label("n"))
        .join(Listing, Listing.college_id == College.id)
        .where(College.is_active == True,            # noqa: E712
               Listing.is_available == True,         # noqa: E712
               Listing.deleted_at == None)           # noqa: E711
        .group_by(College.id)
        .order_by(func.count(Listing.id).desc(), College.name.asc())
        .limit(limit)
    )
    return [(row[0], row[1]) for row in (await db.execute(stmt)).all()]

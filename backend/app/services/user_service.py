import logging
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.user import UserUpdate

logger = logging.getLogger(__name__)


async def count_sales(db: AsyncSession, user_id: UUID) -> int:
    """Number of completed sales for a seller — transactions that reached 'released'.

    Computed live rather than stored: the stored total_sales counter was never
    incremented on release, so it always read 0. Counting released transactions is
    the spec-canonical sales metric (analytics filter by transactions.status =
    'released', not listings.sold_at) and avoids the drift a stored counter invites.
    """
    stmt = select(func.count()).select_from(Transaction).where(
        Transaction.seller_id == user_id,
        Transaction.status == "released",
    )
    return (await db.execute(stmt)).scalar_one()


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    stmt = select(User).where(User.id == UUID(user_id))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is not None:
        # Overwrite the stale stored counter with the live count for read responses.
        # No commit happens on read paths, so this stays in-memory only.
        user.total_sales = await count_sales(db, user.id)
    return user


async def update_user(db: AsyncSession, user_id: str, data: UserUpdate) -> User | None:
    user = await get_user_by_id(db, user_id)
    if not user:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    logger.info("User updated: user=%s", user_id)
    return user

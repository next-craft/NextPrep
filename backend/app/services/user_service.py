import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserUpdate
from app.services import college_service

logger = logging.getLogger(__name__)


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    # books_sold / books_bought are maintained as counters, incremented atomically in the
    # verify-passkey path (see transaction_service.complete_transaction), so they are read
    # back directly here — no live recount needed.
    stmt = select(User).where(User.id == UUID(user_id))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_user(db: AsyncSession, user_id: str, data: UserUpdate) -> User | None:
    user = await get_user_by_id(db, user_id)
    if not user:
        return None

    update_data = data.model_dump(exclude_unset=True)

    # Validate a newly-set canonical campus and keep the college_id XOR college_other
    # invariant after partial updates: setting one source clears the other.
    if update_data.get("college_id") is not None:
        if await college_service.get_active_by_id(db, update_data["college_id"]) is None:
            raise ValueError("Unknown or inactive college.")
        update_data["college_other"] = None
    elif "college_other" in update_data and update_data["college_other"] is not None:
        # A real free-text campus is being set — drop any canonical id so the two
        # never both stick. (An explicit null only clears the free text and leaves
        # an existing college_id untouched.)
        update_data["college_id"] = None

    for field, value in update_data.items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    logger.info("User updated: user=%s", user_id)
    return user

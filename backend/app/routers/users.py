import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_token
from app.schemas.user import UserMe
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])
logger = logging.getLogger(__name__)


@router.get("/me", response_model=UserMe)
async def get_me(
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token),
):
    me = await user_service.get_user_by_id(db, user["sub"])
    if not me:
        raise HTTPException(404, "User not found.")
    return UserMe.model_validate(me)

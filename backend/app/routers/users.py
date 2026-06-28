import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_token
from app.schemas.user import UserMe, UserPublic, UserUpdate
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


@router.patch("/me", response_model=UserMe)
async def update_me(
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token),
):
    try:
        updated = await user_service.update_user(db, user["sub"], data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not updated:
        raise HTTPException(404, "User not found.")
    return UserMe.model_validate(updated)


@router.get("/{user_id}", response_model=UserPublic)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    found = await user_service.get_user_by_id(db, str(user_id))
    if not found:
        raise HTTPException(404, "User not found.")
    return UserPublic.model_validate(found)

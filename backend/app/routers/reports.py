import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.core.security import verify_token
from app.schemas.report import ReportCreate, ReportAck
from app.services import report_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", response_model=ReportAck, status_code=201)
async def create_report(
    data: ReportCreate,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    user=Depends(verify_token),
):
    return await report_service.create_report(
        db, redis, reporter_id=user["sub"], data=data
    )

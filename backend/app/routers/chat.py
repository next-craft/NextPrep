import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.core.security import verify_token
from app.schemas.chat import ConversationCreate, ConversationOut, MessageCreate, MessageOut
from app.services import chat_service

router = APIRouter(tags=["conversations"])
logger = logging.getLogger(__name__)


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token),
):
    return await chat_service.get_conversations(db, user["sub"])


@router.post("/conversations", response_model=ConversationOut)
async def create_conversation(
    data: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token),
):
    return await chat_service.get_or_create_conversation(db, data.listing_id, user["sub"])


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
async def get_messages(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    user=Depends(verify_token),
):
    return await chat_service.get_messages(db, redis, conversation_id, user["sub"])


@router.post("/conversations/{conversation_id}/messages", response_model=MessageOut, status_code=201)
async def send_message(
    conversation_id: UUID,
    data: MessageCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    user=Depends(verify_token),
):
    return await chat_service.send_message(db, redis, conversation_id, user["sub"], data.body, background_tasks)


@router.patch("/conversations/{conversation_id}/messages/read", status_code=204)
async def mark_read(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    user=Depends(verify_token),
):
    await chat_service.mark_read(db, redis, conversation_id, user["sub"])

import json
import logging
from uuid import UUID

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import supabase_admin
from app.models.conversation import Conversation
from app.models.listing import Listing
from app.models.message import Message
from app.schemas.chat import MessageOut
from app.services import notification_service

logger = logging.getLogger(__name__)

RATE_LIMIT_PER_HOUR = 100
MESSAGE_CACHE_TTL_SECONDS = 30


def _cache_key(conversation_id: UUID) -> str:
    return f"chat:{conversation_id}"


def _rate_key(conversation_id: UUID, sender_id: str) -> str:
    return f"chat_rate:{conversation_id}:{sender_id}"


def _serialize_message(message: Message) -> dict:
    return {
        "id": str(message.id),
        "conversation_id": str(message.conversation_id),
        "sender_id": str(message.sender_id),
        "body": message.body,
        "is_read": message.is_read,
        "created_at": message.created_at.isoformat(),
    }


async def _notify_first_message(conversation_id_str: str, recipient_user_id_str: str) -> None:
    recipient_email = await supabase_admin.fetch_user_email(recipient_user_id_str)
    if recipient_email:
        await notification_service.send_new_message_email(UUID(conversation_id_str), recipient_email)
    else:
        logger.warning("Could not resolve seller email: conversation=%s", conversation_id_str)


async def get_or_create_conversation(
    db: AsyncSession,
    listing_id: UUID,
    buyer_id: str,
) -> Conversation:
    """Returns the existing buyer/listing conversation, or creates one. Falls
    back to fetching the existing row if a concurrent request wins the
    UNIQUE(listing_id, buyer_id) race."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.listing_id == listing_id,
            Conversation.buyer_id == buyer_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    listing = await db.get(Listing, listing_id)
    if not listing or not listing.is_available:
        raise HTTPException(404, "Listing not found.")
    if str(listing.seller_id) == buyer_id:
        raise HTTPException(403, "You cannot message yourself about your own listing.")

    conversation = Conversation(
        listing_id=listing_id,
        buyer_id=buyer_id,
        seller_id=listing.seller_id,
    )
    db.add(conversation)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        result = await db.execute(
            select(Conversation).where(
                Conversation.listing_id == listing_id,
                Conversation.buyer_id == buyer_id,
            )
        )
        return result.scalar_one()

    await db.refresh(conversation)
    logger.info(
        "Conversation created: conversation=%s listing=%s buyer=%s seller=%s",
        conversation.id, listing_id, buyer_id, listing.seller_id,
    )
    return conversation


async def get_conversations(db: AsyncSession, user_id: str) -> list[Conversation]:
    result = await db.execute(
        select(Conversation)
        .where(
            (Conversation.buyer_id == user_id) | (Conversation.seller_id == user_id)
        )
        .order_by(Conversation.created_at.desc())
    )
    return result.scalars().all()


async def get_messages(
    db: AsyncSession,
    redis,
    conversation_id: UUID,
    user_id: str,
) -> list:
    await _assert_participant(db, conversation_id, user_id)

    cache_key = _cache_key(conversation_id)
    cached = await redis.get(cache_key)
    if cached:
        messages = json.loads(cached)
    else:
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        msgs = result.scalars().all()
        messages = [_serialize_message(m) for m in msgs]
        await redis.set(cache_key, json.dumps(messages), ex=MESSAGE_CACHE_TTL_SECONDS)

    for m in messages:
        m["is_mine"] = m["sender_id"] == user_id
    return messages


async def send_message(
    db: AsyncSession,
    redis,
    conversation_id: UUID,
    sender_id: str,
    body: str,
    background_tasks: BackgroundTasks,
) -> MessageOut:
    """Persists the message, enforces the per-conversation hourly rate limit,
    invalidates the message cache, and queues the first-message email
    (at most once per conversation, via an atomic flag flip)."""
    conversation = await _assert_participant(db, conversation_id, sender_id)

    rate_key = _rate_key(conversation_id, sender_id)
    count = await redis.get(rate_key)
    if count and int(count) >= RATE_LIMIT_PER_HOUR:
        raise HTTPException(429, "Message rate limit reached. Try again later.")

    message = Message(
        conversation_id=conversation_id,
        sender_id=sender_id,
        body=body,
    )
    db.add(message)

    new_count = await redis.incr(rate_key)
    if new_count == 1:
        await redis.expire(rate_key, 3600)

    await redis.delete(_cache_key(conversation_id))

    if not conversation.first_message_notified:
        result = await db.execute(
            update(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.first_message_notified == False,  # noqa: E712
            )
            .values(first_message_notified=True)
            .returning(Conversation.id)
        )
        await db.flush()
        if result.scalar_one_or_none() is not None:
            background_tasks.add_task(
                _notify_first_message,
                str(conversation_id),
                str(conversation.seller_id),
            )

    await db.commit()
    await db.refresh(message)
    logger.info(
        "Message sent: message=%s conversation=%s sender=%s",
        message.id, conversation_id, sender_id,
    )
    return MessageOut(**_serialize_message(message), is_mine=True)


async def mark_read(
    db: AsyncSession,
    redis,
    conversation_id: UUID,
    user_id: str,
) -> None:
    """Marks all messages from the other participant as read and invalidates
    the message cache so the next poll reflects the updated read state."""
    await _assert_participant(db, conversation_id, user_id)
    await db.execute(
        update(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.sender_id != user_id,
            Message.is_read == False,  # noqa: E712
        )
        .values(is_read=True)
    )
    await db.commit()
    await redis.delete(_cache_key(conversation_id))


async def _assert_participant(
    db: AsyncSession,
    conversation_id: UUID,
    user_id: str,
) -> Conversation:
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(404, "Conversation not found.")
    if str(conversation.buyer_id) != user_id and str(conversation.seller_id) != user_id:
        raise HTTPException(403, "Not a participant in this conversation.")
    return conversation

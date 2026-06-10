from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class ConversationCreate(BaseModel):
    listing_id: UUID


class ConversationOut(BaseModel):
    id: UUID
    listing_id: UUID | None
    buyer_id: UUID
    seller_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageCreate(BaseModel):
    body: str

    @field_validator("body")
    @classmethod
    def body_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message body cannot be empty.")
        if len(v) > 2000:
            raise ValueError("Message too long (max 2000 characters).")
        return v


class MessageOut(BaseModel):
    id: UUID
    conversation_id: UUID
    sender_id: UUID
    body: str
    is_read: bool
    is_mine: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

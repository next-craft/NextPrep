import logging
from sqlalchemy import Boolean, Column, ForeignKey, String, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

logger = logging.getLogger(__name__)


class Message(Base):
    __tablename__ = "messages"

    id              = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    sender_id       = Column(UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    body            = Column(String, nullable=False)
    is_read         = Column(Boolean, nullable=False, server_default="false")
    created_at      = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))

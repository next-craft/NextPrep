import logging
from sqlalchemy import Boolean, Column, ForeignKey, TIMESTAMP, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

logger = logging.getLogger(__name__)


class Conversation(Base):
    __tablename__ = "conversations"

    id                     = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    listing_id             = Column(UUID(as_uuid=True), ForeignKey("listings.id", ondelete="SET NULL"))
    buyer_id               = Column(UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    seller_id              = Column(UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    first_message_notified = Column(Boolean, nullable=False, server_default="false")
    created_at             = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (
        UniqueConstraint("listing_id", "buyer_id", name="uq_conversation_listing_buyer"),
        # No explicit schema — uses Supabase default search_path (public)
    )

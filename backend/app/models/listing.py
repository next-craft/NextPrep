import logging
from sqlalchemy import (
    ARRAY, Boolean, CheckConstraint, Column, ForeignKey,
    Integer, String, TIMESTAMP, text,
)
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

logger = logging.getLogger(__name__)


class Listing(Base):
    __tablename__ = "listings"

    id                     = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    seller_id              = Column(UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    title                  = Column(String, nullable=False)
    description            = Column(String)
    exam_category          = Column(String, nullable=False)
    subject                = Column(String)
    listing_type           = Column(String, nullable=False)
    condition              = Column(String, nullable=False)
    asking_price           = Column(Integer, nullable=False)
    original_price         = Column(Integer)
    city                   = Column(String, nullable=False)
    images                 = Column(ARRAY(String))
    is_available           = Column(Boolean, nullable=False, server_default="true")
    sold_at                = Column(TIMESTAMP(timezone=True))
    passkey_hash           = Column(String, nullable=False)
    passkey_invalidated    = Column(Boolean, nullable=False, server_default="false")
    passkey_invalidated_at = Column(TIMESTAMP(timezone=True))
    views                  = Column(Integer, nullable=False, server_default="0")
    created_at             = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    deleted_at             = Column(TIMESTAMP(timezone=True))

    __table_args__ = (
        CheckConstraint("listing_type IN ('BOOK', 'NOTES', 'MODULE', 'BUNDLE')", name="ck_listing_type"),
        CheckConstraint("condition IN ('A', 'B', 'C')", name="ck_condition"),
        CheckConstraint("asking_price > 0", name="ck_asking_price_positive"),
        CheckConstraint(
            "NOT (is_available = TRUE AND (sold_at IS NOT NULL OR deleted_at IS NOT NULL))",
            name="no_available_sold_listing",
        ),
        CheckConstraint(
            "NOT (sold_at IS NOT NULL AND deleted_at IS NOT NULL)",
            name="sold_xor_deleted",
        ),
        # No explicit schema — uses Supabase default search_path (public)
    )

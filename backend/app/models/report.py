import logging
from sqlalchemy import (
    CheckConstraint, Column, ForeignKey, String, TIMESTAMP, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

logger = logging.getLogger(__name__)


class Report(Base):
    __tablename__ = "reports"

    id          = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    listing_id  = Column(UUID(as_uuid=True), ForeignKey("listings.id", ondelete="CASCADE"), nullable=False)
    reporter_id = Column(UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    reason      = Column(String, nullable=False)
    note        = Column(String)
    status      = Column(String, nullable=False, server_default="open")
    created_at  = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (
        CheckConstraint(
            "reason IN ('PIRACY', 'CONTACT_INFO', 'SPAM', 'NOT_STUDY_MATERIAL', "
            "'PROHIBITED', 'ABUSIVE', 'OTHER')",
            name="ck_report_reason",
        ),
        CheckConstraint(
            "status IN ('open', 'actioned', 'dismissed')",
            name="ck_report_status",
        ),
        UniqueConstraint("listing_id", "reporter_id", name="uq_report_once"),
        # No explicit schema — uses Supabase default search_path (public)
    )

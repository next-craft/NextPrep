import logging
from sqlalchemy import Column, ForeignKey, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

logger = logging.getLogger(__name__)


class ListingView(Base):
    """One row per (listing, viewer) pair — the record that a given account has
    seen a given listing. Its composite primary key makes inserts idempotent, so
    a listing's view counter only ever increments once per account (and never for
    the owner, who is excluded before we record). Anonymous viewers are not
    recorded — a view is a unique signed-in, non-owner account opening the page.
    """

    __tablename__ = "listing_views"

    listing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("listings.id", ondelete="CASCADE"),
        primary_key=True,
    )
    viewer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("public.users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

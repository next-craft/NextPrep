import logging
from sqlalchemy import Column, ForeignKey, Index, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

logger = logging.getLogger(__name__)


class Transaction(Base):
    """A verified, completed in-person exchange. A row exists only once a buyer has
    entered the listing's correct passkey at the meetup — there is no pending/payment
    state. One row per sold listing; ratings hang off it (one rating per transaction)."""

    __tablename__ = "transactions"

    id         = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    listing_id = Column(UUID(as_uuid=True), ForeignKey("listings.id", ondelete="SET NULL"))
    buyer_id   = Column(UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    seller_id  = Column(UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (
        # A listing sells exactly once -> at most one verified transaction per listing.
        # listing_id becomes NULL on listing delete (FK SET NULL); NULLs are not deduped.
        Index(
            "uq_transaction_per_listing",
            "listing_id",
            unique=True,
            postgresql_where=text("listing_id IS NOT NULL"),
        ),
        # No explicit schema — uses Supabase default search_path (public)
    )

import logging
from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, TIMESTAMP, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

logger = logging.getLogger(__name__)


class SellerRating(Base):
    __tablename__ = "seller_ratings"

    id             = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False)
    rated_by       = Column(UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    seller_id      = Column(UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    rating         = Column(Integer, nullable=False)
    created_at     = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (
        UniqueConstraint("transaction_id", "rated_by", name="uq_rating_transaction_rater"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_rating_range"),
    )

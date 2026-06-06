import logging
from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, String, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

logger = logging.getLogger(__name__)


class Transaction(Base):
    __tablename__ = "transactions"

    id                        = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    listing_id                = Column(UUID(as_uuid=True), ForeignKey("listings.id", ondelete="SET NULL"))
    buyer_id                  = Column(UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    seller_id                 = Column(UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    amount_rupees             = Column(Integer, nullable=False)
    platform_fee_rupees       = Column(Integer, nullable=False, server_default="0")
    seller_payout_rupees      = Column(Integer, nullable=False)
    razorpay_payment_link_id  = Column(String, unique=True)
    razorpay_payment_link_url = Column(String)
    razorpay_payment_id       = Column(String, unique=True)
    status                    = Column(String, nullable=False, server_default="initiated")
    created_at                = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    released_at               = Column(TIMESTAMP(timezone=True))
    refunded_at               = Column(TIMESTAMP(timezone=True))

    __table_args__ = (
        CheckConstraint("status IN ('initiated', 'released', 'cancelled')", name="ck_transaction_status"),
        CheckConstraint("amount_rupees > 0", name="ck_amount_positive"),
        CheckConstraint("seller_payout_rupees >= 0", name="ck_payout_nonnegative"),
    )

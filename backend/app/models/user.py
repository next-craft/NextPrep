import logging
from sqlalchemy import Boolean, CheckConstraint, Column, Integer, Numeric, String, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

logger = logging.getLogger(__name__)


class User(Base):
    __tablename__ = "users"

    id            = Column(UUID(as_uuid=True), primary_key=True)
    full_name     = Column(String, nullable=False)
    city          = Column(String)
    avatar_url    = Column(String)
    is_verified   = Column(Boolean, nullable=False, server_default="false")
    seller_rating = Column(Numeric(3, 2))
    total_sales   = Column(Integer, nullable=False, server_default="0")
    created_at    = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (
        CheckConstraint(
            "seller_rating IS NULL OR seller_rating BETWEEN 1.00 AND 5.00",
            name="ck_seller_rating_range",
        ),
        {"schema": "public"},
    )

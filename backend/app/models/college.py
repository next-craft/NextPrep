import logging
from sqlalchemy import Boolean, Column, String, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

logger = logging.getLogger(__name__)


class College(Base):
    __tablename__ = "colleges"

    id         = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    slug       = Column(String, nullable=False, unique=True)
    name       = Column(String, nullable=False, unique=True)
    state      = Column(String)   # igod state/UT, for disambiguation
    city       = Column(String)   # igod district, for disambiguation
    is_active  = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    # No explicit schema — public default search_path, matching Listing.

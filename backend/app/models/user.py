import logging
from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, Integer, Numeric, String, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base

logger = logging.getLogger(__name__)


class User(Base):
    __tablename__ = "users"

    # Spec 06 declares this PK as a FK into auth.users(id) ON DELETE CASCADE, but we do NOT
    # add that FK: the app should not own a constraint into Supabase's managed `auth` schema,
    # and test fixtures insert public.users rows directly. The handle_new_user trigger keeps
    # public.users in sync with auth.users instead. See DECISIONS.md.
    id            = Column(UUID(as_uuid=True), primary_key=True)
    full_name     = Column(String, nullable=False)
    state         = Column(String)  # state/UT (igod); nullable
    city          = Column(String)  # district within `state` (igod); nullable
    # colleges lives in the public schema (default search_path), like Listing -> reference "colleges.id".
    college_id    = Column(UUID(as_uuid=True), ForeignKey("colleges.id", ondelete="SET NULL"))  # canonical campus; nullable
    college_other = Column(String)  # free-text campus not yet in `colleges`; display-only, never filtered
    avatar_url    = Column(String)
    # Verification badge — earned, not granted at signup: True once books_sold >= 10
    # verified transactions. Set in the verify-passkey path; no longer set by the trigger.
    is_verified   = Column(Boolean, nullable=False, server_default="false")
    seller_rating = Column(Numeric(3, 2))
    books_sold    = Column(Integer, nullable=False, server_default="0")
    books_bought  = Column(Integer, nullable=False, server_default="0")
    created_at    = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    # One-time signup welcome email guard. Set TRUE the first time the welcome sweep
    # (app/jobs/scheduler.py) emails the account; never reset, so later logins never resend.
    welcome_email_sent = Column(Boolean, nullable=False, server_default="false")

    __table_args__ = (
        CheckConstraint(
            "seller_rating IS NULL OR seller_rating BETWEEN 1.00 AND 5.00",
            name="ck_seller_rating_range",
        ),
        {"schema": "public"},
    )

    # Canonical campus, eager-loaded so UserMe/UserPublic can embed CollegeBrief.
    college = relationship("College", lazy="selectin")

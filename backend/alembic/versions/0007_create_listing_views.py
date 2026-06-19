"""Create listing_views table — unique-per-account view dedup

Records that an account has viewed a listing so the listings.views counter
increments at most once per account (owner excluded, recorded by the app).

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "listing_views",
        sa.Column("listing_id", UUID(as_uuid=True), nullable=False),
        sa.Column("viewer_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("listing_id", "viewer_id", name="pk_listing_views"),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["viewer_id"], ["public.users.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("listing_views")

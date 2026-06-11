"""Add original_price > 0 CHECK constraint to listings

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-11
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Spec 06 declares `original_price INTEGER CHECK (original_price > 0)`; migration 0001
    # only added the asking_price check. original_price is nullable (optional display field).
    op.create_check_constraint(
        "ck_original_price_positive",
        "listings",
        "original_price IS NULL OR original_price > 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_original_price_positive", "listings", type_="check")

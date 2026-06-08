"""Add razorpay_account_id to users

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-08
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("razorpay_account_id", sa.String(), nullable=True),
        schema="public",
    )


def downgrade() -> None:
    op.drop_column("users", "razorpay_account_id", schema="public")

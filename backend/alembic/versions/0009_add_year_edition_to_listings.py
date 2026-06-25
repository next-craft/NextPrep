"""Add listings.year and listings.edition — optional book metadata

Both columns are nullable so existing listings are unaffected and sellers may
add them later via PATCH /listings/{id}. `year` is range-checked 2015–2026 to
match the create/edit dropdown; `edition` is free text.

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("listings", sa.Column("year", sa.Integer(), nullable=True))
    op.add_column("listings", sa.Column("edition", sa.String(), nullable=True))
    op.create_check_constraint(
        "ck_year_range",
        "listings",
        "year IS NULL OR (year >= 2015 AND year <= 2026)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_year_range", "listings", type_="check")
    op.drop_column("listings", "edition")
    op.drop_column("listings", "year")

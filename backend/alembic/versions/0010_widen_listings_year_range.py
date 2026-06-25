"""Widen listings.year CHECK range to 2000–2026

0009 introduced ck_year_range as 2015–2026. Widen the lower bound to 2000 so
older editions can be listed. Recreate the constraint with the new bounds.

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-25
"""
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_year_range", "listings", type_="check")
    op.create_check_constraint(
        "ck_year_range",
        "listings",
        "year IS NULL OR (year >= 2000 AND year <= 2026)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_year_range", "listings", type_="check")
    op.create_check_constraint(
        "ck_year_range",
        "listings",
        "year IS NULL OR (year >= 2015 AND year <= 2026)",
    )

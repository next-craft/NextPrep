"""Create reports table (Spec 03 — content policy)

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("listing_id", UUID(as_uuid=True), nullable=False),
        sa.Column("reporter_id", UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("note", sa.String()),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "reason IN ('PIRACY', 'CONTACT_INFO', 'SPAM', 'NOT_STUDY_MATERIAL', "
            "'PROHIBITED', 'ABUSIVE', 'OTHER')",
            name="ck_report_reason",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'actioned', 'dismissed')",
            name="ck_report_status",
        ),
        sa.UniqueConstraint("listing_id", "reporter_id", name="uq_report_once"),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reporter_id"], ["public.users.id"], ondelete="CASCADE"),
    )

    # Supports the moderator triage query: open reports, newest first.
    op.create_index(
        "ix_reports_status",
        "reports",
        ["status", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_reports_status", table_name="reports")
    op.drop_table("reports")

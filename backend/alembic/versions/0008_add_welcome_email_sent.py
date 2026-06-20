"""Add users.welcome_email_sent — one-time signup welcome email guard

A permanent flag so the welcome email is sent exactly once per account, ever.
Signing out and back in never resends it. New rows default FALSE; the welcome
sweep (app/jobs/scheduler.py) sends to FALSE rows and flips them TRUE.

Existing users are backfilled to TRUE so the first sweep does not email the
entire current user base — only accounts created after this migration are welcomed.

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "welcome_email_sent",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        schema="public",
    )
    # Backfill: every account that already exists has, in effect, already "started" —
    # mark them welcomed so the sweep only ever emails genuinely new signups.
    op.execute("UPDATE public.users SET welcome_email_sent = TRUE")


def downgrade() -> None:
    op.drop_column("users", "welcome_email_sent", schema="public")

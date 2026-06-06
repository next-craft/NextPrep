"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("city", sa.String()),
        sa.Column("avatar_url", sa.String()),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("seller_rating", sa.Numeric(3, 2)),
        sa.Column("total_sales", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "seller_rating IS NULL OR seller_rating BETWEEN 1.00 AND 5.00",
            name="ck_seller_rating_range",
        ),
        schema="public",
    )

    op.create_table(
        "listings",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("seller_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String()),
        sa.Column("exam_category", sa.String(), nullable=False),
        sa.Column("subject", sa.String()),
        sa.Column("listing_type", sa.String(), nullable=False),
        sa.Column("condition", sa.String(), nullable=False),
        sa.Column("asking_price", sa.Integer(), nullable=False),
        sa.Column("original_price", sa.Integer()),
        sa.Column("city", sa.String(), nullable=False),
        sa.Column("images", ARRAY(sa.String())),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sold_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("passkey_hash", sa.String(), nullable=False),
        sa.Column("passkey_invalidated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("passkey_invalidated_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("views", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True)),
        sa.CheckConstraint(
            "listing_type IN ('BOOK', 'NOTES', 'MODULE', 'BUNDLE')",
            name="ck_listing_type",
        ),
        sa.CheckConstraint("condition IN ('A', 'B', 'C')", name="ck_condition"),
        sa.CheckConstraint("asking_price > 0", name="ck_asking_price_positive"),
        sa.CheckConstraint(
            "NOT (is_available = TRUE AND (sold_at IS NOT NULL OR deleted_at IS NOT NULL))",
            name="no_available_sold_listing",
        ),
        sa.CheckConstraint(
            "NOT (sold_at IS NOT NULL AND deleted_at IS NOT NULL)",
            name="sold_xor_deleted",
        ),
        sa.ForeignKeyConstraint(["seller_id"], ["public.users.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "conversations",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("listing_id", UUID(as_uuid=True)),
        sa.Column("buyer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("seller_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "first_message_notified",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["buyer_id"], ["public.users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["seller_id"], ["public.users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("listing_id", "buyer_id", name="uq_conversation_listing_buyer"),
    )

    op.create_table(
        "messages",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("conversation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("sender_id", UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.String(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["sender_id"], ["public.users.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "transactions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("listing_id", UUID(as_uuid=True)),
        sa.Column("buyer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("seller_id", UUID(as_uuid=True), nullable=False),
        sa.Column("amount_rupees", sa.Integer(), nullable=False),
        sa.Column(
            "platform_fee_rupees", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("seller_payout_rupees", sa.Integer(), nullable=False),
        sa.Column("razorpay_payment_link_id", sa.String(), unique=True),
        sa.Column("razorpay_payment_link_url", sa.String()),
        sa.Column("razorpay_payment_id", sa.String(), unique=True),
        sa.Column(
            "status", sa.String(), nullable=False, server_default="initiated"
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("released_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("refunded_at", sa.TIMESTAMP(timezone=True)),
        sa.CheckConstraint(
            "status IN ('initiated', 'released', 'cancelled')",
            name="ck_transaction_status",
        ),
        sa.CheckConstraint("amount_rupees > 0", name="ck_amount_positive"),
        sa.CheckConstraint("seller_payout_rupees >= 0", name="ck_payout_nonnegative"),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["buyer_id"], ["public.users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["seller_id"], ["public.users.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "seller_ratings",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("transaction_id", UUID(as_uuid=True), nullable=False),
        sa.Column("rated_by", UUID(as_uuid=True), nullable=False),
        sa.Column("seller_id", UUID(as_uuid=True), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_rating_range"),
        sa.UniqueConstraint(
            "transaction_id", "rated_by", name="uq_rating_transaction_rater"
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"], ["transactions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["rated_by"], ["public.users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["seller_id"], ["public.users.id"], ondelete="CASCADE"),
    )

    # --- Indexes ---
    op.create_index(
        "idx_listings_available",
        "listings",
        ["is_available", "exam_category", "listing_type"],
    )
    op.create_index("idx_listings_seller_id", "listings", ["seller_id"])
    op.create_index(
        "idx_listings_created_at", "listings", [sa.text("created_at DESC")]
    )
    op.create_index("idx_conversations_buyer_id", "conversations", ["buyer_id"])
    op.create_index("idx_conversations_seller_id", "conversations", ["seller_id"])
    op.create_index(
        "idx_messages_conversation_id",
        "messages",
        ["conversation_id", "created_at"],
    )
    op.create_index("idx_transactions_buyer_id", "transactions", ["buyer_id"])
    op.create_index("idx_transactions_seller_id", "transactions", ["seller_id"])
    op.create_index(
        "one_active_transaction_per_buyer_listing",
        "transactions",
        ["listing_id", "buyer_id"],
        unique=True,
        postgresql_where=sa.text("status = 'initiated'"),
    )
    op.create_index(
        "idx_transactions_status_created",
        "transactions",
        ["status", "created_at"],
        postgresql_where=sa.text("status = 'initiated'"),
    )


def downgrade() -> None:
    op.drop_index("idx_transactions_status_created", table_name="transactions")
    op.drop_index("one_active_transaction_per_buyer_listing", table_name="transactions")
    op.drop_index("idx_transactions_seller_id", table_name="transactions")
    op.drop_index("idx_transactions_buyer_id", table_name="transactions")
    op.drop_index("idx_messages_conversation_id", table_name="messages")
    op.drop_index("idx_conversations_seller_id", table_name="conversations")
    op.drop_index("idx_conversations_buyer_id", table_name="conversations")
    op.drop_index("idx_listings_created_at", table_name="listings")
    op.drop_index("idx_listings_seller_id", table_name="listings")
    op.drop_index("idx_listings_available", table_name="listings")
    op.drop_table("seller_ratings")
    op.drop_table("transactions")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("listings")
    op.drop_table("users", schema="public")

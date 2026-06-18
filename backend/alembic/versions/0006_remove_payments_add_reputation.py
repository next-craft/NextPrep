"""Remove payments/Razorpay; passkey-verified transactions + reputation

Drops all payment/Razorpay state and reframes `transactions` as a record of a
verified, completed in-person exchange (one row per sold listing). Adds the
reputation counters and rating review text.

- transactions: drop amount/payout/razorpay/status/released/refunded columns;
  every remaining row is a verified transaction. Historical non-`released`
  rows are deleted (they were never completed exchanges).
- users: rename total_sales -> books_sold, add books_bought, drop
  razorpay_account_id. `is_verified` is repurposed as the verification badge
  (books_sold >= 10), backfilled here and no longer granted by the signup trigger.
- seller_ratings: add nullable `review` text.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop never-completed transactions while `status` still exists. Each remaining
    #    row becomes a "verified transaction" in the new model. seller_ratings rows
    #    tied to them cascade away (FK ON DELETE CASCADE), as intended.
    op.execute("DELETE FROM transactions WHERE status <> 'released'")

    # 2. users: rename the sales counter and add the buyer counter.
    op.alter_column("users", "total_sales", new_column_name="books_sold", schema="public")
    op.add_column(
        "users",
        sa.Column("books_bought", sa.Integer(), nullable=False, server_default="0"),
        schema="public",
    )

    # 3. Backfill the counters from the surviving (verified) transactions.
    op.execute(
        "UPDATE public.users u SET books_sold = "
        "COALESCE((SELECT count(*) FROM transactions t WHERE t.seller_id = u.id), 0)"
    )
    op.execute(
        "UPDATE public.users u SET books_bought = "
        "COALESCE((SELECT count(*) FROM transactions t WHERE t.buyer_id = u.id), 0)"
    )

    # 4. Drop the status-dependent partial indexes before dropping the column.
    op.drop_index("idx_transactions_status_created", table_name="transactions")
    op.drop_index("one_active_transaction_per_buyer_listing", table_name="transactions")

    # 5. Drop payment check constraints, then the payment/razorpay columns.
    op.drop_constraint("ck_transaction_status", "transactions", type_="check")
    op.drop_constraint("ck_amount_positive", "transactions", type_="check")
    op.drop_constraint("ck_payout_nonnegative", "transactions", type_="check")
    for col in (
        "amount_rupees",
        "platform_fee_rupees",
        "seller_payout_rupees",
        "razorpay_payment_link_id",
        "razorpay_payment_link_url",
        "razorpay_payment_id",
        "status",
        "released_at",
        "refunded_at",
    ):
        op.drop_column("transactions", col)

    # 6. A listing can be sold exactly once -> at most one verified transaction per
    #    listing (NULL listing_id allowed many times: FK is ON DELETE SET NULL).
    op.create_index(
        "uq_transaction_per_listing",
        "transactions",
        ["listing_id"],
        unique=True,
        postgresql_where=sa.text("listing_id IS NOT NULL"),
    )

    # 7. seller_ratings: optional free-text review alongside the 1-5 rating.
    op.add_column("seller_ratings", sa.Column("review", sa.String(), nullable=True))

    # 8. users: drop the now-unused Razorpay linked-account id.
    op.drop_column("users", "razorpay_account_id", schema="public")

    # 9. Repurpose is_verified as the verification badge (>= 10 verified sales).
    op.execute("UPDATE public.users SET is_verified = (books_sold >= 10)")

    # 10. Signup trigger no longer grants is_verified from the OAuth email flag — the
    #     badge is earned through verified transactions, set in the verify-passkey path.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION handle_new_user()
        RETURNS TRIGGER AS $$
        BEGIN
          INSERT INTO public.users (id, full_name, avatar_url)
          VALUES (
            NEW.id,
            COALESCE(NEW.raw_user_meta_data->>'full_name', 'User'),
            NEW.raw_user_meta_data->>'avatar_url'
          );
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER;
        """
    )


def downgrade() -> None:
    # Restore the signup trigger to its email-derived is_verified form.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION handle_new_user()
        RETURNS TRIGGER AS $$
        BEGIN
          INSERT INTO public.users (id, full_name, avatar_url, is_verified)
          VALUES (
            NEW.id,
            COALESCE(NEW.raw_user_meta_data->>'full_name', 'User'),
            NEW.raw_user_meta_data->>'avatar_url',
            COALESCE((NEW.raw_user_meta_data->>'email_verified')::boolean, FALSE)
          );
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER;
        """
    )

    op.add_column(
        "users",
        sa.Column("razorpay_account_id", sa.String(), nullable=True),
        schema="public",
    )

    op.drop_column("seller_ratings", "review")

    op.drop_index("uq_transaction_per_listing", table_name="transactions")

    # Re-add payment/razorpay columns (nullable — historical values are unrecoverable).
    op.add_column("transactions", sa.Column("amount_rupees", sa.Integer(), nullable=True))
    op.add_column(
        "transactions",
        sa.Column("platform_fee_rupees", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("transactions", sa.Column("seller_payout_rupees", sa.Integer(), nullable=True))
    op.add_column("transactions", sa.Column("razorpay_payment_link_id", sa.String(), nullable=True))
    op.add_column("transactions", sa.Column("razorpay_payment_link_url", sa.String(), nullable=True))
    op.add_column("transactions", sa.Column("razorpay_payment_id", sa.String(), nullable=True))
    op.add_column(
        "transactions",
        sa.Column("status", sa.String(), nullable=False, server_default="released"),
    )
    op.add_column("transactions", sa.Column("released_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("transactions", sa.Column("refunded_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.create_unique_constraint(None, "transactions", ["razorpay_payment_link_id"])
    op.create_unique_constraint(None, "transactions", ["razorpay_payment_id"])
    op.create_check_constraint(
        "ck_transaction_status",
        "transactions",
        "status IN ('initiated', 'released', 'cancelled')",
    )
    op.create_check_constraint("ck_amount_positive", "transactions", "amount_rupees > 0")
    op.create_check_constraint("ck_payout_nonnegative", "transactions", "seller_payout_rupees >= 0")
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

    op.drop_column("users", "books_bought", schema="public")
    op.alter_column("users", "books_sold", new_column_name="total_sales", schema="public")

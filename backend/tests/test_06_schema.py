"""
test_06_schema.py
=================
Pure unit tests for the SMEI database schema (spec: technical/schema.md).

Strategy:
- Set a dummy DATABASE_URL env var before any app imports so that
  pydantic-settings does not raise a ValidationError at import time.
- Never connect to a real database — all assertions use SQLAlchemy metadata
  introspection via model.__table__ attributes.
- No pytest-asyncio, no TestClient, no fixtures required.
"""

import importlib
import os
import sys

# ---------------------------------------------------------------------------
# Provide required env vars before any app module is imported.
# This must happen before the first `from app.*` import.
# ---------------------------------------------------------------------------
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("PASSKEY_HMAC_SECRET", "0" * 64)
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "dummy_service_role_key")
os.environ.setdefault("RESEND_API_KEY", "re_dummy")
os.environ.setdefault("NEXT_PUBLIC_SUPABASE_URL", "https://dummy.supabase.co")
os.environ.setdefault("CLOUDINARY_CLOUD_NAME", "dummy_cloud")
os.environ.setdefault("CLOUDINARY_API_KEY", "dummy_api_key")
os.environ.setdefault("CLOUDINARY_API_SECRET", "dummy_api_secret")

# ---------------------------------------------------------------------------
# Now safe to import app modules.
# ---------------------------------------------------------------------------
from sqlalchemy import CheckConstraint, Integer, UniqueConstraint  # noqa: E402
from sqlalchemy.dialects.postgresql import UUID  # noqa: E402

# Models imported individually (mirrors what the spec defines as 6 discrete modules)
from app.models.user import User  # noqa: E402
from app.models.listing import Listing  # noqa: E402
from app.models.conversation import Conversation  # noqa: E402
from app.models.message import Message  # noqa: E402
from app.models.transaction import Transaction  # noqa: E402
from app.models.seller_rating import SellerRating  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _constraint_names(model):
    """Return the set of all named constraint names declared in __table_args__."""
    args = getattr(model, "__table_args__", ())
    # __table_args__ may be a tuple or a tuple ending with a dict
    if isinstance(args, dict):
        return set()
    names = set()
    for item in args:
        if isinstance(item, (CheckConstraint, UniqueConstraint)):
            if item.name:
                names.add(item.name)
    return names


def _check_constraint_names(model):
    names = set()
    args = getattr(model, "__table_args__", ())
    if isinstance(args, dict):
        return names
    for item in args:
        if isinstance(item, CheckConstraint) and item.name:
            names.add(item.name)
    return names


def _unique_constraint_names(model):
    names = set()
    args = getattr(model, "__table_args__", ())
    if isinstance(args, dict):
        return names
    for item in args:
        if isinstance(item, UniqueConstraint) and item.name:
            names.add(item.name)
    return names


def _column(model, col_name):
    """Return the Column object for col_name, or None."""
    return model.__table__.columns.get(col_name)


def _fk_targets(model, col_name):
    """Return a set of FK target strings like 'public.users.id' for a column."""
    col = _column(model, col_name)
    if col is None:
        return set()
    return {fk.target_fullname for fk in col.foreign_keys}


# ===========================================================================
# 1. MODEL IMPORTS — all 6 classes must be importable from app.models
# ===========================================================================

class TestModelImports:
    def test_user_importable_from_app_models(self):
        import app.models as m
        assert hasattr(m, "User")

    def test_listing_importable_from_app_models(self):
        import app.models as m
        assert hasattr(m, "Listing")

    def test_conversation_importable_from_app_models(self):
        import app.models as m
        assert hasattr(m, "Conversation")

    def test_message_importable_from_app_models(self):
        import app.models as m
        assert hasattr(m, "Message")

    def test_transaction_importable_from_app_models(self):
        import app.models as m
        assert hasattr(m, "Transaction")

    def test_seller_rating_importable_from_app_models(self):
        import app.models as m
        assert hasattr(m, "SellerRating")


# ===========================================================================
# 2. SHARED BASE — every model must use the same Base from app.core.database
# ===========================================================================

class TestSharedBase:
    def test_user_uses_shared_base(self):
        from app.core.database import Base
        assert issubclass(User, Base)

    def test_listing_uses_shared_base(self):
        from app.core.database import Base
        assert issubclass(Listing, Base)

    def test_conversation_uses_shared_base(self):
        from app.core.database import Base
        assert issubclass(Conversation, Base)

    def test_message_uses_shared_base(self):
        from app.core.database import Base
        assert issubclass(Message, Base)

    def test_transaction_uses_shared_base(self):
        from app.core.database import Base
        assert issubclass(Transaction, Base)

    def test_seller_rating_uses_shared_base(self):
        from app.core.database import Base
        assert issubclass(SellerRating, Base)


# ===========================================================================
# 3. TABLE NAMES AND SCHEMA
# ===========================================================================

class TestTableNames:
    def test_user_tablename_is_users(self):
        assert User.__tablename__ == "users"

    def test_user_schema_is_public(self):
        args = User.__table_args__
        # __table_args__ may be a dict or a tuple ending with a dict
        if isinstance(args, dict):
            schema_dict = args
        else:
            schema_dict = args[-1] if isinstance(args[-1], dict) else {}
        assert schema_dict.get("schema") == "public"

    def test_listing_tablename_is_listings(self):
        assert Listing.__tablename__ == "listings"

    def test_listing_has_no_schema_arg(self):
        # listings lives in the default (public) schema but must NOT declare schema="public"
        # in __table_args__ because it references public.users.id directly via ForeignKey string.
        # The table name used in FK strings must be "listings", not "public.listings".
        assert Listing.__tablename__ == "listings"

    def test_conversation_tablename_is_conversations(self):
        assert Conversation.__tablename__ == "conversations"

    def test_message_tablename_is_messages(self):
        assert Message.__tablename__ == "messages"

    def test_transaction_tablename_is_transactions(self):
        assert Transaction.__tablename__ == "transactions"

    def test_seller_rating_tablename_is_seller_ratings(self):
        assert SellerRating.__tablename__ == "seller_ratings"


# ===========================================================================
# 4. COLUMN PRESENCE — every spec-required column must exist on the model
# ===========================================================================

class TestUserColumns:
    def test_user_has_id(self):
        assert _column(User, "id") is not None

    def test_user_has_full_name(self):
        assert _column(User, "full_name") is not None

    def test_user_has_city(self):
        assert _column(User, "city") is not None

    def test_user_has_avatar_url(self):
        assert _column(User, "avatar_url") is not None

    def test_user_has_is_verified(self):
        assert _column(User, "is_verified") is not None

    def test_user_has_seller_rating(self):
        assert _column(User, "seller_rating") is not None

    def test_user_has_books_sold(self):
        assert _column(User, "books_sold") is not None

    def test_user_has_books_bought(self):
        assert _column(User, "books_bought") is not None

    def test_user_has_created_at(self):
        assert _column(User, "created_at") is not None

    def test_user_has_no_total_sales_column(self):
        # Renamed to books_sold in the no-payments pivot (migration 0006)
        assert _column(User, "total_sales") is None

    def test_user_has_no_razorpay_account_id_column(self):
        # Razorpay linked-account id removed in the no-payments pivot (migration 0006)
        assert _column(User, "razorpay_account_id") is None

    def test_user_has_no_email_column(self):
        assert _column(User, "email") is None

    def test_user_has_no_password_hash_column(self):
        assert _column(User, "password_hash") is None

    def test_user_has_no_phone_column(self):
        assert _column(User, "phone") is None


class TestListingColumns:
    def test_listing_has_id(self):
        assert _column(Listing, "id") is not None

    def test_listing_has_seller_id(self):
        assert _column(Listing, "seller_id") is not None

    def test_listing_has_title(self):
        assert _column(Listing, "title") is not None

    def test_listing_has_description(self):
        assert _column(Listing, "description") is not None

    def test_listing_has_exam_category(self):
        assert _column(Listing, "exam_category") is not None

    def test_listing_has_subject(self):
        assert _column(Listing, "subject") is not None

    def test_listing_has_listing_type(self):
        assert _column(Listing, "listing_type") is not None

    def test_listing_has_condition(self):
        assert _column(Listing, "condition") is not None

    def test_listing_has_asking_price(self):
        assert _column(Listing, "asking_price") is not None

    def test_listing_has_original_price(self):
        assert _column(Listing, "original_price") is not None

    def test_listing_has_city(self):
        assert _column(Listing, "city") is not None

    def test_listing_has_images(self):
        assert _column(Listing, "images") is not None

    def test_listing_has_is_available(self):
        assert _column(Listing, "is_available") is not None

    def test_listing_has_sold_at(self):
        assert _column(Listing, "sold_at") is not None

    def test_listing_has_passkey_hash(self):
        assert _column(Listing, "passkey_hash") is not None

    def test_listing_has_passkey_invalidated(self):
        assert _column(Listing, "passkey_invalidated") is not None

    def test_listing_has_passkey_invalidated_at(self):
        assert _column(Listing, "passkey_invalidated_at") is not None

    def test_listing_has_views(self):
        assert _column(Listing, "views") is not None

    def test_listing_has_created_at(self):
        assert _column(Listing, "created_at") is not None

    def test_listing_has_no_is_featured_column(self):
        assert _column(Listing, "is_featured") is None

    def test_listing_has_no_status_text_column(self):
        # Availability is via is_available boolean, not a text status column
        assert _column(Listing, "status") is None


class TestConversationColumns:
    def test_conversation_has_id(self):
        assert _column(Conversation, "id") is not None

    def test_conversation_has_listing_id(self):
        assert _column(Conversation, "listing_id") is not None

    def test_conversation_has_buyer_id(self):
        assert _column(Conversation, "buyer_id") is not None

    def test_conversation_has_seller_id(self):
        assert _column(Conversation, "seller_id") is not None

    def test_conversation_has_first_message_notified(self):
        assert _column(Conversation, "first_message_notified") is not None

    def test_conversation_has_created_at(self):
        assert _column(Conversation, "created_at") is not None


class TestMessageColumns:
    def test_message_has_id(self):
        assert _column(Message, "id") is not None

    def test_message_has_conversation_id(self):
        assert _column(Message, "conversation_id") is not None

    def test_message_has_sender_id(self):
        assert _column(Message, "sender_id") is not None

    def test_message_has_body(self):
        assert _column(Message, "body") is not None

    def test_message_has_is_read(self):
        assert _column(Message, "is_read") is not None

    def test_message_has_created_at(self):
        assert _column(Message, "created_at") is not None


class TestTransactionColumns:
    def test_transaction_has_id(self):
        assert _column(Transaction, "id") is not None

    def test_transaction_has_listing_id(self):
        assert _column(Transaction, "listing_id") is not None

    def test_transaction_has_buyer_id(self):
        assert _column(Transaction, "buyer_id") is not None

    def test_transaction_has_seller_id(self):
        assert _column(Transaction, "seller_id") is not None

    def test_transaction_has_created_at(self):
        assert _column(Transaction, "created_at") is not None

    # --- No-payments pivot (migration 0006): a transactions row is now purely a
    #     record of a verified, completed in-person exchange. All payment/Razorpay
    #     state was dropped. The platform processes no money. ---

    def test_transaction_has_no_amount_rupees_column(self):
        assert _column(Transaction, "amount_rupees") is None

    def test_transaction_has_no_platform_fee_rupees_column(self):
        assert _column(Transaction, "platform_fee_rupees") is None

    def test_transaction_has_no_seller_payout_rupees_column(self):
        assert _column(Transaction, "seller_payout_rupees") is None

    def test_transaction_has_no_razorpay_payment_link_id_column(self):
        assert _column(Transaction, "razorpay_payment_link_id") is None

    def test_transaction_has_no_razorpay_payment_link_url_column(self):
        assert _column(Transaction, "razorpay_payment_link_url") is None

    def test_transaction_has_no_razorpay_payment_id_column(self):
        assert _column(Transaction, "razorpay_payment_id") is None

    def test_transaction_has_no_status_column(self):
        # No pending/initiated/released/cancelled state — a row IS a completed sale
        assert _column(Transaction, "status") is None

    def test_transaction_has_no_released_at_column(self):
        assert _column(Transaction, "released_at") is None

    def test_transaction_has_no_refunded_at_column(self):
        assert _column(Transaction, "refunded_at") is None


class TestSellerRatingColumns:
    def test_seller_rating_has_id(self):
        assert _column(SellerRating, "id") is not None

    def test_seller_rating_has_transaction_id(self):
        assert _column(SellerRating, "transaction_id") is not None

    def test_seller_rating_has_rated_by(self):
        assert _column(SellerRating, "rated_by") is not None

    def test_seller_rating_has_seller_id(self):
        assert _column(SellerRating, "seller_id") is not None

    def test_seller_rating_has_rating(self):
        assert _column(SellerRating, "rating") is not None

    def test_seller_rating_has_review(self):
        # Optional free-text review added in the no-payments pivot (migration 0006)
        assert _column(SellerRating, "review") is not None

    def test_seller_rating_has_created_at(self):
        assert _column(SellerRating, "created_at") is not None


# ===========================================================================
# 5. NULLABLE / NON-NULLABLE — critical NOT NULL columns
# ===========================================================================

class TestNullability:
    def test_listing_passkey_hash_is_not_nullable(self):
        assert _column(Listing, "passkey_hash").nullable is False

    def test_listing_asking_price_is_not_nullable(self):
        assert _column(Listing, "asking_price").nullable is False

    def test_listing_city_is_not_nullable(self):
        assert _column(Listing, "city").nullable is False

    def test_listing_title_is_not_nullable(self):
        assert _column(Listing, "title").nullable is False

    def test_listing_seller_id_is_not_nullable(self):
        assert _column(Listing, "seller_id").nullable is False

    def test_listing_exam_category_is_not_nullable(self):
        assert _column(Listing, "exam_category").nullable is False

    def test_listing_listing_type_is_not_nullable(self):
        assert _column(Listing, "listing_type").nullable is False

    def test_listing_condition_is_not_nullable(self):
        assert _column(Listing, "condition").nullable is False

    def test_listing_description_is_nullable(self):
        assert _column(Listing, "description").nullable is True

    def test_listing_subject_is_nullable(self):
        assert _column(Listing, "subject").nullable is True

    def test_listing_original_price_is_nullable(self):
        assert _column(Listing, "original_price").nullable is True

    def test_listing_sold_at_is_nullable(self):
        assert _column(Listing, "sold_at").nullable is True

    def test_conversation_buyer_id_is_not_nullable(self):
        assert _column(Conversation, "buyer_id").nullable is False

    def test_conversation_seller_id_is_not_nullable(self):
        assert _column(Conversation, "seller_id").nullable is False

    def test_conversation_listing_id_is_nullable(self):
        # SET NULL on delete means this can become NULL
        assert _column(Conversation, "listing_id").nullable is True

    def test_message_body_is_not_nullable(self):
        assert _column(Message, "body").nullable is False

    def test_message_conversation_id_is_not_nullable(self):
        assert _column(Message, "conversation_id").nullable is False

    def test_message_sender_id_is_not_nullable(self):
        assert _column(Message, "sender_id").nullable is False

    def test_transaction_buyer_id_is_not_nullable(self):
        assert _column(Transaction, "buyer_id").nullable is False

    def test_transaction_seller_id_is_not_nullable(self):
        assert _column(Transaction, "seller_id").nullable is False

    def test_transaction_listing_id_is_nullable(self):
        # SET NULL on delete means this can become NULL
        assert _column(Transaction, "listing_id").nullable is True

    def test_user_full_name_is_not_nullable(self):
        assert _column(User, "full_name").nullable is False

    def test_user_city_is_nullable(self):
        assert _column(User, "city").nullable is True

    def test_user_seller_rating_is_nullable(self):
        assert _column(User, "seller_rating").nullable is True


# ===========================================================================
# 6. SERVER DEFAULTS
# ===========================================================================

class TestServerDefaults:
    def test_listing_is_available_server_default_is_true(self):
        col = _column(Listing, "is_available")
        assert col.server_default is not None
        assert "true" in str(col.server_default.arg).lower()

    def test_listing_passkey_invalidated_server_default_is_false(self):
        col = _column(Listing, "passkey_invalidated")
        assert col.server_default is not None
        assert "false" in str(col.server_default.arg).lower()

    def test_user_is_verified_server_default_is_false(self):
        col = _column(User, "is_verified")
        assert col.server_default is not None
        assert "false" in str(col.server_default.arg).lower()

    def test_user_books_sold_server_default_is_zero(self):
        col = _column(User, "books_sold")
        assert col.server_default is not None
        assert str(col.server_default.arg) == "0"

    def test_user_books_bought_server_default_is_zero(self):
        col = _column(User, "books_bought")
        assert col.server_default is not None
        assert str(col.server_default.arg) == "0"

    def test_conversation_first_message_notified_server_default_is_false(self):
        col = _column(Conversation, "first_message_notified")
        assert col.server_default is not None
        assert "false" in str(col.server_default.arg).lower()

    def test_message_is_read_server_default_is_false(self):
        col = _column(Message, "is_read")
        assert col.server_default is not None
        assert "false" in str(col.server_default.arg).lower()


# ===========================================================================
# 7. CHECK CONSTRAINT NAMES
# ===========================================================================

class TestCheckConstraintNames:
    def test_listing_has_ck_listing_type(self):
        assert "ck_listing_type" in _check_constraint_names(Listing)

    def test_listing_has_ck_condition(self):
        assert "ck_condition" in _check_constraint_names(Listing)

    def test_listing_has_ck_asking_price_positive(self):
        assert "ck_asking_price_positive" in _check_constraint_names(Listing)

    def test_listing_has_no_available_sold_listing(self):
        assert "no_available_sold_listing" in _check_constraint_names(Listing)

    def test_listing_has_sold_xor_deleted(self):
        assert "sold_xor_deleted" in _check_constraint_names(Listing)

    def test_listing_has_ck_original_price_positive(self):
        assert "ck_original_price_positive" in _check_constraint_names(Listing)

    def test_transaction_has_no_payment_check_constraints(self):
        # Payment-era checks dropped in the no-payments pivot (migration 0006)
        names = _check_constraint_names(Transaction)
        assert "ck_transaction_status" not in names
        assert "ck_amount_positive" not in names
        assert "ck_payout_nonnegative" not in names

    def test_user_has_ck_seller_rating_range(self):
        assert "ck_seller_rating_range" in _check_constraint_names(User)

    def test_seller_rating_has_ck_rating_range(self):
        assert "ck_rating_range" in _check_constraint_names(SellerRating)


# ===========================================================================
# 8. UNIQUE CONSTRAINT NAMES
# ===========================================================================

class TestUniqueConstraintNames:
    def test_conversation_has_uq_conversation_listing_buyer(self):
        assert "uq_conversation_listing_buyer" in _unique_constraint_names(Conversation)

    def test_seller_rating_has_uq_rating_transaction_rater(self):
        assert "uq_rating_transaction_rater" in _unique_constraint_names(SellerRating)

    def test_uq_conversation_listing_buyer_covers_correct_columns(self):
        """The unique constraint must cover (listing_id, buyer_id) — not just one column."""
        args = getattr(Conversation, "__table_args__", ())
        for item in args:
            if isinstance(item, UniqueConstraint) and item.name == "uq_conversation_listing_buyer":
                col_names = {c.key for c in item.columns}
                assert "listing_id" in col_names
                assert "buyer_id" in col_names
                return
        raise AssertionError("uq_conversation_listing_buyer constraint not found")

    def test_uq_rating_transaction_rater_covers_correct_columns(self):
        """The unique constraint must cover (transaction_id, rated_by)."""
        args = getattr(SellerRating, "__table_args__", ())
        for item in args:
            if isinstance(item, UniqueConstraint) and item.name == "uq_rating_transaction_rater":
                col_names = {c.key for c in item.columns}
                assert "transaction_id" in col_names
                assert "rated_by" in col_names
                return
        raise AssertionError("uq_rating_transaction_rater constraint not found")


# ===========================================================================
# 9. FOREIGN KEY TARGETS
# ===========================================================================

class TestForeignKeyTargets:
    def test_listing_seller_id_fk_targets_public_users_id(self):
        targets = _fk_targets(Listing, "seller_id")
        assert "public.users.id" in targets

    def test_conversation_listing_id_fk_targets_listings_id(self):
        targets = _fk_targets(Conversation, "listing_id")
        assert "listings.id" in targets

    def test_conversation_listing_id_fk_has_set_null_on_delete(self):
        col = _column(Conversation, "listing_id")
        for fk in col.foreign_keys:
            if "listings.id" in fk.target_fullname:
                assert fk.ondelete.upper() == "SET NULL"
                return
        raise AssertionError("FK from conversations.listing_id to listings.id not found")

    def test_transaction_listing_id_fk_targets_listings_id(self):
        targets = _fk_targets(Transaction, "listing_id")
        assert "listings.id" in targets

    def test_transaction_listing_id_fk_has_set_null_on_delete(self):
        col = _column(Transaction, "listing_id")
        for fk in col.foreign_keys:
            if "listings.id" in fk.target_fullname:
                assert fk.ondelete.upper() == "SET NULL"
                return
        raise AssertionError("FK from transactions.listing_id to listings.id not found")

    def test_conversation_buyer_id_fk_targets_public_users_id(self):
        targets = _fk_targets(Conversation, "buyer_id")
        assert "public.users.id" in targets

    def test_message_conversation_id_fk_targets_conversations_id(self):
        targets = _fk_targets(Message, "conversation_id")
        assert "conversations.id" in targets

    def test_message_sender_id_fk_targets_public_users_id(self):
        targets = _fk_targets(Message, "sender_id")
        assert "public.users.id" in targets

    def test_transaction_buyer_id_fk_targets_public_users_id(self):
        targets = _fk_targets(Transaction, "buyer_id")
        assert "public.users.id" in targets

    def test_seller_rating_transaction_id_fk_targets_transactions_id(self):
        targets = _fk_targets(SellerRating, "transaction_id")
        assert "transactions.id" in targets

    def test_seller_rating_rated_by_fk_targets_public_users_id(self):
        targets = _fk_targets(SellerRating, "rated_by")
        assert "public.users.id" in targets

    def test_seller_rating_seller_id_fk_targets_public_users_id(self):
        targets = _fk_targets(SellerRating, "seller_id")
        assert "public.users.id" in targets


# ===========================================================================
# 10. PRICE INTEGRITY — listing prices must be whole-rupee Integer type
# ===========================================================================

class TestPriceColumnTypes:
    def test_listing_asking_price_is_integer_type(self):
        col = _column(Listing, "asking_price")
        assert isinstance(col.type, Integer), (
            f"asking_price must be Integer (whole rupees), got {type(col.type)}"
        )

    def test_listing_original_price_is_integer_type_when_present(self):
        col = _column(Listing, "original_price")
        assert isinstance(col.type, Integer), (
            f"original_price must be Integer (whole rupees), got {type(col.type)}"
        )

    def test_listing_asking_price_is_not_float(self):
        from sqlalchemy import Float
        col = _column(Listing, "asking_price")
        assert not isinstance(col.type, Float)

    def test_listing_asking_price_is_not_numeric(self):
        from sqlalchemy import Numeric
        col = _column(Listing, "asking_price")
        assert not isinstance(col.type, Numeric)


# ===========================================================================
# 11. MIGRATION STRUCTURE
# ===========================================================================

class TestMigrationStructure:
    """
    Introspect the migration file as a Python module.
    No DB connection required — we only check module-level attributes and
    that the callable signatures exist.
    """

    def _load_migration(self):
        import importlib.util, pathlib
        migration_path = pathlib.Path(__file__).parents[1] / "alembic" / "versions" / "0001_initial_schema.py"
        spec = importlib.util.spec_from_file_location("migration_0001", migration_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_migration_revision_is_0001(self):
        mod = self._load_migration()
        assert mod.revision == "0001"

    def test_migration_down_revision_is_none(self):
        mod = self._load_migration()
        assert mod.down_revision is None

    def test_migration_has_upgrade_function(self):
        mod = self._load_migration()
        assert callable(getattr(mod, "upgrade", None))

    def test_migration_has_downgrade_function(self):
        mod = self._load_migration()
        assert callable(getattr(mod, "downgrade", None))

    def _downgrade_drop_table_pos(self, table_name: str) -> int:
        """Return position of drop_table("<table_name>") in the downgrade block."""
        import pathlib
        migration_path = pathlib.Path(__file__).parents[1] / "alembic" / "versions" / "0001_initial_schema.py"
        source = migration_path.read_text()
        downgrade_source = source[source.index("def downgrade()"):]
        return downgrade_source.find(f'drop_table("{table_name}"')

    def test_migration_downgrade_drops_seller_ratings_before_transactions(self):
        """Verify FK-safe reverse drop order: seller_ratings before transactions."""
        seller_pos = self._downgrade_drop_table_pos("seller_ratings")
        transactions_pos = self._downgrade_drop_table_pos("transactions")
        assert seller_pos != -1, "seller_ratings not dropped in downgrade"
        assert transactions_pos != -1, "transactions not dropped in downgrade"
        assert seller_pos < transactions_pos, (
            "seller_ratings must be dropped before transactions in downgrade()"
        )

    def test_migration_downgrade_drops_transactions_before_messages(self):
        assert self._downgrade_drop_table_pos("transactions") < self._downgrade_drop_table_pos("messages")

    def test_migration_downgrade_drops_messages_before_conversations(self):
        assert self._downgrade_drop_table_pos("messages") < self._downgrade_drop_table_pos("conversations")

    def test_migration_downgrade_drops_conversations_before_listings(self):
        assert self._downgrade_drop_table_pos("conversations") < self._downgrade_drop_table_pos("listings")

    def test_migration_downgrade_drops_listings_before_users(self):
        assert self._downgrade_drop_table_pos("listings") < self._downgrade_drop_table_pos("users")


# ===========================================================================
# 12. ALEMBIC PARTIAL INDEX — one_active_transaction_per_buyer_listing
# ===========================================================================

class TestPartialIndex:
    def _migration_source(self):
        import pathlib
        migration_path = pathlib.Path(__file__).parents[1] / "alembic" / "versions" / "0001_initial_schema.py"
        return migration_path.read_text()

    def test_partial_index_is_created_in_migration(self):
        source = self._migration_source()
        assert "one_active_transaction_per_buyer_listing" in source

    def test_partial_index_is_unique(self):
        source = self._migration_source()
        # The create_index call for the partial index must have unique=True
        idx_start = source.find("one_active_transaction_per_buyer_listing")
        # Grab a generous window around it to check for unique=True
        window = source[idx_start: idx_start + 300]
        assert "unique=True" in window

    def test_partial_index_has_postgresql_where_clause(self):
        source = self._migration_source()
        idx_start = source.find("one_active_transaction_per_buyer_listing")
        window = source[idx_start: idx_start + 300]
        assert "postgresql_where" in window

    def test_partial_index_where_clause_filters_on_initiated_status(self):
        source = self._migration_source()
        idx_start = source.find("one_active_transaction_per_buyer_listing")
        window = source[idx_start: idx_start + 300]
        assert "initiated" in window

    def test_partial_index_covers_listing_id_and_buyer_id(self):
        source = self._migration_source()
        idx_start = source.find("one_active_transaction_per_buyer_listing")
        window = source[idx_start: idx_start + 300]
        assert "listing_id" in window
        assert "buyer_id" in window


# ===========================================================================
# 13. CHECK CONSTRAINT CONTENT — validate constraint expressions encode the
#     correct business rules (not just the name).
# ===========================================================================

class TestCheckConstraintContent:
    def _get_check(self, model, name):
        args = getattr(model, "__table_args__", ())
        for item in args:
            if isinstance(item, CheckConstraint) and item.name == name:
                return str(item.sqltext)
        return None

    def test_ck_listing_type_includes_all_four_types(self):
        expr = self._get_check(Listing, "ck_listing_type")
        assert expr is not None
        for t in ("BOOK", "NOTES", "MODULE", "BUNDLE"):
            assert t in expr

    def test_ck_condition_includes_a_b_c(self):
        expr = self._get_check(Listing, "ck_condition")
        assert expr is not None
        for c in ("A", "B", "C"):
            assert c in expr

    def test_ck_asking_price_positive_uses_greater_than_zero(self):
        expr = self._get_check(Listing, "ck_asking_price_positive")
        assert expr is not None
        assert "asking_price" in expr
        assert "0" in expr

    def test_no_available_sold_listing_references_is_available_and_sold_at(self):
        expr = self._get_check(Listing, "no_available_sold_listing")
        assert expr is not None
        assert "is_available" in expr
        assert "sold_at" in expr

    def test_sold_xor_deleted_references_sold_at_and_deleted_at(self):
        # A listing can be sold OR soft-deleted, never both (migration 0006-era model)
        expr = self._get_check(Listing, "sold_xor_deleted")
        assert expr is not None
        assert "sold_at" in expr
        assert "deleted_at" in expr

    def test_ck_rating_range_is_between_1_and_5(self):
        expr = self._get_check(SellerRating, "ck_rating_range")
        assert expr is not None
        assert "1" in expr
        assert "5" in expr


# ===========================================================================
# 14. PRIMARY KEY TYPE — all PKs must be UUID
# ===========================================================================

class TestPrimaryKeyTypes:
    def _pk_col(self, model):
        for col in model.__table__.columns:
            if col.primary_key:
                return col
        return None

    def test_user_pk_is_uuid(self):
        col = self._pk_col(User)
        assert isinstance(col.type, UUID)

    def test_listing_pk_is_uuid(self):
        col = self._pk_col(Listing)
        assert isinstance(col.type, UUID)

    def test_conversation_pk_is_uuid(self):
        col = self._pk_col(Conversation)
        assert isinstance(col.type, UUID)

    def test_message_pk_is_uuid(self):
        col = self._pk_col(Message)
        assert isinstance(col.type, UUID)

    def test_transaction_pk_is_uuid(self):
        col = self._pk_col(Transaction)
        assert isinstance(col.type, UUID)

    def test_seller_rating_pk_is_uuid(self):
        col = self._pk_col(SellerRating)
        assert isinstance(col.type, UUID)


# ===========================================================================
# 15. TRANSACTION-PER-LISTING UNIQUENESS — a listing sells exactly once, so at
#     most one verified transaction may reference a given listing. After the
#     no-payments pivot (migration 0006) this is enforced by a partial unique
#     index `uq_transaction_per_listing` (WHERE listing_id IS NOT NULL),
#     declared on the model via Index(...). The old per-column Razorpay unique
#     constraints were removed along with those columns.
# ===========================================================================

class TestTransactionUniqueness:
    def _indexes(self):
        from sqlalchemy import Index
        args = getattr(Transaction, "__table_args__", ())
        if isinstance(args, dict):
            return []
        return [item for item in args if isinstance(item, Index)]

    def _uq_per_listing(self):
        for idx in self._indexes():
            if idx.name == "uq_transaction_per_listing":
                return idx
        return None

    def test_uq_transaction_per_listing_index_exists(self):
        assert self._uq_per_listing() is not None

    def test_uq_transaction_per_listing_is_unique(self):
        idx = self._uq_per_listing()
        assert idx is not None
        assert idx.unique is True

    def test_uq_transaction_per_listing_covers_listing_id(self):
        idx = self._uq_per_listing()
        assert idx is not None
        col_names = {c.key for c in idx.columns}
        assert "listing_id" in col_names

    def test_uq_transaction_per_listing_is_partial_on_non_null_listing(self):
        # NULL listing_id (set when a sold listing is deleted) must not be deduped.
        idx = self._uq_per_listing()
        assert idx is not None
        where = str(idx.dialect_options["postgresql"].get("where", ""))
        assert "listing_id" in where

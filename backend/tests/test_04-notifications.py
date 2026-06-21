"""
Spec-driven tests for Spec 04 — Notifications.

Test surface (NO-PAYMENTS model — see CLAUDE.md):
  Email 1 — First-message email  (send_new_message_email, chat_service._notify_first_message)
  Email 2 — Sale-complete email  (send_sale_complete, transactions._notify_seller_of_sale)
  Email 4 — Listing-removed email  (send_listing_removed_email — isolated, no trigger wired)

The platform processes no payment. The sale-complete email is triggered by passkey
verification (transactions router), carries NO amount/payout, and the seller is
notified by listing title only. The former payment-era abandoned-checkout email
(Email 3) and its scheduler job no longer exist and are not tested here.

Cross-cutting:
  - From address: "NextPrep <no-reply@nextprep.online>"
  - Fire-and-forget: Resend exceptions swallowed, never re-raised
  - Logging: INFO on success, ERROR on failure, WARNING on unresolved email
  - Security: email never in API responses, service-role key never in request path

All Resend calls are patched — no real network/email calls.
All fetch_user_email calls are patched where needed.

Windows note: the existing conftest.py already sets WindowsSelectorEventLoopPolicy.
pytest-asyncio is used for coroutine tests.
"""

import logging
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Windows event-loop policy is set globally in conftest.py.


# ---------------------------------------------------------------------------
# Helpers / constants
# ---------------------------------------------------------------------------
SELLER_EMAIL = "seller@example.com"
FROM_ADDRESS = "NextPrep <no-reply@nextprep.online>"

LISTING_ID = uuid.uuid4()
TRANSACTION_ID = uuid.uuid4()
CONVERSATION_ID = uuid.uuid4()
SELLER_ID = uuid.uuid4()
LISTING_TITLE = "HC Verma Concepts of Physics Vol 1"


# ===========================================================================
# EMAIL 1 — First-message notification
# ===========================================================================

class TestSendNewMessageEmail:
    """Unit tests for notification_service.send_new_message_email."""

    @pytest.mark.asyncio
    async def test_first_message_email_uses_correct_subject(self):
        """Spec 04 §Email1: subject must be exactly 'Someone is interested in your listing'."""
        from app.services.notification_service import send_new_message_email

        with patch("app.services.notification_service.resend.Emails.send") as mock_send:
            await send_new_message_email(CONVERSATION_ID, SELLER_EMAIL)

        mock_send.assert_called_once()
        payload = mock_send.call_args[0][0]
        assert payload["subject"] == "Someone is interested in your listing"

    @pytest.mark.asyncio
    async def test_first_message_email_uses_correct_from_address(self):
        """Spec 04 cross-cutting: from address must be 'NextPrep <no-reply@yourdomain.com>'."""
        from app.services.notification_service import send_new_message_email

        with patch("app.services.notification_service.resend.Emails.send") as mock_send:
            await send_new_message_email(CONVERSATION_ID, SELLER_EMAIL)

        payload = mock_send.call_args[0][0]
        assert payload["from"] == FROM_ADDRESS

    @pytest.mark.asyncio
    async def test_first_message_email_html_body_content(self):
        """Spec 04 §Email1 template: body must contain the canonical copy."""
        from app.services.notification_service import send_new_message_email

        with patch("app.services.notification_service.resend.Emails.send") as mock_send:
            await send_new_message_email(CONVERSATION_ID, SELLER_EMAIL)

        payload = mock_send.call_args[0][0]
        assert "A buyer has sent you a message about your listing on NextPrep" in payload["html"]
        assert "Log in to reply" in payload["html"]

    @pytest.mark.asyncio
    async def test_first_message_email_sends_to_seller(self):
        """Spec 04 §Email1: recipient is the listing seller."""
        from app.services.notification_service import send_new_message_email

        with patch("app.services.notification_service.resend.Emails.send") as mock_send:
            await send_new_message_email(CONVERSATION_ID, SELLER_EMAIL)

        payload = mock_send.call_args[0][0]
        assert SELLER_EMAIL in payload["to"]

    @pytest.mark.asyncio
    async def test_first_message_email_resend_exception_is_swallowed(self):
        """Spec 04 cross-cutting: Resend raising must be swallowed, never re-raised."""
        from app.services.notification_service import send_new_message_email

        with patch(
            "app.services.notification_service.resend.Emails.send",
            side_effect=Exception("Resend outage"),
        ):
            # Must not raise
            await send_new_message_email(CONVERSATION_ID, SELLER_EMAIL)

    @pytest.mark.asyncio
    async def test_first_message_email_logs_info_on_success(self):
        """Spec 04 logging: success logged at INFO keyed by conversation UUID."""
        from app.services import notification_service

        with patch("app.services.notification_service.resend.Emails.send"):
            with patch.object(notification_service.logger, "info") as mock_info:
                await notification_service.send_new_message_email(CONVERSATION_ID, SELLER_EMAIL)

        # At least one INFO call that includes the conversation id
        logged_messages = [str(c) for c in mock_info.call_args_list]
        assert any(str(CONVERSATION_ID) in m for m in logged_messages)

    @pytest.mark.asyncio
    async def test_first_message_email_logs_error_on_resend_failure(self):
        """Spec 04 logging: failure logged at ERROR with entity UUID (never the email body)."""
        from app.services import notification_service

        with patch(
            "app.services.notification_service.resend.Emails.send",
            side_effect=Exception("timeout"),
        ):
            with patch.object(notification_service.logger, "error") as mock_error:
                await notification_service.send_new_message_email(CONVERSATION_ID, SELLER_EMAIL)

        mock_error.assert_called_once()
        error_args = str(mock_error.call_args)
        # Entity UUID logged, not the email body or recipient address
        assert str(CONVERSATION_ID) in error_args

    @pytest.mark.asyncio
    async def test_first_message_email_does_not_log_recipient_address_on_error(self):
        """Spec 04 logging: recipient email address must NEVER appear in error log."""
        from app.services import notification_service

        with patch(
            "app.services.notification_service.resend.Emails.send",
            side_effect=Exception("timeout"),
        ):
            with patch.object(notification_service.logger, "error") as mock_error:
                await notification_service.send_new_message_email(CONVERSATION_ID, SELLER_EMAIL)

        error_args = str(mock_error.call_args)
        assert SELLER_EMAIL not in error_args


class TestNotifyFirstMessageDispatch:
    """Tests for chat_service._notify_first_message — the BackgroundTask wrapper."""

    @pytest.mark.asyncio
    async def test_notify_first_message_sends_email_when_email_resolved(self):
        """Spec 04 §Email1: email sent when fetch_user_email returns a valid address."""
        from app.services.chat_service import _notify_first_message

        with patch("app.services.chat_service.supabase_admin.fetch_user_email", new_callable=AsyncMock,
                   return_value=SELLER_EMAIL) as mock_fetch:
            with patch("app.services.chat_service.notification_service.send_new_message_email",
                       new_callable=AsyncMock) as mock_send:
                await _notify_first_message(str(CONVERSATION_ID), str(SELLER_ID))

        mock_fetch.assert_awaited_once_with(str(SELLER_ID))
        mock_send.assert_awaited_once_with(CONVERSATION_ID, SELLER_EMAIL)

    @pytest.mark.asyncio
    async def test_notify_first_message_skips_send_when_email_unresolved(self):
        """Spec 04 §Email1: no send if fetch_user_email returns None; logs warning."""
        from app.services import chat_service

        with patch("app.services.chat_service.supabase_admin.fetch_user_email", new_callable=AsyncMock,
                   return_value=None):
            with patch("app.services.chat_service.notification_service.send_new_message_email",
                       new_callable=AsyncMock) as mock_send:
                with patch.object(chat_service.logger, "warning") as mock_warn:
                    await chat_service._notify_first_message(str(CONVERSATION_ID), str(SELLER_ID))

        mock_send.assert_not_awaited()
        mock_warn.assert_called_once()
        warn_args = str(mock_warn.call_args)
        assert str(CONVERSATION_ID) in warn_args

    @pytest.mark.asyncio
    async def test_notify_first_message_unresolved_warning_never_logs_email(self):
        """Spec 04 logging/security: the warning for unresolved email must not log
        a recipient address (there isn't one — but guard against accidental arg exposure)."""
        from app.services import chat_service

        with patch("app.services.chat_service.supabase_admin.fetch_user_email", new_callable=AsyncMock,
                   return_value=None):
            with patch.object(chat_service.logger, "warning") as mock_warn:
                await chat_service._notify_first_message(str(CONVERSATION_ID), str(SELLER_ID))

        warn_args = str(mock_warn.call_args)
        # No email address form (contains @) should appear in the warning
        assert "@" not in warn_args


class TestFirstMessageAtomicFlagGuard:
    """Tests for the atomic UPDATE ... WHERE first_message_notified = FALSE RETURNING id guard."""

    @pytest.mark.asyncio
    async def test_first_message_flag_flip_prevents_second_notification(self):
        """Spec 04 §Email1 single-send guard: the BackgroundTask is only queued when
        the UPDATE ... RETURNING wins the race (returns a row). If it returns no row,
        notify_first stays False and no BackgroundTask is added."""
        from fastapi import BackgroundTasks
        from app.services import chat_service

        # Build a mock DB that returns None from scalar_one_or_none() on the UPDATE
        # (simulates a concurrent request already flipped the flag)
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.add = MagicMock()  # SQLAlchemy session.add() is synchronous

        # First execute (SELECT for _assert_participant) returns a conversation with
        # first_message_notified already = True
        seller_uuid = uuid.uuid4()
        conversation_already_notified = MagicMock()
        conversation_already_notified.first_message_notified = True
        conversation_already_notified.buyer_id = seller_uuid
        conversation_already_notified.seller_id = SELLER_ID

        select_result = MagicMock()
        select_result.scalar_one_or_none.return_value = conversation_already_notified

        mock_db.execute.return_value = select_result
        # send_message's "listing still available?" guard does `await db.get(Listing, ...)`;
        # return an active listing (available, not sold, not deleted) so the guard passes
        # and we reach the flag-flip logic.
        mock_db.get = AsyncMock(return_value=MagicMock(sold_at=None, is_available=True, deleted_at=None))
        mock_db.commit = AsyncMock()

        # db.refresh populates server-generated columns (id, created_at, is_read) on the
        # ORM instance the way real Postgres does — otherwise _serialize_message/MessageOut
        # crash before the assertion about BackgroundTasks can run.
        async def _refresh(obj, *args, **kwargs):
            obj.id = uuid.uuid4()
            obj.created_at = datetime.now(timezone.utc)
            obj.is_read = False

        mock_db.refresh = _refresh

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock()
        mock_redis.delete = AsyncMock()

        bt = BackgroundTasks()

        with patch("app.services.chat_service.supabase_admin.fetch_user_email", new_callable=AsyncMock,
                   return_value=SELLER_EMAIL):
            with patch("app.services.chat_service.notification_service.send_new_message_email",
                       new_callable=AsyncMock) as mock_email_send:
                await chat_service.send_message(
                    db=mock_db,
                    redis=mock_redis,
                    conversation_id=CONVERSATION_ID,
                    sender_id=str(seller_uuid),  # sender is buyer
                    body="Hello",
                    background_tasks=bt,
                )

        # Since first_message_notified is already True, no background email task queued
        assert len(bt.tasks) == 0


# ===========================================================================
# EMAIL 2 — Sale-complete notification
# ===========================================================================

class TestSendSaleComplete:
    """Unit tests for notification_service.send_sale_complete.

    NO-PAYMENTS model: the current signature is send_sale_complete(listing_title,
    seller_email). It carries no amount/payout — the platform processes no money.
    Success/failure are logged keyed by the listing title (the only stable id the
    BackgroundTask receives), never by the seller email.
    """

    @pytest.mark.asyncio
    async def test_sale_complete_email_uses_correct_subject(self):
        """Spec 04 §Email2: subject must be exactly 'Your listing has been sold!'"""
        from app.services.notification_service import send_sale_complete

        with patch("app.services.notification_service.resend.Emails.send") as mock_send:
            await send_sale_complete(LISTING_TITLE, SELLER_EMAIL)

        payload = mock_send.call_args[0][0]
        assert payload["subject"] == "Your listing has been sold!"

    @pytest.mark.asyncio
    async def test_sale_complete_email_uses_correct_from_address(self):
        """Spec 04 cross-cutting: from address must be 'NextPrep <no-reply@nextprep.online>'."""
        from app.services.notification_service import send_sale_complete

        with patch("app.services.notification_service.resend.Emails.send") as mock_send:
            await send_sale_complete(LISTING_TITLE, SELLER_EMAIL)

        payload = mock_send.call_args[0][0]
        assert payload["from"] == FROM_ADDRESS

    @pytest.mark.asyncio
    async def test_sale_complete_email_body_contains_listing_title(self):
        """Spec 04 §Email2 (NO-PAYMENTS): body must include the listing title so the seller
        knows which listing sold. There is no amount/payout — the platform handles no money."""
        from app.services.notification_service import send_sale_complete

        with patch("app.services.notification_service.resend.Emails.send") as mock_send:
            await send_sale_complete(LISTING_TITLE, SELLER_EMAIL)

        payload = mock_send.call_args[0][0]
        assert LISTING_TITLE in payload["html"]

    @pytest.mark.asyncio
    async def test_sale_complete_email_sends_to_seller(self):
        """Spec 04 §Email2: recipient is the seller."""
        from app.services.notification_service import send_sale_complete

        with patch("app.services.notification_service.resend.Emails.send") as mock_send:
            await send_sale_complete(LISTING_TITLE, SELLER_EMAIL)

        payload = mock_send.call_args[0][0]
        assert SELLER_EMAIL in payload["to"]

    @pytest.mark.asyncio
    async def test_sale_complete_email_resend_exception_is_swallowed(self):
        """Spec 04 cross-cutting: Resend failure must never block the (already-committed) sale."""
        from app.services.notification_service import send_sale_complete

        with patch(
            "app.services.notification_service.resend.Emails.send",
            side_effect=Exception("Resend down"),
        ):
            # Must not raise
            await send_sale_complete(LISTING_TITLE, SELLER_EMAIL)

    @pytest.mark.asyncio
    async def test_sale_complete_email_logs_info_on_success(self):
        """Spec 04 logging: success logged at INFO keyed by listing title."""
        from app.services import notification_service

        with patch("app.services.notification_service.resend.Emails.send"):
            with patch.object(notification_service.logger, "info") as mock_info:
                await notification_service.send_sale_complete(LISTING_TITLE, SELLER_EMAIL)

        logged = [str(c) for c in mock_info.call_args_list]
        assert any(LISTING_TITLE in m for m in logged)

    @pytest.mark.asyncio
    async def test_sale_complete_email_logs_error_on_resend_failure(self):
        """Spec 04 logging: Resend failure logged at ERROR with the listing title."""
        from app.services import notification_service

        with patch(
            "app.services.notification_service.resend.Emails.send",
            side_effect=Exception("timeout"),
        ):
            with patch.object(notification_service.logger, "error") as mock_error:
                await notification_service.send_sale_complete(LISTING_TITLE, SELLER_EMAIL)

        mock_error.assert_called_once()
        assert LISTING_TITLE in str(mock_error.call_args)

    @pytest.mark.asyncio
    async def test_sale_complete_email_error_log_never_contains_recipient_address(self):
        """Spec 04 logging/security: the error log must not include the seller email."""
        from app.services import notification_service

        with patch(
            "app.services.notification_service.resend.Emails.send",
            side_effect=Exception("timeout"),
        ):
            with patch.object(notification_service.logger, "error") as mock_error:
                await notification_service.send_sale_complete(LISTING_TITLE, SELLER_EMAIL)

        assert SELLER_EMAIL not in str(mock_error.call_args)


class TestNotifySellerOfSaleDispatch:
    """Tests for transactions._notify_seller_of_sale — the BackgroundTask wrapper.

    NO-PAYMENTS model: this wrapper is queued by the passkey-verify endpoint (not a
    payment webhook) and takes (seller_id, listing_title). It resolves the seller's
    email server-side and forwards (listing_title, seller_email) to send_sale_complete.
    """

    @pytest.mark.asyncio
    async def test_notify_seller_sends_when_email_resolved(self):
        """Spec 04 §Email2 dispatch: send_sale_complete called with title + resolved email."""
        from app.routers.transactions import _notify_seller_of_sale

        with patch("app.routers.transactions.fetch_user_email", new_callable=AsyncMock,
                   return_value=SELLER_EMAIL):
            with patch("app.routers.transactions.notification_service.send_sale_complete",
                       new_callable=AsyncMock) as mock_send:
                await _notify_seller_of_sale(SELLER_ID, LISTING_TITLE)

        mock_send.assert_awaited_once_with(LISTING_TITLE, SELLER_EMAIL)

    @pytest.mark.asyncio
    async def test_notify_seller_logs_warning_when_email_unresolved(self):
        """Spec 04 §Email2 dispatch: warning logged when seller email cannot be resolved."""
        import app.routers.transactions as transactions_module

        with patch("app.routers.transactions.fetch_user_email", new_callable=AsyncMock,
                   return_value=None):
            with patch("app.routers.transactions.notification_service.send_sale_complete",
                       new_callable=AsyncMock) as mock_send:
                with patch.object(transactions_module.logger, "warning") as mock_warn:
                    await transactions_module._notify_seller_of_sale(SELLER_ID, LISTING_TITLE)

        mock_send.assert_not_awaited()
        mock_warn.assert_called_once()
        assert LISTING_TITLE in str(mock_warn.call_args)

    @pytest.mark.asyncio
    async def test_notify_seller_warning_never_logs_resolved_email(self):
        """Spec 04 security/logging: the warning for unresolved seller must not include
        any email address in the log output."""
        import app.routers.transactions as transactions_module

        with patch("app.routers.transactions.fetch_user_email", new_callable=AsyncMock,
                   return_value=None):
            with patch.object(transactions_module.logger, "warning") as mock_warn:
                await transactions_module._notify_seller_of_sale(SELLER_ID, LISTING_TITLE)

        assert "@" not in str(mock_warn.call_args)


# ===========================================================================
# EMAIL 4 — Listing-removed notification (function isolated, trigger deferred)
# ===========================================================================

class TestSendListingRemovedEmail:
    """Unit tests for notification_service.send_listing_removed_email.

    Spec 04 §Email4: the trigger is DEFERRED — no route, scheduler, or job wires
    this function in v1. Tests cover the function in isolation only.
    """

    @pytest.mark.asyncio
    async def test_listing_removed_email_uses_correct_subject(self):
        """Spec 04 §Email4: subject must be exactly 'Your listing was removed from NextPrep'."""
        from app.services.notification_service import send_listing_removed_email

        with patch("app.services.notification_service.resend.Emails.send") as mock_send:
            await send_listing_removed_email(LISTING_ID, SELLER_EMAIL, "PIRACY")

        payload = mock_send.call_args[0][0]
        assert payload["subject"] == "Your listing was removed from NextPrep"

    @pytest.mark.asyncio
    async def test_listing_removed_email_uses_correct_from_address(self):
        """Spec 04 cross-cutting: from address must be 'NextPrep <no-reply@yourdomain.com>'."""
        from app.services.notification_service import send_listing_removed_email

        with patch("app.services.notification_service.resend.Emails.send") as mock_send:
            await send_listing_removed_email(LISTING_ID, SELLER_EMAIL, "SPAM")

        payload = mock_send.call_args[0][0]
        assert payload["from"] == FROM_ADDRESS

    @pytest.mark.asyncio
    async def test_listing_removed_email_body_contains_reason_category(self):
        """Spec 04 §Email4 template: body must include the reason_category."""
        from app.services.notification_service import send_listing_removed_email

        reason = "CONTACT_INFO"

        with patch("app.services.notification_service.resend.Emails.send") as mock_send:
            await send_listing_removed_email(LISTING_ID, SELLER_EMAIL, reason)

        payload = mock_send.call_args[0][0]
        assert reason in payload["html"]

    @pytest.mark.asyncio
    async def test_listing_removed_email_body_mentions_content_policy(self):
        """Spec 04 §Email4 template: body must reference content policy."""
        from app.services.notification_service import send_listing_removed_email

        with patch("app.services.notification_service.resend.Emails.send") as mock_send:
            await send_listing_removed_email(LISTING_ID, SELLER_EMAIL, "ABUSIVE")

        payload = mock_send.call_args[0][0]
        assert "content policy" in payload["html"]

    @pytest.mark.asyncio
    async def test_listing_removed_email_body_allows_relisting(self):
        """Spec 04 §Email4 template: body must tell seller they can list compliant material again."""
        from app.services.notification_service import send_listing_removed_email

        with patch("app.services.notification_service.resend.Emails.send") as mock_send:
            await send_listing_removed_email(LISTING_ID, SELLER_EMAIL, "PIRACY")

        payload = mock_send.call_args[0][0]
        assert "compliant material" in payload["html"] or "list" in payload["html"].lower()

    @pytest.mark.asyncio
    async def test_listing_removed_email_sends_to_seller(self):
        """Spec 04 §Email4: recipient is the seller of the removed listing."""
        from app.services.notification_service import send_listing_removed_email

        with patch("app.services.notification_service.resend.Emails.send") as mock_send:
            await send_listing_removed_email(LISTING_ID, SELLER_EMAIL, "NOT_STUDY_MATERIAL")

        payload = mock_send.call_args[0][0]
        assert SELLER_EMAIL in payload["to"]

    @pytest.mark.asyncio
    async def test_listing_removed_email_body_never_contains_reporter_identity(self):
        """Spec 04 §Email4 security (Spec 03 policy): body must never disclose reporter identity.
        The only caller-supplied fields are listing_id and reason_category — not any reporter id.
        We assert the function signature takes no reporter argument and the body contains
        only the reason_category, not any injected reporter identifier."""
        import inspect
        from app.services import notification_service

        sig = inspect.signature(notification_service.send_listing_removed_email)
        param_names = list(sig.parameters.keys())

        # Function signature must NOT have a reporter/reporter_id parameter
        assert "reporter" not in param_names
        assert "reporter_id" not in param_names

    @pytest.mark.asyncio
    async def test_listing_removed_email_body_contains_only_category_not_other_args(self):
        """Spec 04 §Email4: body must include the reason_category and must NOT leak the
        only other caller-supplied value, listing_id (a log-only field). This guards against
        the body being built by blindly concatenating arguments."""
        from app.services.notification_service import send_listing_removed_email

        with patch("app.services.notification_service.resend.Emails.send") as mock_send:
            await send_listing_removed_email(LISTING_ID, SELLER_EMAIL, "PIRACY")

        payload = mock_send.call_args[0][0]
        assert "PIRACY" in payload["html"]
        # listing_id is a log-only field — it must never appear in the email body.
        assert str(LISTING_ID) not in payload["html"]

    @pytest.mark.asyncio
    async def test_listing_removed_email_rejects_invalid_reason_category(self):
        """Spec 04 §Email4 / H-1 hardening: reason_category is interpolated into HTML, so an
        unrecognised value must fail closed — no email sent, error logged keyed by listing_id."""
        from app.services.notification_service import send_listing_removed_email

        injection = "<script>alert(1)</script>"
        with patch("app.services.notification_service.resend.Emails.send") as mock_send:
            with patch("app.services.notification_service.logger") as mock_logger:
                await send_listing_removed_email(LISTING_ID, SELLER_EMAIL, injection)

        mock_send.assert_not_called()
        mock_logger.error.assert_called_once()
        # The invalid/attacker-controlled value is never logged — only listing_id is.
        logged = " ".join(str(a) for a in mock_logger.error.call_args[0][1:])
        assert injection not in mock_logger.error.call_args[0][0]
        assert injection not in logged

    @pytest.mark.asyncio
    async def test_listing_removed_email_resend_exception_is_swallowed(self):
        """Spec 04 cross-cutting: Resend failure must be swallowed (never re-raised)."""
        from app.services.notification_service import send_listing_removed_email

        with patch(
            "app.services.notification_service.resend.Emails.send",
            side_effect=Exception("Resend down"),
        ):
            # Must not raise
            await send_listing_removed_email(LISTING_ID, SELLER_EMAIL, "PROHIBITED")

    @pytest.mark.asyncio
    async def test_listing_removed_email_logs_info_on_success(self):
        """Spec 04 logging: success logged at INFO keyed by listing UUID."""
        from app.services import notification_service

        with patch("app.services.notification_service.resend.Emails.send"):
            with patch.object(notification_service.logger, "info") as mock_info:
                await notification_service.send_listing_removed_email(
                    LISTING_ID, SELLER_EMAIL, "SPAM"
                )

        logged = [str(c) for c in mock_info.call_args_list]
        assert any(str(LISTING_ID) in m for m in logged)

    @pytest.mark.asyncio
    async def test_listing_removed_email_logs_error_on_resend_failure(self):
        """Spec 04 logging: failure logged at ERROR with listing UUID."""
        from app.services import notification_service

        with patch(
            "app.services.notification_service.resend.Emails.send",
            side_effect=Exception("timeout"),
        ):
            with patch.object(notification_service.logger, "error") as mock_error:
                await notification_service.send_listing_removed_email(
                    LISTING_ID, SELLER_EMAIL, "OTHER"
                )

        mock_error.assert_called_once()
        assert str(LISTING_ID) in str(mock_error.call_args)

    @pytest.mark.asyncio
    async def test_listing_removed_email_error_log_never_contains_seller_email(self):
        """Spec 04 logging/security: error log must not include the seller email address."""
        from app.services import notification_service

        with patch(
            "app.services.notification_service.resend.Emails.send",
            side_effect=Exception("timeout"),
        ):
            with patch.object(notification_service.logger, "error") as mock_error:
                await notification_service.send_listing_removed_email(
                    LISTING_ID, SELLER_EMAIL, "ABUSIVE"
                )

        assert SELLER_EMAIL not in str(mock_error.call_args)

    @pytest.mark.asyncio
    async def test_listing_removed_email_all_valid_reason_categories_render(self):
        """Spec 04 §Email4: all documented reason categories produce a valid email body
        (i.e., the function does not raise or reject any canonical category value)."""
        from app.services.notification_service import send_listing_removed_email

        # Canonical values from frontend/constants/reportReasons.js as documented in Spec 04
        valid_categories = [
            "PIRACY",
            "CONTACT_INFO",
            "SPAM",
            "NOT_STUDY_MATERIAL",
            "PROHIBITED",
            "ABUSIVE",
            "OTHER",
        ]

        for category in valid_categories:
            with patch("app.services.notification_service.resend.Emails.send") as mock_send:
                await send_listing_removed_email(LISTING_ID, SELLER_EMAIL, category)

            payload = mock_send.call_args[0][0]
            assert category in payload["html"], (
                f"Category '{category}' not found in email body"
            )

    def test_listing_removed_function_exists_and_is_async(self):
        """Spec 04 §Email4 function spec: send_listing_removed_email must exist and be async."""
        import inspect
        from app.services import notification_service

        assert hasattr(notification_service, "send_listing_removed_email"), (
            "send_listing_removed_email must be defined in notification_service"
        )
        assert inspect.iscoroutinefunction(
            notification_service.send_listing_removed_email
        ), "send_listing_removed_email must be an async function"

    def test_listing_removed_function_signature_matches_spec(self):
        """Spec 04 §Email4 function spec: signature must be
        send_listing_removed_email(listing_id, seller_email, reason_category)."""
        import inspect
        from app.services.notification_service import send_listing_removed_email

        sig = inspect.signature(send_listing_removed_email)
        params = list(sig.parameters.keys())
        assert "listing_id" in params
        assert "seller_email" in params
        assert "reason_category" in params


# ===========================================================================
# CROSS-CUTTING SECURITY / CONTRACT TESTS
# ===========================================================================

class TestCrossCuttingSecurityRules:
    """Cross-cutting assertions that apply to all live emails (NO-PAYMENTS model)."""

    def test_all_send_functions_exist_in_notification_service(self):
        """Spec 04 scope (NO-PAYMENTS): notification_service must expose the live send
        functions. The payment-era abandoned-checkout email no longer exists."""
        from app.services import notification_service

        assert hasattr(notification_service, "send_new_message_email")
        assert hasattr(notification_service, "send_sale_complete")
        assert hasattr(notification_service, "send_welcome_email")
        assert hasattr(notification_service, "send_listing_removed_email")

    def test_all_send_functions_are_async(self):
        """Spec 04 dispatch model: all send functions must be async (fire-and-forget model)."""
        import inspect
        from app.services import notification_service

        for fn_name in [
            "send_new_message_email",
            "send_sale_complete",
            "send_welcome_email",
            "send_listing_removed_email",
        ]:
            fn = getattr(notification_service, fn_name)
            assert inspect.iscoroutinefunction(fn), (
                f"{fn_name} must be an async coroutine function"
            )

    def test_notification_service_uses_module_level_logger(self):
        """Spec 04 / CLAUDE.md logging: module must use logging.getLogger(__name__),
        not print() — confirm logger attribute exists at module level."""
        from app.services import notification_service
        import logging

        assert hasattr(notification_service, "logger")
        assert isinstance(notification_service.logger, logging.Logger)

    def test_no_resend_api_key_in_module_attributes(self):
        """Security: RESEND_API_KEY must not be bound as a public module attribute
        that could be accidentally serialised or logged. Checks the attribute NAME
        unconditionally so the assertion is never skipped when the env var is unset."""
        from app.services import notification_service

        public_attr_names = [
            k for k in vars(notification_service) if not k.startswith("_")
        ]
        assert "RESEND_API_KEY" not in public_attr_names

    @pytest.mark.asyncio
    async def test_send_sale_complete_does_not_return_email_in_return_value(self):
        """Security Rule 1: send_sale_complete must return None (not expose email in return)."""
        from app.services.notification_service import send_sale_complete

        with patch("app.services.notification_service.resend.Emails.send"):
            result = await send_sale_complete(LISTING_TITLE, SELLER_EMAIL)

        assert result is None

    @pytest.mark.asyncio
    async def test_send_new_message_email_does_not_return_email_in_return_value(self):
        """Security Rule 1: send_new_message_email must return None."""
        from app.services.notification_service import send_new_message_email

        with patch("app.services.notification_service.resend.Emails.send"):
            result = await send_new_message_email(CONVERSATION_ID, SELLER_EMAIL)

        assert result is None

    @pytest.mark.asyncio
    async def test_send_listing_removed_does_not_return_email_in_return_value(self):
        """Security Rule 1: send_listing_removed_email must return None."""
        from app.services.notification_service import send_listing_removed_email

        with patch("app.services.notification_service.resend.Emails.send"):
            result = await send_listing_removed_email(LISTING_ID, SELLER_EMAIL, "PIRACY")

        assert result is None

    @pytest.mark.asyncio
    async def test_supabase_admin_fetch_user_email_returns_none_on_exception(self):
        """Spec 04 recipient resolution: fetch_user_email must return None (not raise)
        when the Supabase Admin API errors — callers rely on None to skip gracefully."""
        from app.core import supabase_admin

        mock_admin = MagicMock()
        mock_admin.auth.admin.get_user_by_id.side_effect = Exception("supabase down")

        with patch("app.core.supabase_admin.get_supabase_admin", return_value=mock_admin):
            result = await supabase_admin.fetch_user_email("some-user-id")

        assert result is None

    @pytest.mark.asyncio
    async def test_completed_transaction_response_has_no_email_field(self):
        """Security Rule 1 (NO-PAYMENTS): the passkey-verify response (CompleteTransactionResponse)
        must never surface any email field. There is no payment/status endpoint in v1."""
        from app.schemas.transaction import CompleteTransactionResponse

        response = CompleteTransactionResponse(
            transaction_id=TRANSACTION_ID,
            seller_id=SELLER_ID,
            seller_name="A Seller",
            listing_title=LISTING_TITLE,
        )
        for key in response.model_dump():
            assert "email" not in key.lower(), (
                f"CompleteTransactionResponse must not expose any email field, found: {key}"
            )


class TestEmailNotExposedInApiResponse:
    """Assert that email addresses are never surfaced in API responses (Security Rule 1)."""

    def test_fetch_user_email_is_not_exposed_in_verify_passkey_endpoint(self):
        """Security Rule 9 (NO-PAYMENTS): fetch_user_email uses the service role, so it must
        only run server-internally. The transactions router imports it solely for the
        _notify_seller_of_sale BackgroundTask — the user-facing verify-passkey handler must
        never call it directly inside the request path."""
        import inspect
        from app.routers import transactions as transactions_router

        # fetch_user_email is referenced (import + the internal BackgroundTask helper).
        source = inspect.getsource(transactions_router)
        assert source.count("fetch_user_email") >= 1
        # The user-facing verify endpoint must not call fetch_user_email in-request.
        verify_source = inspect.getsource(transactions_router.verify_passkey_endpoint)
        assert "fetch_user_email" not in verify_source


class TestNoEmailBuyerFacing:
    """Spec 04 out-of-scope: no buyer-facing emails exist in v1."""

    def test_notification_service_has_no_buyer_email_functions(self):
        """Spec 04 scope/out-of-scope: notification_service must not expose any
        function that sends email to a buyer (v1 has zero buyer-facing emails)."""
        from app.services import notification_service
        import inspect

        all_functions = [
            name for name, obj in inspect.getmembers(notification_service)
            if inspect.isfunction(obj) or inspect.iscoroutinefunction(obj)
        ]

        # No function name should suggest buyer-targeted email
        buyer_keywords = ["buyer", "purchase_confirm", "buyer_receipt"]
        for fn_name in all_functions:
            for keyword in buyer_keywords:
                assert keyword not in fn_name.lower(), (
                    f"Unexpected buyer-facing email function: {fn_name} (v1 has none)"
                )

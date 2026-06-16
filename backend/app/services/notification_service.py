import logging
from typing import get_args
from uuid import UUID

import resend

from app.core import config
from app.schemas.report import ReportReason

logger = logging.getLogger(__name__)
# Access the key through the config module instead of `from app.core.config import
# RESEND_API_KEY`, so the secret string is not bound as a discoverable module-level
# attribute of this module (CLAUDE.md: secrets never logged or exposed).
resend.api_key = config.RESEND_API_KEY

# Allowed content-policy categories for the removal email, derived from the canonical
# ReportReason Literal so the two can never drift apart.
_VALID_REASON_CATEGORIES = frozenset(get_args(ReportReason))


async def send_sale_complete(transaction_id: UUID, seller_payout_rupees: int, seller_email: str) -> None:
    """Takes plain values rather than a Transaction ORM object — this runs as a
    FastAPI BackgroundTask, after the request's DB session has closed, so the
    instance would otherwise be detached. Failures are logged, never raised —
    a missed notification must not affect the (already-committed) payment outcome."""
    try:
        resend.Emails.send({
            "from": "NextPrep <no-reply@nextprep.online>",
            "to": [seller_email],
            "subject": "Your listing has been sold!",
            "html": (
                f"<p>Your listing has been purchased. "
                f"₹{seller_payout_rupees} will be credited to your Razorpay account.</p>"
            ),
        })
        logger.info("Sale complete email sent: transaction=%s", transaction_id)
    except Exception as e:
        logger.error("Failed to send sale complete email: transaction=%s error=%s", transaction_id, str(e))


async def send_new_message_email(conversation_id: UUID, seller_email: str) -> None:
    """Takes plain values rather than a Conversation ORM object — runs as a
    FastAPI BackgroundTask after the DB session closes. Failures logged, never raised."""
    try:
        resend.Emails.send({
            "from": "NextPrep <no-reply@nextprep.online>",
            "to": [seller_email],
            "subject": "Someone is interested in your listing",
            "html": (
                "<p>A buyer has sent you a message about your listing on NextPrep. "
                "Log in to reply.</p>"
            ),
        })
        logger.info("First-message email sent: conversation=%s", conversation_id)
    except Exception as e:
        logger.error(
            "Failed to send first-message email: conversation=%s error=%s",
            conversation_id, str(e)
        )


async def send_abandoned_checkout_email(listing_id: UUID, seller_email: str) -> None:
    """Notifies the seller that a buyer abandoned checkout. Takes plain values
    (mirrors `send_sale_complete`) rather than a Transaction ORM object, since the
    scheduler builds its `cancelled` list from a bulk UPDATE...RETURNING and never
    holds onto live ORM rows. Failures are logged, never raised — the scheduler
    must keep cancelling abandoned transactions regardless of whether the email
    provider is reachable."""
    try:
        resend.Emails.send({
            "from": "NextPrep <no-reply@nextprep.online>",
            "to": [seller_email],
            "subject": "A buyer didn't complete checkout",
            "html": "<p>A buyer started a purchase but did not complete payment. Your listing is still available.</p>",
        })
        logger.info("Abandoned checkout email sent: listing=%s", listing_id)
    except Exception as e:
        logger.error("Failed to send abandoned email: listing=%s error=%s", listing_id, str(e))


async def send_listing_removed_email(listing_id: UUID, seller_email: str, reason_category: str) -> None:
    # NOTE: deferred in v1 — no caller is wired yet (see Spec 04 §Email4).
    """Notifies a seller their listing was removed by moderation. Takes plain values
    (mirrors the other senders) rather than a Listing ORM object. Failures are logged,
    never raised. `reason_category` is the content-policy category only — never the
    reporter identity (Spec 03). In v1 the trigger is deferred: moderation is manual via
    the Supabase dashboard, so this function is invoked manually, not wired to any route
    or job."""
    # Fail closed on an unrecognised category: reason_category is interpolated into the
    # email HTML, so never send an unvalidated value. Mirrors the ReportReason allowlist.
    if reason_category not in _VALID_REASON_CATEGORIES:
        logger.error(
            "send_listing_removed_email called with invalid reason_category: listing=%s",
            listing_id,
        )
        return
    try:
        resend.Emails.send({
            "from": "NextPrep <no-reply@nextprep.online>",
            "to": [seller_email],
            "subject": "Your listing was removed from NextPrep",
            "html": (
                f"<p>Your listing was removed from NextPrep because it violated our content "
                f"policy ({reason_category}). If you believe this was a mistake, you can list "
                f"compliant material again.</p>"
            ),
        })
        logger.info("Listing removed email sent: listing=%s", listing_id)
    except Exception as e:
        logger.error("Failed to send listing removed email: listing=%s error=%s", listing_id, str(e))

import logging
from uuid import UUID

import resend

from app.core.config import RESEND_API_KEY

logger = logging.getLogger(__name__)
resend.api_key = RESEND_API_KEY


async def send_sale_complete(transaction_id: UUID, seller_payout_rupees: int, seller_email: str) -> None:
    """Takes plain values rather than a Transaction ORM object — this runs as a
    FastAPI BackgroundTask, after the request's DB session has closed, so the
    instance would otherwise be detached. Failures are logged, never raised —
    a missed notification must not affect the (already-committed) payment outcome."""
    try:
        resend.Emails.send({
            "from": "NextPrep <no-reply@yourdomain.com>",
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
            "from": "NextPrep <no-reply@yourdomain.com>",
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
            "from": "NextPrep <no-reply@yourdomain.com>",
            "to": [seller_email],
            "subject": "A buyer didn't complete checkout",
            "html": "<p>A buyer started a purchase but did not complete payment. Your listing is still available.</p>",
        })
        logger.info("Abandoned checkout email sent: listing=%s", listing_id)
    except Exception as e:
        logger.error("Failed to send abandoned email: listing=%s error=%s", listing_id, str(e))

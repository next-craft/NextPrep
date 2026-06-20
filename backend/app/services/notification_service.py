import html
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

_FROM = "NextPrep <no-reply@nextprep.online>"

# Allowed content-policy categories for the removal email, derived from the canonical
# ReportReason Literal so the two can never drift apart.
_VALID_REASON_CATEGORIES = frozenset(get_args(ReportReason))

# ── Email theme ────────────────────────────────────────────────────────────
# Mirrors the frontend "paper & ink" design tokens (frontend/app/globals.css):
# cornsilk paper, deep-bronze ink, bronze CTA, warm bronze borders, olive muted.
_PAPER = "#fefae0"
_INK = "#32210f"
_CARD = "#fffdf6"
_BRONZE = "#96622e"
_BRONZE_FG = "#fdf6e9"
_BORDER = "#e7d4bf"
_MUTED = "#7a6a52"
_KICKER = "#96622e"
# Web fonts mirror the site (Fraunces display / Hanken Grotesk body); clients that
# don't load them fall back to the same families the Tailwind config declares.
_FONT_DISPLAY = "'Fraunces', Georgia, 'Times New Roman', serif"
_FONT_SANS = "'Hanken Grotesk', -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif"


def _button(href: str, label: str) -> str:
    """Bulletproof bronze CTA — VML for Outlook, padded anchor everywhere else."""
    return f"""
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center" style="margin:28px auto 4px;">
        <tr><td align="center" bgcolor="{_BRONZE}" style="border-radius:10px;">
          <!--[if mso]>
          <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="urn:schemas-microsoft-com:office:word"
            href="{href}" style="height:48px;v-text-anchor:middle;width:280px;" arcsize="21%" stroke="f" fillcolor="{_BRONZE}">
          <w:anchorlock/><center style="color:{_BRONZE_FG};font-family:Arial,sans-serif;font-size:15px;font-weight:bold;">{label}</center>
          </v:roundrect>
          <![endif]-->
          <!--[if !mso]><!-->
          <a href="{href}" target="_blank"
            style="display:inline-block;padding:14px 32px;font-family:{_FONT_SANS};font-size:15px;font-weight:600;line-height:20px;color:{_BRONZE_FG};text-decoration:none;border-radius:10px;">{label}</a>
          <!--<![endif]-->
        </td></tr>
      </table>"""


def _render(*, preheader: str, kicker: str, heading: str, body_html: str,
            cta_label: str, cta_href: str) -> str:
    """Wrap email content in the shared NextPrep chrome (header wordmark, paper
    card, bronze CTA, footer). `body_html` is trusted markup built by callers;
    any user-supplied value interpolated into it must be escaped by the caller."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="color-scheme" content="light only">
  <meta name="supported-color-schemes" content="light only">
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Hanken+Grotesk:wght@400;500;600&display=swap" rel="stylesheet">
  <title>{heading}</title>
</head>
<body style="margin:0;padding:0;width:100%;background-color:{_PAPER};">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;font-size:1px;line-height:1px;color:{_PAPER};">{preheader}</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:{_PAPER};">
    <tr><td align="center" style="padding:40px 16px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:560px;width:100%;">
        <!-- Brand header -->
        <tr><td style="padding:0 4px 22px;text-align:center;">
          <span style="font-family:{_FONT_DISPLAY};font-size:26px;font-weight:600;letter-spacing:-0.5px;color:{_INK};">Next<span style="color:{_BRONZE};">Prep</span></span>
        </td></tr>
        <!-- Card -->
        <tr><td style="background-color:{_CARD};border:1px solid {_BORDER};border-radius:16px;padding:40px 36px;box-shadow:0 8px 30px -10px rgba(50,33,15,0.16);">
          <p style="margin:0 0 14px;font-family:{_FONT_SANS};font-size:12px;font-weight:600;letter-spacing:1.6px;text-transform:uppercase;color:{_KICKER};">{kicker}</p>
          <h1 style="margin:0 0 18px;font-family:{_FONT_DISPLAY};font-size:27px;line-height:1.2;font-weight:600;color:{_INK};">{heading}</h1>
          <div style="font-family:{_FONT_SANS};font-size:16px;line-height:1.65;color:{_INK};">{body_html}</div>
          {_button(cta_href, cta_label)}
        </td></tr>
        <!-- Footer -->
        <tr><td style="padding:26px 24px 0;text-align:center;">
          <p style="margin:0 0 6px;font-family:{_FONT_DISPLAY};font-size:14px;font-weight:600;color:{_INK};">NextPrep</p>
          <p style="margin:0;font-family:{_FONT_SANS};font-size:12px;line-height:1.6;color:{_MUTED};">India's marketplace for exam books, notes &amp; coaching material.<br>In-person meetup only — no shipping, no online payments.</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


async def send_sale_complete(listing_title: str, seller_email: str) -> None:
    """Notifies the seller that a buyer verified the passkey and the listing is sold.
    Runs as a FastAPI BackgroundTask after the request's DB session has closed, so it
    takes plain values, not an ORM object. Failures are logged, never raised — a missed
    notification must not affect the (already-committed) sale. The platform processes no
    payment, so this carries no amount."""
    safe_title = html.escape(listing_title)
    body = (
        f"<p style='margin:0 0 16px;'>Great news — a buyer confirmed the exchange of "
        f"<strong style='color:{_BRONZE};'>{safe_title}</strong> with your passkey at the "
        f"meetup. The listing is now marked as <strong>sold</strong>.</p>"
        f"<p style='margin:0;'>Your <strong>books sold</strong> count has gone up, which builds "
        f"your seller reputation. Sell 10 verified items to earn your verified badge.</p>"
    )
    try:
        resend.Emails.send({
            "from": _FROM,
            "to": [seller_email],
            "subject": "Your listing has been sold!",
            "html": _render(
                preheader=f"{safe_title} is confirmed sold.",
                kicker="Sale confirmed",
                heading="Your listing has been sold!",
                body_html=body,
                cta_label="View your dashboard",
                cta_href=f"{config.FRONTEND_URL}/dashboard",
            ),
        })
        logger.info("Sale complete email sent: listing=%s", listing_title)
    except Exception as e:
        logger.error("Failed to send sale complete email: listing=%s error=%s", listing_title, str(e))


async def send_welcome_email(user_id: UUID, user_email: str, user_name: str) -> None:
    """Welcomes a user on signup, sent once by the welcome sweep (app/jobs/scheduler.py).
    Takes plain values — runs outside any request DB session. Failures logged, never raised.
    `user_id` is logged for traceability; the email address (PII) is never logged."""
    safe_name = html.escape(user_name)
    body = (
        f"<p style='margin:0 0 16px;'>Hi {safe_name}, welcome aboard — you've joined India's "
        f"marketplace for exam books, handwritten notes, and coaching modules, built by students "
        f"for students.</p>"
        f"<p style='margin:0 0 16px;'>Here's how it works:</p>"
        f"<ul style='margin:0 0 16px;padding-left:20px;'>"
        f"<li style='margin:0 0 8px;'><strong>Sell</strong> the material you've finished with — "
        f"books, notes, test series, full bundles.</li>"
        f"<li style='margin:0 0 8px;'><strong>Buy</strong> your next set from a fellow student "
        f"near you.</li>"
        f"<li style='margin:0;'><strong>Meet up</strong>, hand over the material, and confirm "
        f"with a passkey. No shipping, no online payments.</li>"
        f"</ul>"
        f"<p style='margin:0;'>Ready when you are — happy studying!</p>"
    )
    try:
        resend.Emails.send({
            "from": _FROM,
            "to": [user_email],
            "subject": "Welcome to NextPrep!",
            "html": _render(
                preheader="Buy and sell exam study material with fellow students.",
                kicker="Welcome aboard",
                heading="Welcome to NextPrep!",
                body_html=body,
                cta_label="Browse study material",
                cta_href=f"{config.FRONTEND_URL}/listings",
            ),
        })
        logger.info("Welcome email sent: user=%s", user_id)
    except Exception as e:
        logger.error("Failed to send welcome email: user=%s error=%s", user_id, str(e))


async def send_new_message_email(conversation_id: UUID, seller_email: str) -> None:
    """Takes plain values rather than a Conversation ORM object — runs as a
    FastAPI BackgroundTask after the DB session closes. Failures logged, never raised."""
    # The two phrases below are canonical (asserted by tests/spec) — keep verbatim.
    body = (
        "<p style='margin:0 0 16px;'>A buyer has sent you a message about your listing on "
        "NextPrep. They're interested — reply to answer their questions and arrange a meetup.</p>"
        "<p style='margin:0;'>Log in to reply. We never share your contact details; everything "
        "stays inside the chat until you both agree to meet.</p>"
    )
    try:
        resend.Emails.send({
            "from": _FROM,
            "to": [seller_email],
            "subject": "Someone is interested in your listing",
            "html": _render(
                preheader="A buyer messaged you about your listing.",
                kicker="New message",
                heading="Someone's interested in your listing",
                body_html=body,
                cta_label="Reply to the buyer",
                cta_href=f"{config.FRONTEND_URL}/chat/{conversation_id}",
            ),
        })
        logger.info("First-message email sent: conversation=%s", conversation_id)
    except Exception as e:
        logger.error(
            "Failed to send first-message email: conversation=%s error=%s",
            conversation_id, str(e)
        )


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

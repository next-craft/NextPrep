import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, update

from app.core.database import AsyncSessionLocal
from app.core.supabase_admin import fetch_user_email
from app.models.user import User
from app.services import notification_service

scheduler = AsyncIOScheduler()
logger = logging.getLogger(__name__)


async def send_pending_welcome_emails() -> None:
    """Welcome-email sweep. There are no auth endpoints on FastAPI, so the only signal a
    signup happened is the public.users row the handle_new_user trigger inserts. This job
    finds rows not yet welcomed, sends once, and marks them. The permanent
    welcome_email_sent flag makes it idempotent — a later login is a no-op.

    Service-role email lookup (fetch_user_email) is used here because this is a background
    job, which CLAUDE.md Security Rule 7 permits directly (not a request-path exception).
    """
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(User.id, User.full_name)
            .where(User.welcome_email_sent == False)  # noqa: E712
            .limit(50)
        )).all()

        for user_id, full_name in rows:
            # Atomic claim — flip the flag BEFORE dispatch (house pattern:
            # conversations.first_message_notified). At-most-once: a transient Resend
            # failure means no retry, acceptable for a welcome email.
            claimed = (await db.execute(
                update(User)
                .where(User.id == user_id, User.welcome_email_sent == False)  # noqa: E712
                .values(welcome_email_sent=True)
                .returning(User.id)
            )).scalar_one_or_none()
            if claimed is None:
                continue
            await db.commit()

            email = await fetch_user_email(str(user_id))
            if email:
                await notification_service.send_welcome_email(user_id, email, full_name)
            else:
                logger.warning("Could not resolve email for welcome: user=%s", user_id)


scheduler.add_job(
    send_pending_welcome_emails,
    trigger="interval",
    minutes=5,
    id="welcome_emails",
    coalesce=True,
    max_instances=1,
)

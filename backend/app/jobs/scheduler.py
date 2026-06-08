import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, update

from app.core.database import AsyncSessionLocal
from app.core.redis import create_redis
from app.core.supabase_admin import fetch_user_email
from app.models.transaction import Transaction
from app.services import notification_service

scheduler = AsyncIOScheduler()
logger = logging.getLogger(__name__)

# APScheduler jobs run outside request scope, so `Depends(get_redis)` / `app.state.redis`
# aren't available here — the job owns one long-lived client of its own instead.
_redis = None


def _get_redis():
    global _redis
    if _redis is None:
        _redis = create_redis()
    return _redis


@scheduler.scheduled_job("interval", minutes=5)
async def cancel_abandoned_transactions():
    redis = _get_redis()
    async with AsyncSessionLocal() as db:
        cutoff = datetime.utcnow() - timedelta(minutes=15)
        result = await db.execute(
            select(Transaction).where(
                Transaction.status == "initiated",
                Transaction.created_at < cutoff,
            )
        )
        transactions = result.scalars().all()
        logger.info("APScheduler: found %d abandoned transactions", len(transactions))

        cancelled = []
        for txn in transactions:
            # Atomic conditional update — mirrors the webhook's winner-selection pattern
            # (UPDATE ... WHERE status = 'initiated' RETURNING) so a transaction the
            # webhook just released in parallel can never be clobbered back to cancelled.
            # RETURNING the plain columns (not the ORM row) — the bulk UPDATE bypasses
            # the identity map, so a stale `txn` would keep reading status="initiated".
            update_result = await db.execute(
                update(Transaction)
                .where(Transaction.id == txn.id, Transaction.status == "initiated")
                .values(status="cancelled")
                .returning(Transaction.listing_id, Transaction.seller_id)
            )
            row = update_result.fetchone()
            if row:
                cancelled.append((row.listing_id, row.seller_id))

        await db.commit()
        logger.info("APScheduler: cancelled %d transactions", len(cancelled))

        for listing_id, seller_id in cancelled:
            notified_key = f"abandoned_notified:{listing_id}"
            # Atomic claim — SET ... NX so two abandoned transactions for the same
            # listing in one run can't both pass the cooldown and double-send.
            claimed = await redis.set(notified_key, "1", ex=21600, nx=True)
            if not claimed:
                continue
            seller_email = await fetch_user_email(str(seller_id))
            if not seller_email:
                # The cooldown is already claimed for 6h — note the loss explicitly
                # so an email-resolution outage is visible rather than silent.
                logger.warning("Abandoned-checkout notify skipped (no email): listing=%s", listing_id)
                continue
            await notification_service.send_abandoned_checkout_email(listing_id, seller_email)

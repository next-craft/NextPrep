import logging
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listing import Listing
from app.models.report import Report
from app.schemas.report import ReportCreate, ReportAck

logger = logging.getLogger(__name__)

REPORT_RATE_LIMIT = 20          # reports per reporter per hour
REPORT_RATE_TTL = 3600          # seconds


async def create_report(
    db: AsyncSession, redis, reporter_id: str, data: ReportCreate
) -> ReportAck:
    """Record a user's report against a listing.

    Never auto-hides the listing — reports feed a manual moderation queue.
    Never returns report counts or other reporters' identities.
    Idempotent on a duplicate (listing, reporter) pair.
    """
    # 1. Rate limit per reporter (anti-abuse / anti-enumeration).
    #    Checked before the 404 lookup intentionally — this prevents listing-ID
    #    enumeration even when the listing does not exist or is already deleted.
    key = f"report_rate:{reporter_id}"
    count = await redis.incr(key)
    # Set the 1-hour window atomically: nx=True writes the TTL only when the key
    # has none yet, so concurrent first requests can't repeatedly reset/extend it
    # (avoids the incr-then-expire race).
    await redis.expire(key, REPORT_RATE_TTL, nx=True)
    if count > REPORT_RATE_LIMIT:
        logger.warning("report_rate_limited reporter=%s", reporter_id)
        raise HTTPException(status_code=429, detail="Too many reports. Try again later.")

    # 2. Listing must exist and not already be removed.
    listing = await db.scalar(
        select(Listing).where(
            Listing.id == data.listing_id,
            Listing.deleted_at.is_(None),
        )
    )
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")

    # 3. Idempotent: a duplicate (listing, reporter) is silently accepted.
    #    Never reveal whether a prior report exists.
    existing = await db.scalar(
        select(Report).where(
            Report.listing_id == data.listing_id,
            Report.reporter_id == UUID(reporter_id),
        )
    )
    if existing:
        logger.info("report_duplicate listing=%s", data.listing_id)
        return ReportAck()

    report = Report(
        listing_id=data.listing_id,
        reporter_id=UUID(reporter_id),
        reason=data.reason,
        note=data.note,
    )
    db.add(report)
    await db.commit()
    # No db.refresh needed — we return ReportAck(), not the ORM object.

    # No PII beyond UUIDs; never log the free-text note.
    logger.info("report_created listing=%s reason=%s", data.listing_id, data.reason)
    return ReportAck()

import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.core.security import verify_passkey, verify_token
from app.core.supabase_admin import fetch_user_email
from app.models.listing import Listing
from app.schemas.transaction import (
    CompleteTransactionResponse,
    RatingCreate,
    RatingResponse,
    TransactionListItem,
    VerifyPasskeyRequest,
)
from app.services import notification_service, transaction_service

router = APIRouter(prefix="/transactions", tags=["transactions"])
logger = logging.getLogger(__name__)


async def _notify_seller_of_sale(seller_id: UUID, listing_title: str) -> None:
    """Runs as a BackgroundTask after the response is sent — the sale is already
    committed, so a slow Resend/Supabase Admin call must not delay the buyer's response."""
    seller_email = await fetch_user_email(str(seller_id))
    if seller_email:
        await notification_service.send_sale_complete(listing_title, seller_email)
    else:
        logger.warning("Could not resolve seller email for sold listing=%s", listing_title)


@router.post("/verify-passkey", response_model=CompleteTransactionResponse)
async def verify_passkey_endpoint(
    data: VerifyPasskeyRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token),
    redis=Depends(get_redis),
):
    """The buyer enters the 8-digit code the seller shared at the meetup. A correct
    code completes the transaction: listing -> SOLD, counters bumped, buyer can rate."""
    listing_id = str(data.listing_id)
    buyer_id = user["sub"]

    # Check 1 — listing exists, not sold, not paused
    listing = await db.get(Listing, data.listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found.")
    if listing.passkey_invalidated:
        raise HTTPException(400, "This listing has already been sold.")
    if not listing.is_available:
        raise HTTPException(400, "This listing is temporarily unavailable.")

    # Check 1b — buyer cannot complete their own listing
    if str(listing.seller_id) == buyer_id:
        raise HTTPException(403, "You cannot purchase your own listing.")

    # Check 2 — atomically reserve an attempt slot BEFORE comparing the hash. Fails
    # CLOSED: if Redis is unavailable the only brute-force control is gone, so the
    # request must be rejected (503), never allowed through unmetered.
    attempts_key = f"passkey_attempts:{listing_id}:{buyer_id}"
    try:
        attempt_no = await transaction_service.register_attempt(redis, attempts_key)
    except Exception as e:
        logger.error(
            "Passkey attempt counter unavailable (failing closed): listing=%s buyer=%s err=%s",
            listing_id, buyer_id, str(e),
        )
        raise HTTPException(503, "Verification temporarily unavailable. Please try again shortly.")
    if attempt_no > 3:
        logger.warning("Blocked buyer attempt: listing=%s buyer=%s", listing_id, buyer_id)
        raise HTTPException(403, "You have been blocked from this listing.")

    # Check 3 — verify passkey hash (constant-time)
    if not verify_passkey(data.passkey, listing_id, listing.passkey_hash):
        remaining = max(0, 3 - attempt_no)
        logger.warning(
            "Incorrect passkey: listing=%s buyer=%s attempt=%d remaining=%d",
            listing_id, buyer_id, attempt_no, remaining
        )
        if remaining == 0:
            raise HTTPException(403, "You have been blocked from this listing.")
        raise HTTPException(400, transaction_service.attempts_message(remaining))

    logger.info("Passkey verified: listing=%s buyer=%s", listing_id, buyer_id)
    result = await transaction_service.complete_transaction(db, listing, buyer_id)
    background_tasks.add_task(_notify_seller_of_sale, result.seller_id, result.listing_title)
    return result


@router.get("", response_model=list[TransactionListItem])
async def list_my_transactions(
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token),
):
    return await transaction_service.get_my_transactions(db, user["sub"])


@router.post("/{transaction_id}/rating", response_model=RatingResponse)
async def rate_transaction(
    transaction_id: UUID,
    data: RatingCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token),
):
    return await transaction_service.rate_seller(
        db, transaction_id, user["sub"], data.rating, data.review
    )

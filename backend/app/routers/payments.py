import json
import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import RAZORPAY_WEBHOOK_SECRET
from app.core.database import get_db
from app.core.redis import get_redis
from app.core.security import verify_passkey, verify_token
from app.core.supabase_admin import fetch_user_email
from app.models.listing import Listing
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.payment import (
    OnboardCompleteRequest,
    OnboardCompleteResponse,
    OnboardResponse,
    TransactionStatusResponse,
    VerifyPasskeyRequest,
    VerifyPasskeyResponse,
)
from app.services import notification_service, payment_service

router = APIRouter(prefix="/payments", tags=["payments"])
status_router = APIRouter(tags=["transactions"])
logger = logging.getLogger(__name__)

EXPECTED_EVENT = "payment_link.paid"


async def _notify_seller_of_sale(transaction_id: UUID, seller_id: UUID, seller_payout_rupees: int) -> None:
    """Runs as a BackgroundTask, after the response is sent — DB state is already
    committed and idempotent at this point, so a slow Resend/Supabase Admin API
    call must not delay the webhook's 200 (and risk a Razorpay retry)."""
    seller_email = await fetch_user_email(str(seller_id))
    if seller_email:
        await notification_service.send_sale_complete(transaction_id, seller_payout_rupees, seller_email)
    else:
        logger.warning("Could not resolve seller email for transaction=%s", transaction_id)


@router.post("/verify-passkey", response_model=VerifyPasskeyResponse)
async def verify_passkey_endpoint(
    data: VerifyPasskeyRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token),
    redis=Depends(get_redis),
):
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

    # Check 1b — buyer cannot purchase their own listing
    if str(listing.seller_id) == buyer_id:
        raise HTTPException(403, "You cannot purchase your own listing.")

    # Check 2 — buyer not blocked
    attempts_key = f"passkey_attempts:{listing_id}:{buyer_id}"
    attempts = await redis.get(attempts_key)
    if attempts and int(attempts) >= 3:
        logger.warning("Blocked buyer attempt: listing=%s buyer=%s", listing_id, buyer_id)
        raise HTTPException(403, "You have been blocked from purchasing this listing.")

    # Check 3 — verify passkey hash
    if not verify_passkey(data.passkey, listing_id, listing.passkey_hash):
        count = await payment_service.record_failed_attempt(redis, listing_id, buyer_id)
        remaining = max(0, 3 - count)
        logger.warning(
            "Incorrect passkey: listing=%s buyer=%s attempts=%d remaining=%d",
            listing_id, buyer_id, count, remaining
        )
        if remaining == 0:
            raise HTTPException(403, "You have been blocked from purchasing this listing.")
        raise HTTPException(400, payment_service.attempts_message(remaining))

    logger.info("Passkey verified: listing=%s buyer=%s", listing_id, buyer_id)
    return await payment_service.initiate_payment(db, redis, listing, buyer_id)


@router.post("/onboard", response_model=OnboardResponse)
async def onboard_seller(
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token),
):
    seller = await db.get(User, UUID(user["sub"]))
    if not seller:
        raise HTTPException(404, "User profile not found.")
    return await payment_service.create_onboarding_link(db, seller, user["email"])


@router.post("/onboard/complete", response_model=OnboardCompleteResponse)
async def complete_onboarding(
    data: OnboardCompleteRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token),
):
    seller = await db.get(User, UUID(user["sub"]))
    if not seller:
        raise HTTPException(404, "User profile not found.")
    return await payment_service.complete_onboarding(db, seller, data.razorpay_account_id)


@router.post("/webhook")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")

    # Step 1 — verify HMAC signature
    try:
        payment_service.razorpay_client.utility.verify_webhook_signature(
            body.decode(), signature, RAZORPAY_WEBHOOK_SECRET
        )
    except Exception:
        logger.warning("Invalid webhook signature received")
        return Response(status_code=400)

    payload = json.loads(body)

    # Step 2 — verify event type (return 200 for unknown events — no Razorpay retries)
    event = payload.get("event")
    if event != EXPECTED_EVENT:
        logger.info("Ignoring webhook event: %s", event)
        return Response(status_code=200)

    # Step 3 — extract identifiers
    payment_link_id = payload["payload"]["payment_link"]["entity"]["id"]
    payment_id = payload["payload"]["payment"]["entity"]["id"]
    logger.info("Webhook received: payment_link=%s payment=%s", payment_link_id, payment_id)

    # Step 4 — find transaction
    result = await db.execute(
        select(Transaction).where(Transaction.razorpay_payment_link_id == payment_link_id)
    )
    transaction = result.scalar_one_or_none()
    if not transaction:
        logger.warning("Unknown payment_link_id: %s", payment_link_id)
        return Response(status_code=200)

    # Step 5 — idempotency (already released)
    if transaction.status == "released":
        logger.info("Already processed: transaction=%s", transaction.id)
        return Response(status_code=200)

    # Step 6 — late webhook (transaction cancelled by scheduler — refund immediately)
    if transaction.status != "initiated":
        if transaction.refunded_at is not None:
            logger.info("Late webhook already refunded: transaction=%s", transaction.id)
            return Response(status_code=200)
        logger.warning(
            "Late webhook for transaction=%s status=%s — refunding",
            transaction.id, transaction.status
        )
        await payment_service.refund_transaction(transaction, payment_id)
        await db.commit()
        return Response(status_code=200)

    # Step 7 — atomic transaction status update
    update_result = await db.execute(
        update(Transaction)
        .where(Transaction.id == transaction.id, Transaction.status == "initiated")
        .values(status="released", released_at=datetime.utcnow(), razorpay_payment_id=payment_id)
        .returning(Transaction.id)
    )
    if not update_result.fetchone():
        logger.warning("Race on transaction=%s — already handled", transaction.id)
        return Response(status_code=200)

    # Step 8 — atomic listing update (winner selection — only one buyer can win)
    listing_result = await db.execute(
        update(Listing)
        .where(Listing.id == transaction.listing_id, Listing.is_available == True)
        .values(
            is_available=False,
            sold_at=datetime.utcnow(),
            passkey_invalidated=True,
            passkey_invalidated_at=datetime.utcnow(),
        )
        .returning(Listing.id)
    )
    if not listing_result.fetchone():
        # Concurrent payment — another buyer's webhook already closed the listing
        logger.warning(
            "Concurrent payment on listing=%s — refunding transaction=%s",
            transaction.listing_id, transaction.id
        )
        await payment_service.refund_transaction(transaction, payment_id)
        transaction.status = "cancelled"
        await db.commit()
        return Response(status_code=200)

    await db.commit()

    # Step 9 — post-payment notification (Razorpay Route handles seller payout automatically).
    # Dispatched as a background task — DB state is already committed/idempotent, so a
    # slow Resend/Supabase Admin API call must not delay the 200 back to Razorpay.
    logger.info("Released: transaction=%s listing=%s", transaction.id, transaction.listing_id)
    background_tasks.add_task(
        _notify_seller_of_sale, transaction.id, transaction.seller_id, transaction.seller_payout_rupees
    )

    return Response(status_code=200)


@status_router.get("/transactions/{transaction_id}/status", response_model=TransactionStatusResponse)
async def get_transaction_status(
    transaction_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token),
):
    buyer_id = user["sub"]
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.buyer_id == UUID(buyer_id),
        )
    )
    transaction = result.scalar_one_or_none()
    if not transaction:
        raise HTTPException(404, "Transaction not found.")

    return TransactionStatusResponse(status=transaction.status, amount_rupees=transaction.amount_rupees)

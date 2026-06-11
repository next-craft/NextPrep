import logging
from datetime import datetime, timedelta

import razorpay
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import FRONTEND_URL, RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET
from app.models.listing import Listing
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.payment import OnboardCompleteResponse, OnboardResponse, VerifyPasskeyResponse

logger = logging.getLogger(__name__)
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


def attempts_message(remaining: int) -> str:
    if remaining == 1:
        return "Incorrect passkey. 1 attempt remaining."
    return f"Incorrect passkey. {remaining} attempts remaining."


async def record_failed_attempt(redis, listing_id: str, buyer_id: str) -> int:
    """Atomically increment the buyer's attempt counter for this listing and
    refresh its 7-day TTL. Returns the new attempt count."""
    attempts_key = f"passkey_attempts:{listing_id}:{buyer_id}"
    pipe = redis.pipeline()
    pipe.incr(attempts_key)
    pipe.expire(attempts_key, 604800)  # 7 days
    count, _ = await pipe.execute()
    return count


async def initiate_payment(db: AsyncSession, redis, listing: Listing, buyer_id: str) -> VerifyPasskeyResponse:
    """Create (or reuse) an `initiated` transaction and a Razorpay Payment Link.

    Order matches PAYMENT.md: idempotency check, row lock (concurrent-write guard —
    real winner-selection happens in the webhook), transaction row, payment link.
    """
    listing_id = listing.id

    # Idempotency — return the existing link if one is already initiated
    existing = await db.execute(
        select(Transaction).where(
            Transaction.listing_id == listing_id,
            Transaction.buyer_id == buyer_id,
            Transaction.status == "initiated",
        )
    )
    existing = existing.scalar_one_or_none()
    if existing:
        logger.info("Returning existing payment link: transaction=%s", existing.id)
        return VerifyPasskeyResponse(payment_link_url=existing.razorpay_payment_link_url)

    # Row lock — minor concurrent-write guard; held for milliseconds only
    locked = await db.execute(
        select(Listing)
        .where(
            Listing.id == listing_id,
            Listing.is_available == True,
            Listing.passkey_invalidated == False,
        )
        .with_for_update(skip_locked=True)
    )
    if not locked.scalar_one_or_none():
        raise HTTPException(409, "This listing was just sold. You have not been charged.")

    platform_fee = 0  # 0% in v1 — math.floor(amount * rate) when introduced
    transaction = Transaction(
        listing_id=listing_id,
        buyer_id=buyer_id,
        seller_id=listing.seller_id,
        amount_rupees=listing.asking_price,
        platform_fee_rupees=platform_fee,
        seller_payout_rupees=listing.asking_price - platform_fee,
        status="initiated",
    )
    db.add(transaction)
    await db.flush()  # transaction.id needed before the Razorpay call

    expire_at = datetime.utcnow() + timedelta(minutes=15)
    payment_link = razorpay_client.payment_link.create({
        "amount": transaction.amount_rupees * 100,  # paise — only at this boundary
        "currency": "INR",
        "expire_by": int(expire_at.timestamp()),
        "description": f"Study material: {listing.title}",
        "notify": {"sms": False, "email": False},
        "callback_url": f"{FRONTEND_URL}/transactions/{transaction.id}/status",
        "callback_method": "get",
    })

    transaction.razorpay_payment_link_id = payment_link["id"]
    transaction.razorpay_payment_link_url = payment_link["short_url"]
    await db.commit()

    logger.info(
        "Payment link created: transaction=%s listing=%s buyer=%s",
        transaction.id, listing_id, buyer_id,
    )
    return VerifyPasskeyResponse(payment_link_url=payment_link["short_url"])


async def refund_transaction(transaction: Transaction, payment_id: str) -> None:
    """Refund a payment in full and stamp the transaction as refunded.
    Paise conversion happens here only — the second (and last) boundary site,
    mirroring the `* 100` at `payment_link.create()`."""
    razorpay_client.payment.refund(payment_id, {"amount": transaction.amount_rupees * 100})
    transaction.refunded_at = datetime.utcnow()
    logger.info("Refunded: transaction=%s payment=%s", transaction.id, payment_id)


async def create_onboarding_link(db: AsyncSession, seller: User, seller_email: str) -> OnboardResponse:
    """Create a Razorpay Route linked account and return its KYC onboarding URL.
    `razorpay_account_id` is NOT saved here — only after KYC completes
    (see complete_onboarding). `seller_email` comes from the JWT payload
    (`user["email"]`) per spec — `fetch_user_email` (service role) is reserved
    for the webhook/scheduler only, where no JWT is available. Identity itself
    is still derived solely from `payload["sub"]` (the `db.get` lookup above)."""
    if seller.razorpay_account_id:
        return OnboardResponse(message="Already onboarded")

    try:
        account = razorpay_client.account.create({
            "email": seller_email,
            "profile": {"category": "individual", "subcategory": "individual"},
            "legal_business_name": seller.full_name,
            "business_type": "individual",
        })
        onboarding_url = razorpay_client.stakeholder.create(account["id"], {})["url"]
    except razorpay.errors.BadRequestError as e:
        logger.error("Razorpay Route onboarding failed for seller=%s: %s", seller.id, str(e))
        raise HTTPException(
            status_code=502,
            detail=(
                f"Razorpay onboarding is unavailable (linked-account API said: '{e}'). "
                "This usually means Razorpay Route is not yet activated on the account."
            ),
        )

    logger.info("Razorpay onboarding started for seller=%s account=%s", seller.id, account["id"])
    return OnboardResponse(onboarding_url=onboarding_url, razorpay_account_id=account["id"])


async def complete_onboarding(db: AsyncSession, seller: User, razorpay_account_id: str) -> OnboardCompleteResponse:
    """Verify the linked account's KYC status with Razorpay before granting the gate."""
    if seller.razorpay_account_id:
        return OnboardCompleteResponse(status="already_complete")

    try:
        account = razorpay_client.account.fetch(razorpay_account_id)
    except razorpay.errors.BadRequestError as e:
        logger.error("Razorpay account fetch failed for seller=%s: %s", seller.id, str(e))
        raise HTTPException(status_code=502, detail=f"Could not verify Razorpay account: {e}")
    if account.get("profile", {}).get("status") != "activated":
        raise HTTPException(400, "Razorpay account KYC not yet complete. Please finish verification.")

    seller.razorpay_account_id = razorpay_account_id
    await db.commit()

    logger.info("Seller onboarding complete: seller=%s razorpay_account=%s", seller.id, razorpay_account_id)
    return OnboardCompleteResponse(status="complete")

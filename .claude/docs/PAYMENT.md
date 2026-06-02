# PAYMENT.md — Payment Workflow (Final Spec v4)

---

## Overview

- No escrow. Money never sits with you.
- Razorpay Route handles 100% payout to seller at payment time.
- Platform fee is 0% in v1. Config only — no code change needed when introduced.
- Passkey proves in-person meetup happened before any money moves.
- Webhook is the authoritative payment confirmation — never the client callback.

---

## Seller onboarding (pre-requisite)

Seller must connect a Razorpay account via Razorpay Route before creating a listing.
One-time KYC. Without it, "Create Listing" is disabled with prompt: "Complete payment setup to start selling."

---

## Listing creation — passkey

On listing creation, generate an 8-digit numeric passkey:

```python
import secrets
passkey = str(secrets.randbelow(100_000_000)).zfill(8)  # e.g. "03918472"
passkey_hash = hash_passkey(passkey, str(listing.id))
# Store passkey_hash in DB — never store plaintext
# Return plaintext passkey in creation API response — only time it exists
```

Seller sees the plaintext passkey on the creation success screen only.
"Regenerate passkey" button on seller dashboard creates a new passkey + new hash.
Old hash is overwritten. Passkey can never be recovered — only regenerated.

---

## Buy Now

Buyer clicks Buy Now:
- **No DB writes. No transaction. No listing state change.**
- Buyer's UI shows passkey input field
- Listing stays available to everyone

Buy Now is a pure UI event. Backend is not called.

---

## Passkey validation — POST /payments/verify-passkey

Checks run in this exact order. Stop immediately on any failure.

### Check 1 — Is listing available?

```python
listing = await db.get(Listing, listing_id)
if not listing or not listing.is_available or listing.passkey_invalidated:
    raise HTTPException(400, "This listing has already been sold.")
```

### Check 2 — Is buyer blocked?

```python
attempts_key = f"passkey_attempts:{listing_id}:{buyer_id}"
attempts = await redis.get(attempts_key)
if attempts and int(attempts) >= 3:
    raise HTTPException(403, "You have been blocked from purchasing this listing.")
```

Hash comparison never runs if buyer is blocked.

### Check 3 — Verify passkey hash

```python
from app.core.security import verify_passkey

if not verify_passkey(submitted_passkey, str(listing_id), listing.passkey_hash):
    # Increment attempt counter
    pipe = redis.pipeline()
    pipe.incr(attempts_key)
    pipe.expire(attempts_key, 604800)  # 7 days
    count, _ = await pipe.execute()

    remaining = max(0, 3 - count)
    if remaining == 0:
        raise HTTPException(403, "You have been blocked from purchasing this listing.")
    raise HTTPException(400, f"Incorrect passkey. {remaining} attempts remaining.")
```

If correct → proceed immediately to payment initiation in the same request.

---

## Payment initiation (on correct passkey)

### Step 1 — Idempotency: check for existing initiated transaction

```python
existing = await db.execute(
    select(Transaction)
    .where(
        Transaction.listing_id == listing_id,
        Transaction.buyer_id == buyer_id,
        Transaction.status == 'initiated'
    )
)
existing = existing.scalar_one_or_none()
if existing:
    return {"payment_link_url": existing.razorpay_payment_link_url}
```

Returns same link. No new transaction. No new Razorpay call.

### Step 2 — Acquire row lock (concurrent write guard)

```python
locked = await db.execute(
    select(Listing)
    .where(
        Listing.id == listing_id,
        Listing.is_available == True,
        Listing.passkey_invalidated == False
    )
    .with_for_update(skip_locked=True)
)
if not locked.scalar_one_or_none():
    raise HTTPException(409, "This listing was just sold. You have not been charged.")
```

Note: this lock is held for milliseconds. It does not prevent multiple buyers from
eventually getting payment links. The real concurrency protection is in webhook Step 8.

### Step 3 — Create transaction row

```python
transaction = Transaction(
    listing_id=listing_id,
    buyer_id=buyer_id,
    seller_id=listing.seller_id,
    amount_rupees=listing.asking_price,
    platform_fee_rupees=0,           # 0% in v1
    seller_payout_rupees=listing.asking_price,
    status='initiated'
)
db.add(transaction)
await db.flush()  # get the id before Razorpay call
```

Partial unique index prevents duplicate initiated transactions:
```sql
CREATE UNIQUE INDEX one_active_transaction_per_buyer_listing
ON transactions (listing_id, buyer_id) WHERE status = 'initiated';
```

### Step 4 — Generate Razorpay Payment Link (15-minute expiry)

```python
import datetime

expire_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=15)

payment_link = razorpay_client.payment_link.create({
    "amount": transaction.amount_rupees * 100,   # Razorpay requires paise
    "currency": "INR",
    "expire_by": int(expire_at.timestamp()),
    "description": f"Study material: {listing.title}",
    "notify": {"sms": False, "email": False},
    "callback_url": f"{FRONTEND_URL}/transactions/{transaction.id}/status",
    "callback_method": "get"
})

transaction.razorpay_payment_link_id = payment_link["id"]
transaction.razorpay_payment_link_url = payment_link["short_url"]
await db.commit()
```

Razorpay link expiry is synchronised with the 15-minute APScheduler cancellation.
Razorpay rejects payment attempts on expired links automatically.

**Important:** `amount_rupees * 100` is the only place paise appear. All storage and
display is in whole rupees.

**Platform fee calculation when introduced (month 2):**
```python
import math
platform_fee = math.floor(amount_rupees * fee_rate)  # floor, not round
seller_payout = amount_rupees - platform_fee
```

### Step 5 — Return payment link to buyer

Buyer is redirected to Razorpay. Passkey is NOT invalidated at this point.
Passkey remains valid until a payment successfully completes.

---

## Payment abandonment

APScheduler Job 1 — runs every 5 minutes:

```python
# backend/app/jobs/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('interval', minutes=5)
async def cancel_abandoned_transactions():
    logger = logging.getLogger(__name__)
    async with AsyncSessionLocal() as db:
        cutoff = datetime.utcnow() - timedelta(minutes=15)
        result = await db.execute(
            select(Transaction)
            .where(Transaction.status == 'initiated', Transaction.created_at < cutoff)
        )
        transactions = result.scalars().all()
        logger.info("APScheduler: found %d abandoned transactions", len(transactions))

        for txn in transactions:
            txn.status = 'cancelled'

            # Seller email with 6h cooldown per listing
            notified_key = f"abandoned_notified:{txn.listing_id}"
            already_notified = await redis.get(notified_key)
            if not already_notified:
                await notification_service.send_abandoned_checkout_email(txn)
                await redis.set(notified_key, 1, ex=21600)  # 6 hours

        await db.commit()
```

On cancellation:
- `status = 'cancelled'`
- Listing stays available
- Passkey stays valid and reusable
- No passkey attempt consumed
- No refund (no money was taken)
- Seller email sent with 6h cooldown per listing (max 1 email per listing per 6 hours)

---

## Successful payment — webhook handler

### Authoritative flow (never reverse this order)

```
Razorpay webhook (server-to-server)
→ verify HMAC signature
→ verify event type
→ update DB atomically
→ buyer's polling detects status change → success screen shown
```

The callback URL shows "Payment processing..." only.
It polls `GET /transactions/{id}/status` every 2 seconds.
It NEVER triggers DB updates.

### Complete webhook handler

```python
# backend/app/routers/payments.py
import json
import logging
from datetime import datetime
from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update, select
from app.core.database import get_db
from app.models.transaction import Transaction
from app.models.listing import Listing
import razorpay

router = APIRouter()
logger = logging.getLogger(__name__)
EXPECTED_EVENT = "payment_link.paid"

razorpay_client = razorpay.Client(
    auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)
)

@router.post("/payments/webhook")
async def handle_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")

    # Step 1 — verify HMAC signature
    try:
        razorpay_client.utility.verify_webhook_signature(
            body.decode(), signature, RAZORPAY_WEBHOOK_SECRET
        )
    except Exception:
        logger.warning("Invalid webhook signature")
        return Response(status_code=400)

    payload = json.loads(body)

    # Step 2 — verify event type
    event = payload.get("event")
    if event != EXPECTED_EVENT:
        logger.info("Ignoring webhook event: %s", event)
        return Response(status_code=200)  # 200, not 4xx — prevents Razorpay retries

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

    # Step 5 — idempotency check
    if transaction.status == 'released':
        logger.info("Already processed: transaction=%s", transaction.id)
        return Response(status_code=200)

    # Step 6 — late webhook check
    if transaction.status != 'initiated':
        logger.warning("Late webhook for transaction=%s status=%s — refunding",
                       transaction.id, transaction.status)
        razorpay_client.payment.refund(payment_id,
            {"amount": transaction.amount_rupees * 100})
        transaction.refunded_at = datetime.utcnow()
        await db.commit()
        return Response(status_code=200)

    # Step 7 — atomic transaction status update
    update_result = await db.execute(
        update(Transaction)
        .where(Transaction.id == transaction.id, Transaction.status == 'initiated')
        .values(
            status='released',
            released_at=datetime.utcnow(),
            razorpay_payment_id=payment_id
        )
        .returning(Transaction.id)
    )
    if not update_result.fetchone():
        logger.warning("Race on transaction=%s — already handled", transaction.id)
        return Response(status_code=200)

    # Step 8 — atomic listing update (real winner-selection)
    listing_result = await db.execute(
        update(Listing)
        .where(Listing.id == transaction.listing_id, Listing.is_available == True)
        .values(
            is_available=False,
            sold_at=datetime.utcnow(),
            passkey_invalidated=True,
            passkey_invalidated_at=datetime.utcnow()
        )
        .returning(Listing.id)
    )
    if not listing_result.fetchone():
        # Concurrent payment — another buyer's payment completed first
        logger.warning("Concurrent payment on listing=%s — refunding transaction=%s",
                       transaction.listing_id, transaction.id)
        razorpay_client.payment.refund(payment_id,
            {"amount": transaction.amount_rupees * 100})
        transaction.refunded_at = datetime.utcnow()
        transaction.status = 'cancelled'
        await db.commit()
        return Response(status_code=200)

    await db.commit()

    # Step 9 — post-payment actions
    logger.info("Released: transaction=%s listing=%s", transaction.id, transaction.listing_id)
    await notification_service.send_sale_complete(transaction)
    # Razorpay Route automatically sends 100% to seller's linked account

    return Response(status_code=200)
```

---

## Passkey audit and lifecycle

| State | `passkey_hash` | `passkey_invalidated` | `passkey_invalidated_at` |
|-------|---------------|----------------------|--------------------------|
| Active listing | stored | FALSE | NULL |
| Sale completed | stored | TRUE | timestamp |
| Listing paused/suspended | stored | FALSE | NULL |
| Relisted after failed sale | unchanged | FALSE | NULL |
| Relisted after completed sale | new hash | FALSE | NULL |

The hash stays in the column forever for audit purposes.
It is NEVER returned in any API response once `passkey_invalidated = TRUE`.
A completed sale's passkey hash is proof of which passkey was used and when.

---

## APScheduler jobs summary

**Only one job exists:**

Job 1 — Cancel abandoned transactions
- Schedule: every 5 minutes
- Query: `status = 'initiated' AND created_at < now() - 15 minutes`
- Action: `status = cancelled`, conditional seller email (6h cooldown per listing)

No escrow release job. No auto-confirm job. No refund job. Money never sits with you.

---

## What does NOT exist in this payment system

- No escrow — money never held by platform
- No `pending` transaction status — Buy Now creates nothing
- No `disputed` transaction status — blocked buyers tracked in Redis only
- No `confirmed` status — passkey replaces self-reported confirmation
- No refund job — refunds triggered inline in webhook handler only
- No global passkey attempt counter — always per-buyer per-listing
- No callback-driven DB updates — webhook is the only authoritative source
- No reopening of cancelled transactions — late webhooks always refund
- No seller email spam — max one notification per listing per 6 hours
- No Razorpay payment links without `expire_by` — always 15-minute expiry
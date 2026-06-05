# Spec 09: Payment

## Purpose

This spec covers the full end-to-end payment flow for Study Material Exchange India — from seller onboarding on Razorpay Route, through in-person meetup passkey verification, to Razorpay Payment Link generation, webhook-authoritative confirmation, and automated abandonment handling via APScheduler. The payment system is designed around one core constraint: money never sits with the platform. Razorpay Route disburses 100% of the payment directly to the seller's linked account at the moment of payment. The passkey mechanism replaces escrow-based confirmation — the buyer and seller must physically meet, the seller shares the passkey, and only then does the payment link unlock. Race conditions between concurrent buyers are resolved atomically in the webhook handler via a conditional UPDATE on the listing. The v1 platform fee is 0%; the fee calculation is wired in code but evaluates to zero.

---

## Depends on

- **Spec 06 — Schema:** `listings`, `transactions`, `public.users` tables, `one_active_transaction_per_buyer_listing` partial unique index
- **Spec 07 — Auth:** `verify_token` dependency, `user["sub"]` as buyer UUID
- **Spec 08 — Passkey:** `hash_passkey`, `verify_passkey` in `security.py`, Redis attempt tracking

---

## Scope

**In scope:**
- Seller Razorpay Route account onboarding (pre-listing gate)
- `POST /payments/verify-passkey` — passkey check + payment link generation in one request
- `POST /payments/webhook` — HMAC signature verification, idempotency, race-condition handling, refunds
- `GET /transactions/{id}/status` — buyer polling endpoint
- APScheduler Job 1 — cancel abandoned transactions + conditional seller email
- Frontend passkey input, redirect to Razorpay, polling-based status page
- Passkey regeneration on seller dashboard

**Out of scope:**
- Platform fee (config exists, value is 0% in v1)
- Dispute resolution — no `disputed` status exists
- Admin panel
- Refund initiated by seller or admin (only auto-refund on concurrent/late webhook)
- Automated moderation
- Shipping or delivery tracking

---

## Seller onboarding — Razorpay Route

Before a seller can create a listing, they must connect a Razorpay account via Razorpay Route (KYC). This is a one-time step.

### Gate logic

On `POST /listings`, check if the seller has a linked Razorpay account:

```python
# backend/app/services/listing_service.py
async def create_listing(db: AsyncSession, seller_id: str, data: ListingCreate):
    seller = await db.get(User, seller_id)
    if not seller.razorpay_account_id:
        raise HTTPException(403, "Complete payment setup to start selling.")
    # ... proceed with listing creation
```

Frontend disables "Create Listing" if `razorpay_account_id` is null on the user profile:

```jsx
// frontend/components/listings/CreateListingButton.jsx
'use client'
import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

export default function CreateListingButton() {
  const { data: me } = useQuery({
    queryKey: ['me'],
    queryFn: () => api.get('/users/me').then(r => r.data)
  })

  const isReady = me?.razorpay_account_id

  return (
    <div>
      <button
        disabled={!isReady}
        className={isReady ? '' : 'opacity-50 cursor-not-allowed'}
        onClick={() => router.push('/listings/new')}
      >
        Create Listing
      </button>
      {!isReady && (
        <p className="text-sm text-muted-foreground mt-1">
          Complete payment setup to start selling.
        </p>
      )}
    </div>
  )
}
```

### Razorpay Route onboarding flow

```
Seller clicks "Connect Payment Account"
→ Backend calls Razorpay Route API to create linked account
→ Redirects seller to Razorpay KYC URL
→ On completion, Razorpay webhook (account.activated) fires
→ Backend saves razorpay_account_id to users table
```

```python
# backend/app/routers/payments.py
@router.post("/payments/onboard")
async def onboard_seller(
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token)
):
    seller_id = user["sub"]
    seller = await db.get(User, seller_id)
    if seller.razorpay_account_id:
        return {"message": "Already onboarded"}

    account = razorpay_client.account.create({
        "email": user["email"],
        "profile": {"category": "individual", "subcategory": "individual"},
        "legal_business_name": seller.full_name,
        "business_type": "individual"
    })

    seller.razorpay_account_id = account["id"]
    await db.commit()

    onboarding_url = razorpay_client.stakeholder.create(
        account["id"], {}
    )["url"]

    logger.info("Razorpay onboarding initiated for seller=%s", seller_id)
    return {"onboarding_url": onboarding_url}
```

`users` table requires an additional column:

```sql
ALTER TABLE public.users ADD COLUMN razorpay_account_id TEXT;
```

Alembic migration required — see Files to create.

---

## Passkey generation at listing creation

On listing creation, an 8-digit numeric passkey is generated, hashed with HMAC-SHA256, and only the hash is stored:

```python
# backend/app/services/listing_service.py
import secrets
from app.core.security import hash_passkey

async def create_listing(db: AsyncSession, seller_id: str, data: ListingCreate):
    listing = Listing(**data.model_dump(), seller_id=seller_id)
    db.add(listing)
    await db.flush()  # get listing.id before hashing

    passkey = str(secrets.randbelow(100_000_000)).zfill(8)
    listing.passkey_hash = hash_passkey(passkey, str(listing.id))
    await db.commit()
    await db.refresh(listing)

    logger.info("Listing created: listing=%s seller=%s", listing.id, seller_id)
    return {"listing": listing, "passkey": passkey}  # plaintext only here
```

The plaintext passkey is returned in the API response once and is never stored. The seller must save it immediately. It is shown on the creation success screen only.

---

## Passkey regeneration

Seller can regenerate the passkey from their dashboard. Old hash is overwritten. Old passkey is permanently unrecoverable.

```python
# backend/app/routers/listings.py
@router.post("/listings/{listing_id}/regenerate-passkey")
async def regenerate_passkey(
    listing_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token)
):
    seller_id = user["sub"]
    listing = await db.get(Listing, listing_id)

    if not listing or listing.seller_id != seller_id:
        raise HTTPException(403, "Not your listing.")
    if not listing.is_available:
        raise HTTPException(400, "Cannot regenerate passkey for unavailable listing.")

    passkey = str(secrets.randbelow(100_000_000)).zfill(8)
    listing.passkey_hash = hash_passkey(passkey, str(listing.id))
    await db.commit()

    logger.info("Passkey regenerated: listing=%s seller=%s", listing_id, seller_id)
    return {"passkey": passkey}
```

---

## Buy Now — frontend only

Buyer clicks Buy Now. **No API call is made. No DB row is created.**

```jsx
// frontend/components/listings/BuyNowSection.jsx
'use client'
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import api from '@/lib/api'

export default function BuyNowSection({ listingId }) {
  const [passkey, setPasskey] = useState('')
  const [showInput, setShowInput] = useState(false)

  const verify = useMutation({
    mutationFn: () => api.post('/payments/verify-passkey', {
      listing_id: listingId,
      passkey
    }),
    onSuccess: (res) => {
      window.location.href = res.data.payment_link_url
    }
  })

  if (!showInput) {
    return (
      <button onClick={() => setShowInput(true)}>
        Buy Now
      </button>
    )
  }

  return (
    <div>
      <p className="text-sm mb-2">
        Meet the seller in person. Ask them for the 8-digit passkey to proceed.
      </p>
      <input
        type="text"
        inputMode="numeric"
        maxLength={8}
        value={passkey}
        onChange={e => setPasskey(e.target.value.replace(/\D/g, ''))}
        placeholder="Enter 8-digit passkey"
        className="border rounded px-3 py-2 w-full"
      />
      <button
        onClick={() => verify.mutate()}
        disabled={passkey.length !== 8 || verify.isPending}
        className="mt-2 w-full"
      >
        {verify.isPending ? 'Verifying...' : 'Confirm Purchase'}
      </button>
      {verify.isError && (
        <p className="text-red-500 text-sm mt-1">
          {verify.error?.response?.data?.detail}
        </p>
      )}
    </div>
  )
}
```

---

## POST /payments/verify-passkey

Passkey verification and payment initiation happen in a single request. Checks run in strict order — stop on first failure.

```python
# backend/app/routers/payments.py
from pydantic import BaseModel
from uuid import UUID

class VerifyPasskeyRequest(BaseModel):
    listing_id: UUID
    passkey: str

@router.post("/payments/verify-passkey")
async def verify_passkey_and_initiate(
    body: VerifyPasskeyRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token)
):
    buyer_id = user["sub"]
    listing_id = body.listing_id

    # Check 1 — listing availability
    listing = await db.get(Listing, listing_id)
    if not listing or not listing.is_available or listing.passkey_invalidated:
        raise HTTPException(400, "This listing has already been sold.")

    # Check 2 — buyer not blocked
    attempts_key = f"passkey_attempts:{listing_id}:{buyer_id}"
    attempts = await redis.get(attempts_key)
    if attempts and int(attempts) >= 3:
        raise HTTPException(403, "You have been blocked from purchasing this listing.")

    # Check 3 — verify passkey hash (constant-time)
    if not verify_passkey(body.passkey, str(listing_id), listing.passkey_hash):
        pipe = redis.pipeline()
        pipe.incr(attempts_key)
        pipe.expire(attempts_key, 604800)  # 7 days
        count, _ = await pipe.execute()

        remaining = max(0, 3 - count)
        if remaining == 0:
            raise HTTPException(403, "You have been blocked from purchasing this listing.")
        raise HTTPException(400, f"Incorrect passkey. {remaining} attempts remaining.")

    # Passkey correct — proceed to payment initiation

    # Idempotency: return existing link if one exists
    existing = await db.execute(
        select(Transaction).where(
            Transaction.listing_id == listing_id,
            Transaction.buyer_id == buyer_id,
            Transaction.status == 'initiated'
        )
    )
    existing = existing.scalar_one_or_none()
    if existing:
        logger.info("Returning existing payment link: transaction=%s", existing.id)
        return {"payment_link_url": existing.razorpay_payment_link_url}

    # Acquire row lock
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

    # Create transaction row
    platform_fee = 0  # 0% in v1; use math.floor(amount * rate) when introduced
    transaction = Transaction(
        listing_id=listing_id,
        buyer_id=buyer_id,
        seller_id=listing.seller_id,
        amount_rupees=listing.asking_price,
        platform_fee_rupees=platform_fee,
        seller_payout_rupees=listing.asking_price - platform_fee,
        status='initiated'
    )
    db.add(transaction)
    await db.flush()

    # Generate Razorpay Payment Link (15-minute expiry)
    expire_at = datetime.utcnow() + timedelta(minutes=15)
    payment_link = razorpay_client.payment_link.create({
        "amount": transaction.amount_rupees * 100,  # paise — only here
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

    logger.info(
        "Payment link created: transaction=%s listing=%s buyer=%s",
        transaction.id, listing_id, buyer_id
    )
    return {"payment_link_url": payment_link["short_url"]}
```

---

## POST /payments/webhook

The webhook is the **only** authoritative source of payment confirmation. Client callbacks are never trusted.

```python
# backend/app/routers/payments.py
import json
import hmac
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

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

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
    if transaction.status == 'released':
        logger.info("Already processed: transaction=%s", transaction.id)
        return Response(status_code=200)

    # Step 6 — late webhook (transaction cancelled by scheduler — refund immediately)
    if transaction.status != 'initiated':
        logger.warning(
            "Late webhook for transaction=%s status=%s — refunding",
            transaction.id, transaction.status
        )
        razorpay_client.payment.refund(payment_id, {"amount": transaction.amount_rupees * 100})
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

    # Step 8 — atomic listing update (winner selection — only one buyer can win)
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
        # Concurrent payment — another buyer's webhook already closed the listing
        logger.warning(
            "Concurrent payment on listing=%s — refunding transaction=%s",
            transaction.listing_id, transaction.id
        )
        razorpay_client.payment.refund(payment_id, {"amount": transaction.amount_rupees * 100})
        transaction.refunded_at = datetime.utcnow()
        transaction.status = 'cancelled'
        await db.commit()
        return Response(status_code=200)

    await db.commit()

    # Step 9 — post-payment notifications (Razorpay Route handles seller payout automatically)
    logger.info("Released: transaction=%s listing=%s", transaction.id, transaction.listing_id)
    await notification_service.send_sale_complete(transaction)

    return Response(status_code=200)
```

### Race condition model

| Scenario | Outcome |
|---|---|
| Buyer submits passkey twice | Idempotency check returns same payment link |
| Two buyers submit correct passkey simultaneously | Both may get payment links; `FOR UPDATE SKIP LOCKED` reduces but does not eliminate duplicates |
| Two buyers pay simultaneously | Step 8 `UPDATE ... WHERE is_available=TRUE RETURNING id` — only one succeeds; second gets refunded |
| Webhook arrives after 15-min cancellation | Step 6 detects `status != 'initiated'`; refund issued immediately |
| Webhook arrives twice (Razorpay retry) | Step 5 detects `status == 'released'`; returns 200 without action |

---

## GET /transactions/{id}/status

Polling endpoint — called every 2 seconds from the buyer's status page.

```python
# backend/app/routers/payments.py
@router.get("/transactions/{transaction_id}/status")
async def get_transaction_status(
    transaction_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token)
):
    buyer_id = user["sub"]
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.buyer_id == buyer_id
        )
    )
    transaction = result.scalar_one_or_none()
    if not transaction:
        raise HTTPException(404, "Transaction not found.")

    return {
        "status": transaction.status,
        "amount_rupees": transaction.amount_rupees
    }
```

### Buyer status page

```jsx
// frontend/app/transactions/[id]/status/page.jsx
'use client'
import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

export default function TransactionStatusPage({ params }) {
  const { data, isLoading } = useQuery({
    queryKey: ['transaction-status', params.id],
    queryFn: () => api.get(`/transactions/${params.id}/status`).then(r => r.data),
    refetchInterval: (data) => data?.status === 'initiated' ? 2000 : false
  })

  if (isLoading) return <p>Payment processing...</p>

  if (data?.status === 'released') {
    return (
      <div>
        <h1>Payment Successful</h1>
        <p>Your purchase is complete. Contact the seller to arrange pickup.</p>
      </div>
    )
  }

  if (data?.status === 'cancelled') {
    return (
      <div>
        <h1>Payment Cancelled</h1>
        <p>Your payment window expired. You have not been charged. Return to the listing to try again.</p>
      </div>
    )
  }

  return <p>Payment processing...</p>
}
```

---

## APScheduler — cancel abandoned transactions

One job. Runs every 5 minutes. Cancels transactions where `status = 'initiated'` and `created_at < now() - 15 minutes`.

```python
# backend/app/jobs/scheduler.py
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.redis import redis
from app.models.transaction import Transaction
from app.services import notification_service

scheduler = AsyncIOScheduler()
logger = logging.getLogger(__name__)

@scheduler.scheduled_job('interval', minutes=5)
async def cancel_abandoned_transactions():
    async with AsyncSessionLocal() as db:
        cutoff = datetime.utcnow() - timedelta(minutes=15)
        result = await db.execute(
            select(Transaction).where(
                Transaction.status == 'initiated',
                Transaction.created_at < cutoff
            )
        )
        transactions = result.scalars().all()
        logger.info("APScheduler: found %d abandoned transactions", len(transactions))

        for txn in transactions:
            txn.status = 'cancelled'

            notified_key = f"abandoned_notified:{txn.listing_id}"
            already_notified = await redis.get(notified_key)
            if not already_notified:
                await notification_service.send_abandoned_checkout_email(txn)
                await redis.set(notified_key, 1, ex=21600)  # 6-hour cooldown

        await db.commit()
        logger.info("APScheduler: cancelled %d transactions", len(transactions))
```

Scheduler must be started in `main.py`:

```python
# backend/app/main.py
from app.jobs.scheduler import scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)
```

---

## Email notifications

Two email types for payments:

### Sale complete (buyer + seller)

```python
# backend/app/services/notification_service.py
import logging
from app.core.config import settings
import resend

logger = logging.getLogger(__name__)
resend.api_key = settings.RESEND_API_KEY

async def send_sale_complete(transaction):
    try:
        resend.Emails.send({
            "from": "NextPrep <no-reply@yourdomain.com>",
            "to": [transaction.seller_email],
            "subject": "Your listing has been sold!",
            "html": f"<p>Your listing has been purchased. ₹{transaction.seller_payout_rupees} will be credited to your Razorpay account.</p>"
        })
        logger.info("Sale complete email sent: transaction=%s", transaction.id)
    except Exception as e:
        logger.error("Failed to send sale complete email: transaction=%s error=%s", transaction.id, str(e))
```

### Abandoned checkout (seller only, 6h cooldown per listing)

```python
async def send_abandoned_checkout_email(transaction):
    try:
        resend.Emails.send({
            "from": "NextPrep <no-reply@yourdomain.com>",
            "to": [transaction.seller_email],
            "subject": "A buyer didn't complete checkout",
            "html": "<p>A buyer started a purchase but did not complete payment. Your listing is still available.</p>"
        })
        logger.info("Abandoned checkout email sent: listing=%s", transaction.listing_id)
    except Exception as e:
        logger.error("Failed to send abandoned email: listing=%s error=%s", transaction.listing_id, str(e))
```

Seller email is fetched from `payload["email"]` via JWT or joined from `auth.users`. Do not store email in `public.users`. Pass it through the notification call after resolving from the token or a service-role query.

---

## Passkey lifecycle

| State | `passkey_hash` | `passkey_invalidated` | `passkey_invalidated_at` |
|---|---|---|---|
| Active listing | stored | FALSE | NULL |
| Payment initiated | stored | FALSE | NULL |
| Sale completed | stored | TRUE | timestamp |
| Listing paused/suspended | stored | FALSE | NULL |
| Relisted after failed sale | unchanged | FALSE | NULL |
| Relisted after completed sale | new hash | FALSE | NULL |

The hash is never returned in any API response when `passkey_invalidated = TRUE`. The stored hash is a permanent audit record.

---

## Files to create

```
backend/app/routers/payments.py
backend/app/jobs/scheduler.py
backend/app/services/notification_service.py
backend/alembic/versions/<timestamp>_add_razorpay_account_id_to_users.py
frontend/app/transactions/[id]/status/page.jsx
frontend/components/listings/BuyNowSection.jsx
frontend/components/listings/CreateListingButton.jsx
```

---

## Files to modify

```
backend/app/main.py
  — import and start scheduler in lifespan context manager

backend/app/routers/__init__.py or main.py
  — register payments router

backend/app/services/listing_service.py
  — add passkey generation on listing creation
  — add seller onboarding check before create

backend/app/models/user.py
  — add razorpay_account_id: Mapped[Optional[str]]

frontend/app/listings/[id]/page.jsx
  — embed BuyNowSection component (client boundary)
```

---

## New dependencies

```
# backend
razorpay          # Razorpay Python SDK — payment links, refunds, Route
apscheduler       # APScheduler — abandoned transaction job
resend            # Resend email SDK
```

No new frontend dependencies.

---

## Security considerations

The following rules from CLAUDE.md apply directly to this feature:

- **Rule 2** — Always verify Razorpay webhook HMAC signature before processing. Enforced in Step 1 of the webhook handler.
- **Rule 3** — Return 200 for unrecognised webhook events — never 4xx. Enforced in Step 2 (unknown events) and in all webhook branches.
- **Rule 5** — `hmac.compare_digest` used in `verify_passkey` — never `==`. Enforced in `security.py`.
- **Rule 9** — `SUPABASE_SERVICE_ROLE_KEY` for background jobs only — APScheduler uses `AsyncSessionLocal` directly (no request context), acceptable.
- **Rule 10** — `PASSKEY_HMAC_SECRET` never logged, never returned in any response.
- **Rule 11** — `hmac.compare_digest` in `verify_passkey` prevents timing attacks.
- **Rule 12** — No reopening cancelled transactions. Late webhooks always trigger refund, never status reversal.
- Seller contact info is never returned in any payment or transaction API response — only UUIDs and amounts.
- `RAZORPAY_KEY_SECRET` and `RAZORPAY_WEBHOOK_SECRET` are backend-only env vars, never exposed to frontend.
- Paise conversion (`amount_rupees * 100`) happens only at the Razorpay API boundary — all storage and display in rupees.

---

## Definition of done

- [ ] Seller without `razorpay_account_id` receives 403 on `POST /listings`
- [ ] Frontend "Create Listing" button is disabled with explanatory text when `razorpay_account_id` is null
- [ ] `POST /payments/verify-passkey` returns 400 after 3 wrong attempts; 4th attempt returns 403 without running hash comparison
- [ ] Correct passkey returns a Razorpay payment link URL and buyer is redirected
- [ ] Submitting the correct passkey a second time returns the same payment link (idempotency)
- [ ] `POST /payments/webhook` with invalid HMAC signature returns 400
- [ ] `POST /payments/webhook` with unrecognised event type returns 200
- [ ] Successful `payment_link.paid` webhook sets `transaction.status = 'released'`, `listing.is_available = FALSE`, `listing.passkey_invalidated = TRUE`, `listing.sold_at` is not null
- [ ] Duplicate webhook for already-released transaction returns 200 with no DB change
- [ ] Late webhook for cancelled transaction triggers refund and returns 200
- [ ] Concurrent payment scenario: second webhook results in refund; listing remains `is_available = FALSE`
- [ ] APScheduler marks initiated transactions older than 15 minutes as `cancelled`
- [ ] Abandoned seller email is sent at most once per listing per 6 hours
- [ ] `GET /transactions/{id}/status` returns current status; buyer cannot query another buyer's transaction
- [ ] Buyer status page polls every 2 seconds and stops polling when status is `released` or `cancelled`
- [ ] `razorpay_payment_link_url` is never null on any `initiated` transaction in DB
- [ ] DB query confirms no `passkey_invalidated = TRUE AND is_available = TRUE` rows exist after any completed sale
- [ ] All payment events logged with `transaction_id` and `listing_id` — no passkey plaintext, no secrets in logs
- [ ] Passkey regeneration overwrites old hash; old passkey no longer works

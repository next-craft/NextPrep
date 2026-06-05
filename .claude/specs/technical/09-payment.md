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
- `POST /payments/onboard` — create Razorpay linked account, return KYC URL
- `POST /payments/onboard/complete` — verify KYC completion, save `razorpay_account_id`
- `POST /payments/verify-passkey` — passkey check (Spec 08) + payment link generation
- `POST /payments/webhook` — HMAC signature verification, idempotency, race-condition handling, refunds
- `GET /transactions/{id}/status` — buyer polling endpoint
- APScheduler Job 1 — cancel abandoned transactions + conditional seller email
- Frontend passkey input, redirect to Razorpay, polling-based status page
- Seller email resolution via Supabase service role (`auth.users`)

**Out of scope:**
- Platform fee (config exists, value is 0% in v1)
- Dispute resolution — no `disputed` status exists
- Admin panel
- Refund initiated by seller or admin (only auto-refund on concurrent/late webhook)
- Automated moderation
- Shipping or delivery tracking
- Passkey regeneration — fully defined in Spec 08

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
import { useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

export default function CreateListingButton() {
  const router = useRouter()
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
→ POST /payments/onboard creates Razorpay linked account, returns KYC URL
→ Seller completes KYC on Razorpay
→ Razorpay fires account.activated webhook
→ Backend saves razorpay_account_id to users table (only now is the gate open)
```

`razorpay_account_id` is **not** saved at account-creation time. It is saved only when the `account.activated` webhook fires — KYC must be complete before the seller can list.

#### POST /payments/onboard

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
    # Do NOT save account["id"] here — KYC is not yet complete.
    # razorpay_account_id is set by the account.activated webhook handler.

    onboarding_url = razorpay_client.stakeholder.create(
        account["id"], {}
    )["url"]

    logger.info("Razorpay onboarding started for seller=%s account=%s", seller_id, account["id"])
    return {"onboarding_url": onboarding_url, "razorpay_account_id": account["id"]}
```

#### account.activated webhook handler

Razorpay fires `account.activated` when the seller completes KYC. This is handled inside the existing `POST /payments/webhook` endpoint by adding a branch before the `payment_link.paid` check:

```python
# Inside handle_webhook, after signature verification and payload parse:

ROUTE_ACCOUNT_ACTIVATED = "account.activated"

if event == ROUTE_ACCOUNT_ACTIVATED:
    account_id = payload["payload"]["account"]["entity"]["id"]
    email = payload["payload"]["account"]["entity"]["email"]

    # Match seller by email — Razorpay account was created with seller's email
    result = await db.execute(
        select(User).where(User.email_for_lookup == email)
    )
    # public.users has no email column — use the supabase service role to look up by email
    # Resolved via: supabase_admin.auth.admin.list_users() filtered by email
    # Then match to public.users by id
    # See implementation note below.

    logger.info("account.activated: razorpay_account=%s", account_id)
    # Implementation: see "Email-to-user resolution for account.activated" below
    return Response(status_code=200)
```

#### Email-to-user resolution for account.activated

`public.users` has no email column. The seller's email must be resolved from `auth.users` via the Supabase service role. The `POST /payments/onboard` response already returns `razorpay_account_id` to the frontend — store it in the browser session temporarily (not localStorage; use React state or sessionStorage scoped to the onboarding flow) so that the frontend can call a completion-poll endpoint.

**Simpler approach (recommended for v1):** Skip `account.activated` webhook. Instead, have the frontend call `POST /payments/onboard/complete` after Razorpay redirects back, passing the `razorpay_account_id` that was returned from the initial onboard call. The backend verifies the account status via Razorpay API before saving:

```python
class OnboardCompleteRequest(BaseModel):
    razorpay_account_id: str

@router.post("/payments/onboard/complete")
async def complete_onboarding(
    body: OnboardCompleteRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token)
):
    seller_id = user["sub"]
    seller = await db.get(User, seller_id)
    if seller.razorpay_account_id:
        return {"status": "already_complete"}

    # Verify account status with Razorpay before granting access
    account = razorpay_client.account.fetch(body.razorpay_account_id)
    if account.get("profile", {}).get("status") != "activated":
        raise HTTPException(400, "Razorpay account KYC not yet complete. Please finish verification.")

    seller.razorpay_account_id = body.razorpay_account_id
    await db.commit()

    logger.info("Seller onboarding complete: seller=%s razorpay_account=%s",
                seller_id, body.razorpay_account_id)
    return {"status": "complete"}
```

The frontend calls `POST /payments/onboard/complete` after Razorpay redirects to the return URL. If status is not `activated`, it shows "Please complete your KYC on Razorpay." and offers a retry button. The gate (`razorpay_account_id IS NOT NULL`) is only satisfied after this call succeeds.

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

Passkey regeneration is fully defined in **Spec 08 — Passkey**, section "Passkey Regeneration". The endpoint is `PATCH /listings/{id}/passkey` (protected, seller only). It blocks regeneration when `listing.passkey_invalidated = TRUE` (sold listings). Paused listings (`is_available=FALSE, passkey_invalidated=FALSE`) allow regeneration.

This spec does not redefine that endpoint. Implement it as specified in Spec 08.

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

Passkey validation (checks 1–3) is fully defined in **Spec 08 — Passkey**. This section defines only the payment-initiation logic that runs after a correct passkey is confirmed. The checks from Spec 08 must be applied first, in order, before the code below runs.

### Check ordering (from Spec 08 — do not reorder)

1. Listing exists and not sold (`passkey_invalidated=FALSE`) → 400 "This listing has already been sold."
2. Listing not paused (`is_available=TRUE`) → 400 "This listing is temporarily unavailable."
3. Buyer is not the listing's seller → 403 "You cannot purchase your own listing."
4. Redis block check (attempts ≥ 3) → 403 "You have been blocked from purchasing this listing."
5. HMAC passkey verification → 400 `"Incorrect passkey. {remaining} attempts remaining."` or 403 on third failure.

All five checks pass → proceed to `payment_service.initiate_payment`.

### payment_service.initiate_payment

```python
# backend/app/services/payment_service.py
import math
import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.transaction import Transaction
from app.models.listing import Listing
from app.core.config import settings
import razorpay

logger = logging.getLogger(__name__)
razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

async def initiate_payment(db: AsyncSession, listing: Listing, buyer_id: str) -> dict:
    listing_id = listing.id

    # Idempotency: return existing link if one is already initiated for this buyer+listing
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

    # Acquire row lock — minor concurrent write guard
    # Real winner-selection happens in webhook Step 8
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
        from fastapi import HTTPException
        raise HTTPException(409, "This listing was just sold. You have not been charged.")

    # Platform fee: 0% in v1. Use math.floor(amount * rate) when introduced.
    platform_fee = 0
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
    await db.flush()  # get transaction.id before Razorpay call

    # Generate Razorpay Payment Link — 15-minute expiry
    expire_at = datetime.utcnow() + timedelta(minutes=15)
    payment_link = razorpay_client.payment_link.create({
        "amount": transaction.amount_rupees * 100,  # paise — only at this boundary
        "currency": "INR",
        "expire_by": int(expire_at.timestamp()),
        "description": f"Study material: {listing.title}",
        "notify": {"sms": False, "email": False},
        "callback_url": f"{settings.FRONTEND_URL}/transactions/{transaction.id}/status",
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

### Endpoint (in payments router)

```python
# backend/app/routers/payments.py
from app.schemas.payment import VerifyPasskeyRequest, VerifyPasskeyResponse
from app.services import payment_service

@router.post("/payments/verify-passkey", response_model=VerifyPasskeyResponse)
async def verify_passkey_endpoint(
    data: VerifyPasskeyRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token),
    redis=Depends(get_redis),
):
    # Passkey checks 1–5 (see Spec 08) run here.
    # On success, delegate to payment initiation:
    return await payment_service.initiate_payment(db, listing, buyer_id)
```

Schemas (`VerifyPasskeyRequest`, `VerifyPasskeyResponse`) are defined in Spec 08 at `backend/app/schemas/payment.py`.

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

### Resolving seller email

`public.users` has no email column — AUTH.md: "No email, no password_hash, no phone — Supabase Auth owns identity." Email must be resolved from `auth.users` via the Supabase service role key.

**In webhook handler** (has no JWT): use `SUPABASE_SERVICE_ROLE_KEY` to query `auth.users`.
**In APScheduler job** (also has no JWT): same approach.

Both callers must resolve email before calling notification functions. The notification functions accept `seller_email: str` as an explicit argument — they do not resolve it themselves.

```python
# backend/app/core/supabase_admin.py
import os
from supabase import create_client

_admin_client = None

def get_supabase_admin():
    global _admin_client
    if _admin_client is None:
        _admin_client = create_client(
            os.getenv("NEXT_PUBLIC_SUPABASE_URL"),
            os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        )
    return _admin_client

async def fetch_user_email(user_id: str) -> str | None:
    """Fetch email from auth.users using service role. For background jobs and webhook only."""
    admin = get_supabase_admin()
    try:
        response = admin.auth.admin.get_user_by_id(user_id)
        return response.user.email if response.user else None
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Failed to fetch email for user=%s: %s", user_id, str(e))
        return None
```

**Webhook handler** — resolve email after Step 8:

```python
# After db.commit() in successful webhook path:
from app.core.supabase_admin import fetch_user_email

seller_email = await fetch_user_email(str(transaction.seller_id))
if seller_email:
    await notification_service.send_sale_complete(transaction, seller_email)
else:
    logger.warning("Could not resolve seller email for transaction=%s", transaction.id)
```

**APScheduler job** — resolve email per transaction:

```python
for txn in transactions:
    txn.status = 'cancelled'

    notified_key = f"abandoned_notified:{txn.listing_id}"
    already_notified = await redis.get(notified_key)
    if not already_notified:
        seller_email = await fetch_user_email(str(txn.seller_id))
        if seller_email:
            await notification_service.send_abandoned_checkout_email(txn, seller_email)
        await redis.set(notified_key, 1, ex=21600)
```

### Sale complete (seller notification)

```python
# backend/app/services/notification_service.py
import logging
import resend
from app.core.config import settings

logger = logging.getLogger(__name__)
resend.api_key = settings.RESEND_API_KEY

async def send_sale_complete(transaction, seller_email: str) -> None:
    try:
        resend.Emails.send({
            "from": "NextPrep <no-reply@yourdomain.com>",
            "to": [seller_email],
            "subject": "Your listing has been sold!",
            "html": f"<p>Your listing has been purchased. ₹{transaction.seller_payout_rupees} will be credited to your Razorpay account.</p>"
        })
        logger.info("Sale complete email sent: transaction=%s", transaction.id)
    except Exception as e:
        logger.error("Failed to send sale complete email: transaction=%s error=%s", transaction.id, str(e))
```

### Abandoned checkout (seller only, 6h cooldown per listing)

```python
async def send_abandoned_checkout_email(transaction, seller_email: str) -> None:
    try:
        resend.Emails.send({
            "from": "NextPrep <no-reply@yourdomain.com>",
            "to": [seller_email],
            "subject": "A buyer didn't complete checkout",
            "html": "<p>A buyer started a purchase but did not complete payment. Your listing is still available.</p>"
        })
        logger.info("Abandoned checkout email sent: listing=%s", transaction.listing_id)
    except Exception as e:
        logger.error("Failed to send abandoned email: listing=%s error=%s", transaction.listing_id, str(e))

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
backend/app/services/payment_service.py
backend/app/services/notification_service.py
backend/app/core/supabase_admin.py
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

.claude/CLAUDE.md
  — add POST /payments/onboard, POST /payments/onboard/complete,
    GET /transactions/{id}/status to the API endpoints table
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

- [ ] `POST /payments/onboard` returns `onboarding_url` for a seller without `razorpay_account_id`; returns "Already onboarded" if one exists
- [ ] `POST /payments/onboard/complete` with a non-activated Razorpay account returns 400 "KYC not yet complete"
- [ ] `POST /payments/onboard/complete` with an activated account sets `razorpay_account_id` on the seller's `public.users` row
- [ ] Seller without `razorpay_account_id` receives 403 on `POST /listings`
- [ ] Frontend "Create Listing" button is disabled with explanatory text when `razorpay_account_id` is null
- [ ] `POST /payments/verify-passkey` returns 403 on the third wrong attempt (count=3); hash check does not run when count≥3
- [ ] Seller submitting passkey against their own listing receives 403 "You cannot purchase your own listing."
- [ ] Correct passkey returns a Razorpay payment link URL and buyer is redirected
- [ ] Submitting the correct passkey a second time returns the same payment link (idempotency)
- [ ] `POST /payments/webhook` with invalid HMAC signature returns 400
- [ ] `POST /payments/webhook` with unrecognised event type returns 200
- [ ] Successful `payment_link.paid` webhook sets `transaction.status = 'released'`, `listing.is_available = FALSE`, `listing.passkey_invalidated = TRUE`, `listing.sold_at` is not null — all in same DB commit
- [ ] Duplicate webhook for already-released transaction returns 200 with no DB change
- [ ] Late webhook for cancelled transaction triggers refund and returns 200
- [ ] Concurrent payment scenario: second webhook results in refund; listing remains `is_available = FALSE`
- [ ] APScheduler marks initiated transactions older than 15 minutes as `cancelled`
- [ ] Abandoned seller email is sent at most once per listing per 6 hours (Redis key `abandoned_notified:{listing_id}` with TTL 6h)
- [ ] Seller email for both notification types is resolved from `auth.users` via service role — `transaction.seller_email` does not exist and is not accessed anywhere
- [ ] `GET /transactions/{id}/status` returns current status; buyer cannot query another buyer's transaction (returns 404)
- [ ] Buyer status page polls every 2 seconds and stops polling when status is `released` or `cancelled`
- [ ] `razorpay_payment_link_url` is never null on any `initiated` transaction in DB
- [ ] DB query confirms no `passkey_invalidated = TRUE AND is_available = TRUE` rows exist after any completed sale
- [ ] All payment events logged with `transaction_id` and `listing_id` — no passkey plaintext, no secrets in logs

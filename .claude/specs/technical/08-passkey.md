# Spec 08: Passkey

## Purpose

This spec covers the complete passkey subsystem for Study Material Exchange India: generation at listing creation, HMAC-SHA256 hashing and storage, buyer-side validation with Redis-backed attempt tracking, invalidation on successful sale, regeneration from the seller dashboard, and the audit trail embedded in the `listings` table. The passkey is the proof-of-meetup mechanism that gates every payment — a buyer cannot initiate a Razorpay payment link without first submitting the correct 8-digit passkey that only the seller knows. This spec documents every function, endpoint, schema detail, Redis key, and UI surface involved in the passkey lifecycle from generation to invalidation, grounded in the canonical implementations already defined in `AUTH.md` and `PAYMENT.md`.

---

## Depends on

- Spec 06 (Schema) — `listings` table with `passkey_hash`, `passkey_invalidated`, `passkey_invalidated_at` columns
- Spec 07 (Auth) — `verify_token`, `hash_passkey`, `verify_passkey` in `backend/app/core/security.py`; protected route pattern
- `.claude/docs/AUTH.md` — canonical `hash_passkey` and `verify_passkey` implementations
- `.claude/docs/PAYMENT.md` — passkey validation checks, payment initiation flow, passkey audit lifecycle table
- `.claude/docs/SCHEMA.md` — `listings` schema, `passkey_invalidated` column semantics, debug queries

---

## Scope

**In scope:**
- 8-digit numeric passkey generation using `secrets.randbelow`
- HMAC-SHA256 hashing via `hash_passkey(passkey, listing_id)` — already in `security.py`
- Storing only `passkey_hash` in DB — plaintext never persisted beyond the creation response
- `POST /payments/verify-passkey` endpoint — all 3 ordered checks + payment initiation
- Redis attempt tracking: key `passkey_attempts:{listing_id}:{buyer_id}`, max 3 attempts, 7-day TTL
- Passkey invalidation on successful payment (`passkey_invalidated=TRUE`, `passkey_invalidated_at=now()`)
- Passkey regeneration: `PATCH /listings/{id}/passkey` — seller only, overwrites hash, blocked on sold listings (`passkey_invalidated=TRUE`)
- Seller dashboard: display passkey on creation success screen (only time plaintext is shown)
- Seller dashboard: "Regenerate passkey" button
- Buyer UI: passkey input field shown after "Buy Now" click (pure frontend, no backend call)
- Audit trail: `passkey_hash` stays in DB forever after invalidation for forensic use
- Logging every passkey attempt (success and failure), every regeneration, every invalidation

**Out of scope:**
- Passkey length change (8 digits is decided — see DECISIONS.md)
- Argon2 hashing (HMAC-SHA256 is decided — see DECISIONS.md)
- Global attempt counter across all listings for a buyer (always per-buyer per-listing)
- Passkey recovery / reveal — impossible by design (hash only stored)
- Passkey on transaction (passkey is on listing — decided in DECISIONS.md)
- Admin passkey reset — seller regenerates via dashboard only
- Email notification on passkey failure or block — not in v1
- Any passkey-related mobile push notification — not in v1

---

## Passkey Generation

Generated at listing creation time. The seller must have the passkey before any buyer arrives.

```python
import secrets

def generate_passkey() -> str:
    # 8 digits, zero-padded, 100M combinations
    return str(secrets.randbelow(100_000_000)).zfill(8)
```

`secrets.randbelow` uses the OS CSPRNG — no `random` module. The plaintext passkey is:
1. Generated
2. Hashed via `hash_passkey(passkey, str(listing.id))`
3. Stored as `passkey_hash` only
4. Returned in the `POST /listings` response **once** — this is the only time it exists in plaintext anywhere

The hash is computed **after** the listing row is flushed (so `listing.id` exists):

```python
# backend/app/services/listing_service.py
from app.core.security import hash_passkey
import secrets

async def create_listing(db: AsyncSession, seller_id: str, data: ListingCreate) -> dict:
    listing = Listing(
        seller_id=seller_id,
        title=data.title,
        description=data.description,
        exam_category=data.exam_category,
        subject=data.subject,
        listing_type=data.listing_type,
        condition=data.condition,
        asking_price=data.asking_price,
        original_price=data.original_price,
        city=data.city,
        images=data.images,
        passkey_hash="placeholder",   # overwritten below after flush
        passkey_invalidated=False,
    )
    db.add(listing)
    await db.flush()  # listing.id is now available

    passkey = generate_passkey()
    listing.passkey_hash = hash_passkey(passkey, str(listing.id))
    await db.commit()
    await db.refresh(listing)

    logger.info("Listing created: listing=%s seller=%s", listing.id, seller_id)
    return {"listing": listing, "passkey": passkey}  # plaintext returned once
```

The router returns `passkey` in the response body. The seller must note it down — it cannot be retrieved again.

---

## Passkey Hashing

Canonical implementation is in `backend/app/core/security.py` — see `.claude/docs/AUTH.md` "Passkey hashing" section. Do not reproduce or rewrite here.

Key facts:
- HMAC-SHA256 chosen over Argon2: passkey is rate-limited by Redis (3 attempts), not user-chosen. Speed is appropriate. See DECISIONS.md.
- `listing_id` is included in the HMAC message so a hash from one listing cannot validate on another.
- `hmac.compare_digest` mandatory — never `==`.
- `PASSKEY_HMAC_SECRET` must be 32+ random bytes hex. Generate: `python -c "import secrets; print(secrets.token_hex(32))"`

---

## POST /payments/verify-passkey

Protected endpoint. Buyer submits their passkey for a listing. Checks run in exact order — stop on first failure.

### Request and response schemas

```python
# backend/app/schemas/payment.py
from pydantic import BaseModel
import uuid

class VerifyPasskeyRequest(BaseModel):
    listing_id: uuid.UUID
    passkey: str

class VerifyPasskeyResponse(BaseModel):
    payment_link_url: str
```

### Endpoint

```python
# backend/app/routers/payments.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import verify_token, verify_passkey
from app.core.redis import get_redis
from app.schemas.payment import VerifyPasskeyRequest, VerifyPasskeyResponse
from app.models.listing import Listing
from app.services import payment_service
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/payments/verify-passkey", response_model=VerifyPasskeyResponse)
async def verify_passkey_endpoint(
    data: VerifyPasskeyRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token),
    redis=Depends(get_redis),
):
    listing_id = str(data.listing_id)
    buyer_id = user["sub"]
    attempts_key = f"passkey_attempts:{listing_id}:{buyer_id}"

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
    attempts = await redis.get(attempts_key)
    if attempts and int(attempts) >= 3:
        logger.warning("Blocked buyer attempt: listing=%s buyer=%s", listing_id, buyer_id)
        raise HTTPException(403, "You have been blocked from purchasing this listing.")

    # Check 3 — verify passkey hash
    if not verify_passkey(data.passkey, listing_id, listing.passkey_hash):
        pipe = redis.pipeline()
        pipe.incr(attempts_key)
        pipe.expire(attempts_key, 604800)   # 7 days
        count, _ = await pipe.execute()

        remaining = max(0, 3 - count)
        logger.warning(
            "Incorrect passkey: listing=%s buyer=%s attempts=%d remaining=%d",
            listing_id, buyer_id, count, remaining
        )
        if remaining == 0:
            raise HTTPException(403, "You have been blocked from purchasing this listing.")
        raise HTTPException(400, f"Incorrect passkey. {remaining} attempts remaining.")

    logger.info("Passkey verified: listing=%s buyer=%s", listing_id, buyer_id)
    # Proceed to payment initiation — full flow defined in PAYMENT.md
    return await payment_service.initiate_payment(db, redis, listing, buyer_id)
```

### Check ordering rationale

| Order | Check | Why this order |
|-------|-------|----------------|
| 1 | Listing exists, not sold, not paused, not own listing | Fast DB read. Distinct errors for sold vs paused states. Self-purchase rejected before touching Redis. |
| 2 | Redis attempt block | Redis is fast. Prevents hash computation for blocked buyers. |
| 3 | Hash verification | Compute-intensive relative to checks 1–2. Run last. |

Hash comparison **never runs** if the buyer is already blocked. This is intentional — do not reorder.

---

## Redis Attempt Tracking

**Key:** `passkey_attempts:{listing_id}:{buyer_id}`
**Type:** integer (incremented atomically via INCR)
**TTL:** 604800 seconds (7 days) — reset on each increment via EXPIRE
**Max:** 3 attempts — at count=3, buyer is permanently blocked for that listing for 7 days

```python
# On each incorrect attempt:
pipe = redis.pipeline()
pipe.incr(attempts_key)
pipe.expire(attempts_key, 604800)
count, _ = await pipe.execute()

remaining = max(0, 3 - count)
# count=1 → "2 attempts remaining"
# count=2 → "1 attempt remaining"
# count=3 → blocked (403)
```

**Important:** Correct passkey does NOT reset the attempt counter. There is no reason to — a correct passkey immediately proceeds to payment. Attempt counter exists only to gate incorrect attempts.

**Redis failure:** If Redis is unavailable during a passkey attempt, the `pipe.execute()` call raises. This surfaces as HTTP 500. Do not swallow Redis errors silently — log and propagate. A Redis outage means passkey validation cannot proceed (correct behaviour — better to be unavailable than to allow unlimited attempts).

**No global counter:** The key always includes `{listing_id}:{buyer_id}`. A buyer is never globally blocked across all listings. Blocking is scoped to the specific listing they failed on.

---

## Passkey Invalidation

Passkey is invalidated atomically in the webhook handler when payment succeeds (Step 8):

```python
# backend/app/routers/payments.py (webhook handler, Step 8)
from datetime import datetime

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
```

This is the only place `passkey_invalidated` is set to `TRUE`. It happens atomically with `is_available=FALSE` and `sold_at`. These three fields change together or not at all.

**After invalidation:**
- `passkey_hash` stays in DB forever — for audit purposes
- `passkey_invalidated = TRUE`, `passkey_invalidated_at = <timestamp>`
- Any subsequent `POST /payments/verify-passkey` for this listing returns 400 "This listing has already been sold."
- The hash is never returned in any API response once invalidated

**Passkey state lifecycle:**

| Listing state | `passkey_hash` | `passkey_invalidated` | `passkey_invalidated_at` |
|---------------|---------------|----------------------|--------------------------|
| Active listing | stored | FALSE | NULL |
| Sale completed (terminal) | stored (audit) | TRUE | timestamp |
| Listing paused/suspended | stored | FALSE | NULL |
| Relisted after failed sale | unchanged | FALSE | NULL |
| Relisted after completed sale | new hash | FALSE | NULL |

When a listing is re-created after a completed sale (new listing, not same listing), a new passkey is generated. The old listing's hash remains in place on the old listing row.

---

## Passkey Regeneration

Seller can regenerate the passkey from their dashboard at any time. This is the only way to recover if the seller forgets their passkey.

### Endpoint

```
PATCH /listings/{id}/passkey
```

Protected. Seller only. Generates a new passkey, hashes it, and overwrites `passkey_hash`. Only permitted while `passkey_invalidated = FALSE` — consistent with Spec 02, which hides the regenerate button on sold listings. A sold listing's passkey is permanently invalidated; regeneration would be meaningless and is blocked. Does NOT reset buyer attempt counters — a blocked buyer stays blocked; the key format is unchanged after regeneration.

```python
# backend/app/routers/listings.py
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import verify_token, hash_passkey
from app.models.listing import Listing
from app.services.listing_service import generate_passkey
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.patch("/listings/{listing_id}/passkey")
async def regenerate_passkey(
    listing_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token),
):
    listing = await db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found.")
    if str(listing.seller_id) != user["sub"]:
        raise HTTPException(403, "Not your listing.")
    if listing.passkey_invalidated:
        raise HTTPException(400, "Cannot regenerate passkey on a sold listing.")

    passkey = generate_passkey()
    listing.passkey_hash = hash_passkey(passkey, str(listing_id))
    await db.commit()

    logger.info("Passkey regenerated: listing=%s seller=%s", listing_id, user["sub"])
    return {"passkey": passkey}
```

**Response:** Returns `{"passkey": "<new-8-digit>"}`. The seller must record it immediately — it cannot be retrieved again.

**Sold listings:** Returns 400 if `passkey_invalidated = TRUE`. The UI hides the regenerate button on sold listings (Spec 02) so this guard is a backend defence against direct API calls.

**Buyer attempt counters:** Redis keys `passkey_attempts:{listing_id}:{buyer_id}` are NOT reset on regeneration. If a buyer was blocked on 3 wrong attempts for the old passkey, they remain blocked. Regeneration is not an unblock mechanism for buyers — it is a recovery mechanism for sellers who have forgotten their passkey.

---

## POST /listings Response Schema

When a listing is created, the passkey is included in the response:

```python
# backend/app/schemas/listing.py
from pydantic import BaseModel
from typing import Optional
import uuid

class ListingCreateResponse(BaseModel):
    id: uuid.UUID
    title: str
    asking_price: int
    passkey: str              # plaintext — only time it appears
    # ... other listing fields
```

The `passkey` field is present **only** in the create response. It must not appear in:
- `GET /listings` (public listing list)
- `GET /listings/{id}` (public listing detail)
- `PATCH /listings/{id}` (update response)
- Any other endpoint

```python
# backend/app/schemas/listing.py
class ListingPublic(BaseModel):
    id: uuid.UUID
    title: str
    # passkey_hash MUST NOT be included here
    # passkey_invalidated MUST NOT be included here
    asking_price: int
    # ... other public fields
```

---

## Frontend — Passkey Display (Seller)

### Creation success screen

After `POST /listings` succeeds, the seller is shown the passkey once:

```jsx
// frontend/components/listings/PasskeyDisplay.jsx
'use client'
import { useState } from 'react'

export default function PasskeyDisplay({ passkey, listingId }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(passkey)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="rounded-md border border-yellow-300 bg-yellow-50 p-4">
      <p className="text-sm font-medium text-yellow-800">
        Save your passkey — it cannot be shown again
      </p>
      <p className="mt-2 font-mono text-2xl tracking-widest text-yellow-900">
        {passkey}
      </p>
      <button
        onClick={handleCopy}
        className="mt-2 text-sm text-yellow-700 underline"
      >
        {copied ? 'Copied!' : 'Copy passkey'}
      </button>
      <p className="mt-2 text-xs text-yellow-700">
        Share this 8-digit code with the buyer in person to confirm the meetup
        and release payment.
      </p>
    </div>
  )
}
```

This component is shown once on the listing creation success screen. It is never shown again — subsequent visits to the listing page do not include the passkey.

### Regenerate passkey (seller dashboard)

```jsx
// frontend/components/listings/RegeneratePasskey.jsx
'use client'
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import api from '@/lib/api'

export default function RegeneratePasskey({ listingId }) {
  const [newPasskey, setNewPasskey] = useState(null)

  const { mutate, isPending } = useMutation({
    mutationFn: () => api.patch(`/listings/${listingId}/passkey`),
    onSuccess: (res) => setNewPasskey(res.data.passkey),
  })

  return (
    <div>
      <button
        onClick={() => mutate()}
        disabled={isPending}
        className="text-sm text-destructive underline"
      >
        {isPending ? 'Regenerating...' : 'Regenerate passkey'}
      </button>
      {newPasskey && (
        <div className="mt-2 rounded border p-3">
          <p className="text-xs text-muted-foreground">New passkey (save it now):</p>
          <p className="font-mono text-xl tracking-widest">{newPasskey}</p>
        </div>
      )}
    </div>
  )
}
```

---

## Frontend — Passkey Input (Buyer)

"Buy Now" is a pure UI event — no backend call. The passkey input appears after the buyer clicks Buy Now:

```jsx
// frontend/components/listings/PasskeyInput.jsx
'use client'
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import api from '@/lib/api'

export default function PasskeyInput({ listingId, onSuccess }) {
  const [passkey, setPasskey] = useState('')
  const [errorMsg, setErrorMsg] = useState(null)

  const { mutate, isPending } = useMutation({
    mutationFn: () =>
      api.post('/payments/verify-passkey', { listing_id: listingId, passkey }),
    onSuccess: (res) => {
      onSuccess(res.data.payment_link_url)
    },
    onError: (err) => {
      setErrorMsg(err.response?.data?.detail ?? 'Something went wrong.')
    },
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    setErrorMsg(null)
    mutate()
  }

  return (
    <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3">
      <label className="text-sm font-medium">
        Enter the passkey shared by the seller
      </label>
      <input
        type="text"
        inputMode="numeric"
        pattern="\d{8}"
        maxLength={8}
        value={passkey}
        onChange={(e) => setPasskey(e.target.value.replace(/\D/g, ''))}
        className="rounded border px-3 py-2 font-mono text-lg tracking-widest"
        placeholder="00000000"
      />
      {errorMsg && (
        <p className="text-sm text-destructive">{errorMsg}</p>
      )}
      <button
        type="submit"
        disabled={isPending || passkey.length !== 8}
        className="rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
      >
        {isPending ? 'Verifying...' : 'Confirm passkey'}
      </button>
    </form>
  )
}
```

On success, the buyer is redirected to `payment_link_url` (Razorpay). The passkey is never stored in frontend state beyond this form.

---

## Logging Requirements

Every passkey event must be logged. Never log the passkey plaintext or the hash.

| Event | Level | Message format |
|-------|-------|----------------|
| Listing created with passkey | INFO | `"Listing created: listing=%s seller=%s"` |
| Correct passkey submitted | INFO | `"Passkey verified: listing=%s buyer=%s"` |
| Incorrect passkey submitted | WARNING | `"Incorrect passkey: listing=%s buyer=%s attempts=%d remaining=%d"` |
| Buyer blocked (3 attempts) | WARNING | `"Blocked buyer attempt: listing=%s buyer=%s"` |
| Passkey check on sold listing | INFO | (implicit in the 400 response — no separate log needed) |
| Passkey regenerated | INFO | `"Passkey regenerated: listing=%s seller=%s"` |
| Passkey invalidated (in webhook) | INFO | `"Released: transaction=%s listing=%s"` (already in webhook handler) |

Never log:
- `passkey` plaintext
- `passkey_hash` value
- `PASSKEY_HMAC_SECRET`

---

## Schema Reference

Relevant columns on the `listings` table (from Spec 06):

```sql
passkey_hash              TEXT NOT NULL
passkey_invalidated       BOOLEAN DEFAULT FALSE
passkey_invalidated_at    TIMESTAMPTZ DEFAULT NULL
```

No new columns are needed. The schema already supports the full passkey lifecycle.

**Alembic note:** No new migration is needed for this spec — columns already exist. If they were missing, an Alembic migration would be required (never raw schema changes).

---

## Debug Queries

```sql
-- Listings with invalidated passkey — should all be is_available=FALSE
SELECT id, title, is_available, passkey_invalidated, passkey_invalidated_at
FROM listings
WHERE passkey_invalidated = TRUE;

-- Listings with invalidated passkey but still available (impossible state)
SELECT * FROM listings
WHERE passkey_invalidated = TRUE AND is_available = TRUE;

-- Active listings (should have passkey_invalidated=FALSE)
SELECT COUNT(*) FROM listings
WHERE is_available = TRUE AND passkey_invalidated = FALSE;
```

---

## Files to create

```
backend/app/services/listing_service.py          — add generate_passkey(), update create_listing()
backend/app/schemas/payment.py                   — VerifyPasskeyRequest, VerifyPasskeyResponse
backend/app/schemas/listing.py                   — ListingCreate, ListingCreateResponse, ListingPublic
frontend/components/listings/PasskeyDisplay.jsx  — one-time passkey display on creation success
frontend/components/listings/PasskeyInput.jsx    — buyer passkey entry form
frontend/components/listings/RegeneratePasskey.jsx — seller regeneration button + display
```

## Files to modify

```
backend/app/routers/payments.py          — add POST /payments/verify-passkey (passkey checks + payment initiation)
backend/app/routers/listings.py          — add PATCH /listings/{id}/passkey (regeneration endpoint)
frontend/app/(marketplace)/listings/new/page.jsx  — render PasskeyDisplay after successful POST /listings mutation; passkey value comes from mutation response data
.claude/CLAUDE.md                        — add PATCH /listings/{id}/passkey to the API endpoints table: "protected, owner only — regenerate passkey hash"
```

## New dependencies

No new dependencies. All libraries used (`hmac`, `hashlib`, `secrets`) are Python stdlib. `redis`, `sqlalchemy`, `fastapi`, `pydantic` are already in the stack.

---

## Security considerations

The following security rules from CLAUDE.md apply directly to this spec:

- **Rule 5** — Validate ownership before every mutation. `PATCH /listings/{id}/passkey` must check `listing.seller_id == user["sub"]` before regenerating. Any other user (including another seller) gets 403.
- **Rule 10** — `PASSKEY_HMAC_SECRET` never logged, never in responses. `hash_passkey` uses it internally; it must not appear in any log statement or API response. Grep for `PASSKEY_HMAC_SECRET` in logs as part of DoD.
- **Rule 11** — `hmac.compare_digest` for all hash comparisons. `verify_passkey` uses it. Never replace with `==`.
- **Rule 1** — Never expose seller contact info. Passkey responses must not leak seller phone/email. The only passkey-related response fields are `passkey` (plaintext, creation only) and error messages.
- **Rule 12** — No reopening cancelled transactions. This spec does not touch transaction status — passkey regeneration does not reopen a cancelled transaction. The listing itself may still be available after a cancelled transaction, but that is handled in the webhook spec.

**Additional passkey-specific rules:**
- The `passkey_hash` column must never be included in `ListingPublic` or any public-facing schema. The hash leaking would allow offline HMAC preimage attempts.
- `passkey` plaintext is returned exactly once: in the `POST /listings` creation response. If it appears in any other response, that is a bug.
- Redis pipeline (INCR + EXPIRE) must be atomic — do not split into two separate commands, as a crash between them would leave a key with no TTL.

---

## Definition of done

- [ ] `generate_passkey()` returns an 8-digit zero-padded string using `secrets.randbelow`
- [ ] `POST /listings` stores `passkey_hash` in DB and returns `passkey` plaintext in response
- [ ] `GET /listings`, `GET /listings/{id}`, `PATCH /listings/{id}` responses do NOT include `passkey`, `passkey_hash`, or `passkey_invalidated`
- [ ] `POST /payments/verify-passkey` returns 404 if listing does not exist
- [ ] `POST /payments/verify-passkey` returns 400 with `"This listing has already been sold."` if `listing.passkey_invalidated = TRUE`
- [ ] `POST /payments/verify-passkey` returns 400 with `"This listing is temporarily unavailable."` if `listing.is_available = FALSE` and `passkey_invalidated = FALSE` (paused, not sold)
- [ ] `POST /payments/verify-passkey` returns 403 with `"You cannot purchase your own listing."` when caller is the listing's seller
- [ ] `POST /payments/verify-passkey` returns 403 (not 400) if buyer has >= 3 prior incorrect attempts (Redis key exists with value >= 3)
- [ ] `POST /payments/verify-passkey` returns 400 with `"Incorrect passkey. 2 attempts remaining."` on first wrong attempt
- [ ] `POST /payments/verify-passkey` returns 400 with `"Incorrect passkey. 1 attempt remaining."` on second wrong attempt
- [ ] `POST /payments/verify-passkey` returns 403 with `"You have been blocked..."` on third wrong attempt
- [ ] Redis key `passkey_attempts:{listing_id}:{buyer_id}` exists with TTL ~604800 after each wrong attempt — verify with `TTL passkey_attempts:*` in Redis CLI
- [ ] `POST /payments/verify-passkey` with correct passkey proceeds to payment initiation and returns `payment_link_url`
- [ ] Hash comparison uses `hmac.compare_digest` — confirm by reading `security.py`
- [ ] `PATCH /listings/{id}/passkey` returns 403 if caller is not the listing's seller
- [ ] `PATCH /listings/{id}/passkey` returns new 8-digit passkey in response and overwrites `passkey_hash` in DB
- [ ] After regeneration, the old passkey no longer validates (old hash overwritten — verify by submitting old passkey to verify-passkey endpoint, should get 400 incorrect)
- [ ] `PATCH /listings/{id}/passkey` returns 400 with `"Cannot regenerate passkey on a sold listing."` if `passkey_invalidated = TRUE`
- [ ] After regeneration, `passkey_invalidated` remains FALSE in DB (not reset — endpoint blocks when TRUE)
- [ ] Seller dashboard shows PasskeyDisplay on listing creation success — visible once, not on subsequent page loads
- [ ] Seller dashboard shows RegeneratePasskey button, clicking it calls `PATCH /listings/{id}/passkey` and displays new passkey
- [ ] Buyer PasskeyInput only accepts numeric characters, max 8 digits
- [ ] Buyer PasskeyInput "Confirm passkey" button disabled until exactly 8 digits entered
- [ ] Correct passkey redirects buyer to Razorpay payment link URL
- [ ] Passkey verification INFO logged on success with message `"Passkey verified: listing=<uuid> buyer=<uuid>"` — verify in backend logs
- [ ] Incorrect passkey WARNING logged with attempt count — verify in backend logs
- [ ] `passkey_hash` value does not appear in any log line — grep confirms
- [ ] `PASSKEY_HMAC_SECRET` value does not appear in any log line — grep confirms
- [ ] After payment webhook confirms sale: `passkey_invalidated = TRUE`, `passkey_invalidated_at` is set, `is_available = FALSE`, `sold_at` is set — all in same DB commit
- [ ] `SELECT * FROM listings WHERE passkey_invalidated = TRUE AND is_available = TRUE` returns 0 rows after a complete sale

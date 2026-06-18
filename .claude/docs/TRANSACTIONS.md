# TRANSACTIONS.md — Passkey Verification, Completion & Reputation

The platform processes **no payments**. Buyers and sellers settle money directly,
offline, at the in-person meetup. A buyer-entered 8-digit passkey is the **sole**
mechanism that confirms a completed transaction and drives all reputation metrics.

There is no Razorpay, no payout, no escrow, no seller onboarding/KYC, no payment
webhook, no payment window, and no abandonment job. None.

---

## Flow

1. Buyer contacts the seller from a listing (in-app chat).
2. They communicate and meet in person.
3. After inspecting the material and exchanging the book, the seller shares the
   listing's unique 8-digit transaction code (the passkey).
4. The buyer enters the code in the app (`POST /transactions/verify-passkey`).
5. If the code is correct, atomically:
   - the listing becomes **SOLD** (`is_available=FALSE`, `sold_at=now()`,
     `passkey_invalidated=TRUE`) and drops out of active marketplace results,
   - the seller's `books_sold` increments by 1,
   - the buyer's `books_bought` increments by 1,
   - the seller's `is_verified` flips TRUE if `books_sold` reaches 10,
   - the buyer is prompted to rate the seller.
6. The buyer may submit a rating (1–5 stars, optional review) — once.
7. The seller's `seller_rating` average is recomputed from their verified ratings.

---

## Passkey

- 8-digit numeric, generated at listing creation: `str(secrets.randbelow(100_000_000)).zfill(8)`.
- Stored as `passkey_hash` = HMAC-SHA256(`PASSKEY_HMAC_SECRET`, `passkey + listing_id`).
  Plaintext is shown to the seller once at creation and never persisted.
- Verified with `hmac.compare_digest` — never `==`.
- Regenerable by the owner (`PATCH /listings/{id}/passkey`) while the listing is unsold.
- Never logged, never returned once the listing is sold.

### Verify check order (`POST /transactions/verify-passkey`)

Stop on first failure:
1. Listing exists, not sold (`passkey_invalidated=FALSE`), not paused (`is_available=TRUE`).
2. Buyer is not the seller (cannot complete your own listing).
3. Buyer not blocked — Redis `passkey_attempts:{listing_id}:{buyer_id}` < 3.
4. Passkey hash matches.

On a wrong code: increment the Redis counter (TTL 7 days). At 3 attempts the buyer is
blocked from that listing for 7 days. A correct code does NOT reset the counter.

### Completion is atomic and one-way

```sql
UPDATE listings
SET is_available = FALSE, sold_at = now(),
    passkey_invalidated = TRUE, passkey_invalidated_at = now()
WHERE id = :id AND is_available = TRUE AND passkey_invalidated = FALSE
RETURNING id;
```

If no row is returned, the listing was already sold → `409`. This selects the single
winning buyer; a sold listing can never be reopened. The `transactions` row and the
counter increments happen in the same DB transaction.

---

## Ratings & reputation

- `POST /transactions/{id}/rating` — buyer only, once per transaction (enforced by
  `UNIQUE(transaction_id, rated_by)`). Body: `rating` (1–5), `review` (optional text).
- Only ratings from verified transactions can exist, because a transaction row only
  exists after a verified passkey — so all reputation comes from verified exchanges.
- After insert, recompute `public.users.seller_rating = AVG(rating)` for that seller.
- **Seller profile** shows: average rating, total books sold, total verified
  transactions (== `books_sold`).
- **Buyer profile** shows: total books bought (`books_bought`).
- **Verification badge** (`is_verified`): blue badge, auto-set TRUE once `books_sold`
  reaches 10. No manual step; appears as soon as the threshold is crossed.

---

## Notifications

- Sale complete: after a verified passkey, a `BackgroundTask` resolves the seller's
  email (`fetch_user_email`, service role) and sends a "your listing has been sold"
  email — no amount, since no money flows through the platform.

---

## What does NOT exist

No payment of any kind · no Razorpay · no payout/Route · no seller KYC/onboarding ·
no payment webhook · no `initiated`/`released`/`cancelled` statuses · no amount/payout
columns · no payment window or expiry · no abandonment APScheduler job · no refunds ·
no escrow · no buyer ratings (only buyer-rates-seller).

# Spec Review: 09-payment

## Verdict
BLOCKED

One or more blockers present. Do not start implementation until they are resolved.

---

## Blockers

### B1 — Passkey regeneration endpoint conflicts with Spec 08
**Location:** "Passkey regeneration" section
**Issue:** Spec 09 defines the regeneration endpoint as `POST /listings/{listing_id}/regenerate-passkey` and blocks regeneration when `not listing.is_available`. Spec 08 defines it as `PATCH /listings/{id}/passkey` and blocks only when `listing.passkey_invalidated = TRUE`. The guard conditions are semantically different: a paused listing has `is_available=FALSE` and `passkey_invalidated=FALSE` — Spec 09 blocks regeneration for paused listings, Spec 08 allows it. A developer implementing both specs gets a conflict in endpoint path, HTTP method, and gate condition.
**Conflicts with:** `08-passkey.md` — `"PATCH /listings/{id}/passkey"` and `"if listing.passkey_invalidated: raise HTTPException(400, 'Cannot regenerate passkey on a sold listing.')"` and `"Sold listings: Returns 400 if passkey_invalidated = TRUE. The UI hides the regenerate button on sold listings"`.
**Fix:** Delete the regeneration section from Spec 09 entirely. Spec 08 already fully defines this endpoint — reference it rather than redefining it. If the gate condition in Spec 08 needs changing, fix it there.

---

### B2 — Self-purchase check absent from verify-passkey implementation
**Location:** "POST /payments/verify-passkey" section, Check 1
**Issue:** Spec 09's `verify_passkey_and_initiate` has three checks (availability, Redis block, hash). Spec 08 defines a mandatory Check 1b between availability and Redis: `if str(listing.seller_id) == buyer_id: raise HTTPException(403, "You cannot purchase your own listing.")`. Spec 09 omits this guard entirely. A seller can submit their own passkey and generate a payment link against their own listing.
**Conflicts with:** `08-passkey.md` — `"Check 1b — buyer cannot purchase their own listing"` and `"POST /payments/verify-passkey returns 403 with 'You cannot purchase your own listing.' when caller is the listing's seller"` (DoD item).
**Fix:** Add Check 1b between the availability check and the Redis block check, as defined in Spec 08.

---

### B3 — `transaction.seller_email` attribute does not exist
**Location:** "Email notifications" section — `send_sale_complete` and `send_abandoned_checkout_email` functions
**Issue:** Both email functions access `transaction.seller_email`. The `Transaction` model (Spec 06) has no `seller_email` column. `public.users` has no `email` column — AUTH.md states "No email, no password_hash, no phone — Supabase Auth owns identity. Email available via payload['email'] from JWT when needed in backend." The notification call would raise `AttributeError` at runtime. The spec acknowledges the problem in a trailing comment ("Seller email is fetched from payload['email'] via JWT or joined from auth.users") but the actual code shown uses the nonexistent attribute.
**Conflicts with:** `SCHEMA.md` — `"No email, no password_hash, no phone — Supabase Auth owns identity"` on `public.users`; `06-schema.md` User model which has no email column.
**Fix:** Specify the concrete resolution. APScheduler jobs have no JWT — they must use a Supabase service-role query against `auth.users` (`SELECT email FROM auth.users WHERE id = seller_id`). The notification functions must accept `seller_email: str` as a separate argument that the caller resolves before calling. Show this in both the job code and the webhook handler.

---

### B4 — Onboarding flow contradicts its own code: account ID saved before KYC completes
**Location:** "Seller onboarding — Razorpay Route" section, "Razorpay Route onboarding flow" prose vs. code in `POST /payments/onboard`
**Issue:** The prose flow states: "On completion, Razorpay webhook (account.activated) fires → Backend saves razorpay_account_id to users table." This implies the gate is set only after KYC completes. But the code in `POST /payments/onboard` saves `seller.razorpay_account_id = account["id"]` immediately — before the seller has completed KYC. Under this implementation a seller can create listings the moment they click "Connect Payment Account", before Razorpay has verified their identity. Additionally, no webhook handler for `account.activated` is specified anywhere in the spec, so the prose flow is dead code.
**Conflicts with:** Same section — prose says save on webhook, code saves immediately.
**Fix:** Choose one approach and implement it consistently. Option A (simpler): save `razorpay_account_id` immediately on account creation and treat any Razorpay-issued account ID as sufficient. Remove the `account.activated` prose. Option B (stricter): save `razorpay_account_id` only in an `account.activated` webhook handler; the onboard endpoint returns only the KYC URL and saves nothing; the gate check looks for `razorpay_account_id IS NOT NULL`. If Option B, add the webhook handler for `account.activated` to the spec.

---

## Minor gaps

### M1 — `router` undefined in CreateListingButton
**Location:** "Seller onboarding — Razorpay Route", `CreateListingButton.jsx` code
**Issue:** `onClick={() => router.push('/listings/new')}` uses `router` but the component imports nothing from `next/navigation`. No `useRouter()` call exists in the component.
**Fix:** Add `import { useRouter } from 'next/navigation'` and `const router = useRouter()` inside the component.

---

### M2 — `listing.seller_id != seller_id` type mismatch in regenerate_passkey
**Location:** "Passkey regeneration" section, `regenerate_passkey` function
**Issue:** `if not listing or listing.seller_id != seller_id:` — `listing.seller_id` is a Python `UUID` object (from SQLAlchemy), `seller_id` is a `str` from `user["sub"]`. The comparison will always evaluate as not-equal, meaning the 403 fires for every caller including the actual owner. Spec 08 correctly writes `str(listing.seller_id) != user["sub"]`.
**Conflicts with:** `08-passkey.md` — `"if str(listing.seller_id) != user['sub']: raise HTTPException(403, 'Not your listing.')"`.
**Fix:** Use `str(listing.seller_id) != seller_id` to match the string type from the JWT.

---

### M3 — Paused-listing error message differs from Spec 08
**Location:** "POST /payments/verify-passkey", Check 1
**Issue:** Spec 09 collapses both `passkey_invalidated=TRUE` (sold) and `is_available=FALSE` (paused/suspended) into a single 400 `"This listing has already been sold."`. Spec 08 distinguishes them: sold → 400 `"This listing has already been sold."`, paused → 400 `"This listing is temporarily unavailable."`. The merged message is factually wrong for paused listings.
**Conflicts with:** `08-passkey.md` — DoD item `"POST /payments/verify-passkey returns 400 with 'This listing is temporarily unavailable.' if listing.is_available = FALSE and passkey_invalidated = FALSE"`.
**Fix:** Split into two separate checks matching Spec 08's error messages.

---

### M4 — verify-passkey implementation duplicated across Spec 08 and Spec 09
**Location:** "POST /payments/verify-passkey" section
**Issue:** Spec 08 defines the full endpoint including all three checks and delegates to `payment_service.initiate_payment`. Spec 09 redefines the same endpoint inline with the payment initiation code merged in. A developer reading both specs sees two different canonical implementations in two different files and must pick one.
**Fix:** Spec 09 should not reproduce the passkey validation checks. Instead, reference Spec 08 for checks 1–3 and define only the payment-initiation logic (idempotency, row lock, transaction creation, Razorpay link) in `payment_service.initiate_payment`. Show only that service function here.

---

### M5 — `POST /payments/onboard` and `GET /transactions/{id}/status` absent from CLAUDE.md API table
**Location:** "Scope" section (implicit)
**Issue:** CLAUDE.md's API endpoints table does not include `POST /payments/onboard` or `GET /transactions/{id}/status`. Both are new protected endpoints introduced by this spec.
**Fix:** Add both to "Files to modify" with instruction to update the API endpoints table in CLAUDE.md.

---

### M6 — DoD does not verify KYC gate behaviour
**Location:** "Definition of done"
**Issue:** The DoD checks that a seller without `razorpay_account_id` receives 403 on `POST /listings`, but does not address what happens if the onboarding endpoint saves the ID before KYC completes (see B4). If the ID is saved immediately, the DoD item passes even when the seller hasn't finished KYC.
**Fix:** After resolving B4, add a DoD item that tests the specific gate condition chosen (either "ID present = sufficient" or "ID present only after account.activated webhook").

---

## Security check

| # | Rule | Status | Note |
|---|------|--------|------|
| 1 | Seller contact info never exposed | ✓ | Transaction and status responses contain only UUIDs and amounts |
| 2 | Razorpay webhook HMAC verified | ✓ | Step 1 of webhook handler calls `verify_webhook_signature` before any processing |
| 3 | Unrecognised webhook events return 200 | ✓ | Step 2 returns 200 for non-`payment_link.paid` events; all other branches also return 200 |
| 4 | Supabase session in httpOnly cookies | — | Not applicable — this spec has no session management code |
| 5 | Ownership validated before mutations | ✓ | Passkey regeneration checks `listing.seller_id == user["sub"]`; `GET /transactions/{id}/status` checks `buyer_id`; note B2 (self-purchase missing from verify-passkey) |
| 6 | Images direct to Cloudinary | — | Not applicable — no image handling in this spec |
| 7 | Parameterized queries only | ✓ | All queries use SQLAlchemy ORM; `description` field uses f-string in Razorpay call (not a SQL query — acceptable) |
| 8 | CORS restricted to FRONTEND_URL | — | Not applicable — CORS is a global FastAPI config concern |
| 9 | SERVICE_ROLE_KEY in background jobs only | ✓ | APScheduler uses `AsyncSessionLocal` directly; no service role key in request handlers |
| 10 | PASSKEY_HMAC_SECRET never logged | ✓ | No log statement references the secret; spec explicitly calls this out in security section |
| 11 | hmac.compare_digest for comparisons | ✓ | Delegated to `verify_passkey` in `security.py` which is defined in AUTH.md with `hmac.compare_digest` |
| 12 | Cancelled transactions never reopened | ✓ | Late webhooks refund and return 200; Step 6 never sets status back to initiated |
| 13 | Piracy reports hide listing immediately | — | Not applicable — moderation is manual via Supabase dashboard, not part of this spec |

---

## Duplication check

- **"POST /payments/verify-passkey" section** — The full endpoint including all three passkey checks is defined in both `08-passkey.md` (as a complete endpoint with `payment_service.initiate_payment` delegation) and this spec (inline, merged with payment initiation). The two implementations diverge on: self-purchase check (B2), error messages for paused listings (M3), and code structure (delegation vs inline). Recommend Spec 09 references Spec 08 for checks 1–3 and defines only `payment_service.initiate_payment`.
- **"Passkey regeneration" section** — Fully defined in `08-passkey.md` as `PATCH /listings/{id}/passkey`. Spec 09 redefines it with a different method and path. See B1.
- **"Passkey lifecycle" table** — Identical to the lifecycle table in `08-passkey.md` and `PAYMENT.md`. Reference rather than reproduce.

---

## Definition of done check

- `"POST /payments/verify-passkey returns 400 after 3 wrong attempts; 4th attempt returns 403 without running hash comparison"` — The condition is inverted: the 3rd attempt triggers the block (count reaches 3 → 403), not the 4th. Spec 08's DoD is more precise: "returns 403 with 'You have been blocked...' on third wrong attempt".
- `"Concurrent payment scenario: second webhook results in refund; listing remains is_available = FALSE"` — Testable but requires two concurrent HTTP calls in the test. Acceptable but worth noting that this requires a specific integration test, not just running the app.
- No DoD item covers `POST /payments/onboard` success path (onboarding URL returned, account created in Razorpay).
- No DoD item covers what the buyer status page shows while `isLoading = true` on first render before data arrives.

---

## Implementation readiness

1. **How is seller email fetched for APScheduler notifications?** The job runs without a request context and therefore has no JWT. `public.users` has no email column. Is a Supabase service-role query against `auth.users` acceptable here, or should the Transaction row store seller email at initiation time? This must be answered before `notification_service.py` can be written. (BLOCKER — B3)

2. **When exactly is `razorpay_account_id` set?** Immediately on account creation (before KYC), or only after `account.activated` fires? These require different code paths. (BLOCKER — B4)

3. **Does `payment_link.create()` need a `transfers` field to route funds to the seller via Razorpay Route?** The spec and PAYMENT.md both omit this field. Razorpay Route's linked account auto-split may be configured at the Route dashboard level, but if code-level `transfers` is required, the payment link call is incomplete.

---

## Summary

The spec covers the payment flow thoroughly and the webhook handler is correct and complete. The two blockers that will cause runtime failures are: `transaction.seller_email` being accessed on a model that has no such attribute (B3), and the passkey regeneration endpoint conflicting with Spec 08 in both path and guard condition (B1). The self-purchase omission (B2) is a security gap. The onboarding flow contradiction (B4) will produce a gate that doesn't actually gate. Fix B1–B4 before implementation begins.

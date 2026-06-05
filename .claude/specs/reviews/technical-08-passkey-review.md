# Spec Review: 08-passkey

## Verdict
NEEDS FIXES

No blockers. Seven minor gaps spanning completeness, consistency with Spec 02, and code correctness. Safe to fix quickly before implementation.

---

## Blockers
No blockers.

---

## Minor gaps

### M1 — `payment_service` used but never imported in verify-passkey endpoint
**Location:** "POST /payments/verify-passkey" → Endpoint code block
**Issue:** The endpoint ends with `return await payment_service.initiate_payment(db, redis, listing, buyer_id)` but `payment_service` is not imported anywhere in the code block. A developer implementing this file as written would get a `NameError` at runtime.
**Fix:** Add `from app.services import payment_service` (or equivalent) to the imports block, or replace the call with an inline comment: `# → proceed to payment initiation as defined in PAYMENT.md`.

---

### M2 — `uuid` not imported in `regenerate_passkey` code block
**Location:** "Passkey Regeneration" → Endpoint code block
**Issue:** The function signature is `async def regenerate_passkey(listing_id: uuid.UUID, ...)` but `uuid` is not in the import block shown for that file. The existing imports are `APIRouter, Depends, HTTPException, AsyncSession, get_db, verify_token, Listing, generate_passkey, hash_passkey, logging`.
**Fix:** Add `import uuid` to the import block in that code snippet.

---

### M3 — Regeneration resets `passkey_invalidated` but Spec 02 hides the button when it's TRUE
**Location:** "Passkey Regeneration" → prose paragraph; conflicts with Spec 02 "Listing management"
**Issue:** Spec 02 states regeneration is "Available only while `passkey_invalidated = FALSE`" — the UI hides the button on sold listings. Spec 08 adds `listing.passkey_invalidated = False` on regeneration as an "error recovery" path. These two are inconsistent: if the UI never shows the button when `passkey_invalidated=TRUE`, the backend reset is dead code. If the reset is intentional (e.g. via direct API call), Spec 02's guarantee breaks.
**Conflicts with:** `.claude/specs/product/02-user-flows.md` — "Regenerate passkey — Available only while `passkey_invalidated = FALSE`"
**Fix:** Either (a) remove the `passkey_invalidated = False` reset from regeneration and add a guard that raises 403 if the listing is already sold (consistent with Spec 02), or (b) update Spec 02 to permit regeneration on sold listings and explain why. Option (a) is safer and consistent with PAYMENT.md's lifecycle table which shows sold listings keep `passkey_invalidated = TRUE`.

---

### M4 — Check 1 error message misleads buyers when listing is paused, not sold
**Location:** "POST /payments/verify-passkey" → Check 1 code block
**Issue:** When a listing is paused (`is_available=FALSE, sold_at=NULL, passkey_invalidated=FALSE`), Check 1 returns 400 with "This listing has already been sold." The listing has not been sold — it is temporarily paused. Spec 02 shows distinct states ("This listing is temporarily unavailable." for paused vs "This listing has been sold." for sold).
**Fix:** Split Check 1 into two conditions:
```python
if not listing:
    raise HTTPException(404, "Listing not found.")
if listing.passkey_invalidated:
    raise HTTPException(400, "This listing has already been sold.")
if not listing.is_available:
    raise HTTPException(400, "This listing is temporarily unavailable.")
```

---

### M5 — No self-purchase guard in `POST /payments/verify-passkey`
**Location:** "POST /payments/verify-passkey" → Endpoint code block
**Issue:** Spec 02 "Edge Cases" explicitly requires: "Backend rejects if attempted anyway: 403 'You cannot purchase your own listing.'" The verify-passkey endpoint does not include a check that `buyer_id != listing.seller_id`. A seller who knows their own passkey could initiate a payment link against their own listing.
**Conflicts with:** `.claude/specs/product/02-user-flows.md` — "Backend rejects if attempted anyway: 403 'You cannot purchase your own listing.'"
**Fix:** Add after Check 1:
```python
if str(listing.seller_id) == buyer_id:
    raise HTTPException(403, "You cannot purchase your own listing.")
```

---

### M6 — `VerifyPasskeyResponse` Pydantic schema not defined
**Location:** "POST /listings Response Schema" section; "Files to create" — `backend/app/schemas/payment.py`
**Issue:** `VerifyPasskeyRequest` is fully defined. The response shape `{"payment_link_url": "..."}` is only described in prose and in the frontend `onSuccess` handler (`res.data.payment_link_url`). No Pydantic `VerifyPasskeyResponse` class appears in the spec or in the schemas file list. Without it, FastAPI will return an untyped dict and the response won't be documented in OpenAPI.
**Fix:** Add to `backend/app/schemas/payment.py`:
```python
class VerifyPasskeyResponse(BaseModel):
    payment_link_url: str
```
And annotate the endpoint: `async def verify_passkey_endpoint(...) -> VerifyPasskeyResponse`.

---

### M7 — `PATCH /listings/{id}/passkey` missing from CLAUDE.md API endpoint table
**Location:** "Passkey Regeneration" → Endpoint definition
**Issue:** CLAUDE.md lists the canonical API surface. `PATCH /listings/{id}/passkey` does not appear there. This is a new endpoint introduced by this spec that is undocumented at the project level.
**Conflicts with:** `.claude/CLAUDE.md` API endpoints table — the table shows only `PATCH /listings/{id}` for the listings resource with no sub-resource endpoints.
**Fix:** Add `PATCH /listings/{id}/passkey` to the CLAUDE.md API table with annotation "protected, owner only — regenerates passkey hash", or note in this spec that CLAUDE.md should be updated as part of implementation.

---

## Security check

| # | Rule | Status | Note |
|---|------|--------|------|
| 1 | Seller contact info never exposed | ✓ | Passkey responses contain no contact fields; explicitly called out |
| 2 | Razorpay webhook HMAC verified | — | Webhook handler is in PAYMENT.md scope, not this spec |
| 3 | Unrecognised webhook events return 200 | — | Not applicable to this spec |
| 4 | Supabase session in httpOnly cookies | — | Not applicable to this spec |
| 5 | Ownership validated before mutations | ✓ | `PATCH /listings/{id}/passkey` checks `listing.seller_id == user["sub"]` |
| 6 | Images direct to Cloudinary | — | Not applicable to this spec |
| 7 | Parameterized queries only | ✓ | All DB access via SQLAlchemy ORM |
| 8 | CORS restricted to FRONTEND_URL | — | Not applicable to this spec |
| 9 | SERVICE_ROLE_KEY in background jobs only | — | Not applicable to this spec |
| 10 | PASSKEY_HMAC_SECRET never logged | ✓ | Logging requirements table explicitly prohibits it; security section reinforces |
| 11 | hmac.compare_digest for comparisons | ✓ | `verify_passkey` uses it; spec prohibits `==` |
| 12 | Cancelled transactions never reopened | ✓ | Acknowledged in security considerations; regeneration does not touch transactions |
| 13 | Piracy reports hide listing immediately | — | Not applicable to this spec |

---

## Duplication check

The following content in Spec 08 is already fully defined in canonical source files. Duplication is low-risk but creates drift risk if sources are updated:

- **"Passkey Hashing" section** — The `hash_passkey` and `verify_passkey` functions are reproduced verbatim from `.claude/docs/AUTH.md`. AUTH.md already carries the "do not rewrite" instruction. Recommend replacing with a one-line reference: "See AUTH.md — canonical implementation. Do not copy here."
- **"Passkey Invalidation" code block (webhook Step 8)** — The UPDATE statement is reproduced verbatim from `.claude/docs/PAYMENT.md`. Spec 08 says "This is the only place `passkey_invalidated` is set to TRUE" which is correct, but the code itself lives in PAYMENT.md. Recommend referencing PAYMENT.md instead of repeating.
- **Three-check validation logic** — Check 1/2/3 code reproduced from `.claude/docs/PAYMENT.md` "Passkey validation" section. Minor drift risk.

---

## Definition of done check

All 25 DoD items are specific and verifiable. Two observations:

- Item: "Passkey verification INFO logged on success — verify in backend logs" — acceptable, but specify *what* the log message contains so two developers agree: `"Passkey verified: listing=<uuid> buyer=<uuid>"`.
- Missing item: no DoD entry covering the self-purchase guard (M5 above) — "POST /payments/verify-passkey returns 403 'You cannot purchase your own listing.' when caller is the listing's seller."

---

## Implementation readiness

1. **Where is `PasskeyDisplay` rendered after listing creation?** The spec says "shown once on the listing creation success screen" but does not specify which page/component hosts it or how the passkey is passed from the create mutation response to this component. The developer must infer this — likely the `/listings/new` page after a successful `useMutation`, but the spec should state it explicitly.

2. **`payment_service.initiate_payment` signature** — The endpoint calls `payment_service.initiate_payment(db, redis, listing, buyer_id)`. The full implementation of this function is in PAYMENT.md but its exact Python signature is not stated. Developer must reconcile Spec 08's call site with PAYMENT.md's inline payment initiation code. Low friction but worth noting.

3. **Razorpay Route onboarding check in `POST /listings`** — Spec 02 says backend returns 403 if seller hasn't completed Razorpay onboarding. The `create_listing` service in this spec doesn't include that guard. It may be deferred to a payments/listing spec, but the developer implementing `create_listing` from Spec 08 alone would miss it.

---

## Summary

The spec is thorough, well-structured, and correctly grounded in PAYMENT.md and AUTH.md. All three ordered passkey checks are present and in correct sequence. The passkey lifecycle table, logging rules, and security considerations are complete. The main issues to fix before implementation: add the self-purchase guard to `POST /payments/verify-passkey` (M5, required by Spec 02), fix the misleading "already sold" error for paused listings (M4), resolve the regeneration/`passkey_invalidated` reset inconsistency with Spec 02 (M3), and add the missing `VerifyPasskeyResponse` schema (M6). None of these are blockers but M3 and M5 touch correctness of a protected endpoint.

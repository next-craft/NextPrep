# Spec Review: 13-api

## Verdict
NEEDS FIXES

No hard blockers that prevent implementation from starting, but two correctness errors that would produce broken runtime behaviour if implemented as written, plus several minor gaps.

---

## Blockers
No blockers.

---

## Minor gaps

### M1 — DELETE /listings/{id} sets `sold_at` instead of `deleted_at`
**Location:** "DELETE /listings/{id}"
**Issue:** The description reads: "Sets `is_available = FALSE` and `sold_at = now()` on the listing." This is wrong. Spec 06 defines a separate `deleted_at` column for soft-deletes. The correct action is `is_available=FALSE, deleted_at=now(), sold_at stays NULL`. Setting `sold_at` on a delete would put the listing in the "sold" state (not "deleted"), break the listing state breakdown query, and could violate the `sold_xor_deleted` CHECK constraint if a sale had previously occurred.
**Conflicts with:** `06-schema.md` — "deleted → `is_available=FALSE, sold_at=NULL, deleted_at=<timestamp>`" and `CheckConstraint("NOT (sold_at IS NOT NULL AND deleted_at IS NOT NULL)", name='sold_xor_deleted')`.
**Fix:** Change the description to "Sets `is_available = FALSE` and `deleted_at = now()` on the listing. `sold_at` is not set." Also update the DoD item: "`DELETE /listings/{id}` sets `deleted_at` (not `sold_at`) in DB; `SELECT * FROM listings WHERE id='<id>'` shows `deleted_at IS NOT NULL, sold_at IS NULL`."

---

### M2 — POST /payments/verify-passkey missing 404 error for listing not found
**Location:** "POST /payments/verify-passkey", Errors table
**Issue:** The errors table starts at 400 for a sold/unavailable listing but skips 404. Spec 08 explicitly raises 404 as the first check: `if not listing: raise HTTPException(404, "Listing not found.")`. This is the first code path hit when the UUID does not exist in the DB.
**Conflicts with:** `08-passkey.md` — `"if not listing: raise HTTPException(404, 'Listing not found.')"`.
**Fix:** Add a row to the error table: `| 404 | Listing UUID not found | "Listing not found." |` as the first entry.

---

### M3 — `deleted_at` missing from "Fields never returned" table
**Location:** "Fields never returned in any response"
**Issue:** Spec 06 defines a `deleted_at` column on `listings`. It is not in the "Fields never returned" table. Any response that serialises the listing ORM object naively would expose this column.
**Fix:** Add a row: `| deleted_at | listings | Internal soft-delete timestamp — not needed by clients |`.

---

### M4 — `original_price` shown as non-nullable in response examples
**Location:** GET /listings response, GET /listings/{id} response, POST /listings response
**Issue:** `"original_price": 600` in the JSON examples implies the field is always present. Spec 06 defines it as `INTEGER` (no `NOT NULL`), so it is nullable. A frontend developer reading only this spec would not write a null-guard.
**Fix:** Change the example to `"original_price": 600` with a note `"original_price": 600,  // nullable — omit or null if not set` or add a table row clarifying nullability, consistent with how `description` and `subject` are already annotated as `"string | null"`.

---

### M5 — "Fields never returned" table is inaccurate for `razorpay_account_id`
**Location:** "Fields never returned in any response", row for `razorpay_account_id`
**Issue:** The table header says "Fields never returned in any response" but `razorpay_account_id` IS returned in `GET /users/me`. The inline note "Only returned in GET /users/me" contradicts the table header. This will confuse a developer reading the table header only.
**Fix:** Remove `razorpay_account_id` from this table (it is returned). Instead, add a note under `GET /users/{id}` that `razorpay_account_id` is excluded from the public profile response but is present in `GET /users/me`.

---

### M6 — POST /conversations response code "200 or 201" is ambiguous
**Location:** "POST /conversations", Response section
**Issue:** The spec says "Response: 200 or 201" without specifying which code maps to which case (existing vs. new). A developer implementing or testing this endpoint needs one deterministic code. Spec 10 (`chat.md`) does not resolve this either.
**Fix:** Pick one: use `200` for both cases (idempotent endpoint convention), or `201` for new and `200` for existing — and state it explicitly. Recommended: return `200` for both (simplest, matches idempotency convention used for Razorpay `verify-passkey`).

---

### M7 — `GET /conversations` response missing `first_message_notified` suppression note
**Location:** "GET /conversations", Response section
**Issue:** `first_message_notified` is in the "Fields never returned" table but the GET /conversations response schema does not explicitly list which fields are returned. A developer serialising the ORM object must know to exclude this column. The other conversation-related endpoint specs (Spec 10) show `ConversationOut` explicitly excludes it via the Pydantic schema, but this spec doesn't make that clear.
**Fix:** Minor — add `"first_message_notified"` to the fields-never-returned note directly in the GET /conversations section, or note that `ConversationOut` (defined in Spec 10) does not include it.

---

### M8 — DoD does not verify `deleted_at` column behaviour
**Location:** "Definition of done"
**Issue:** The DoD checks `DELETE /listings/{id}` sets `is_available=FALSE` but does not verify the correct column (`deleted_at`) is set. Because of M1, this item would pass even with the wrong implementation (using `sold_at`).
**Fix:** After fixing M1, update the DoD item to: "`DELETE /listings/{id}` sets `deleted_at=now()` in DB; `sold_at` remains NULL; running the state breakdown debug query from Spec 06 counts the listing under 'deleted', not 'sold'."

---

## Security check

| # | Rule | Status | Note |
|---|------|--------|------|
| 1 | Seller contact info never exposed | ✓ | MessageOut contains no PII fields; contacts table omitted from all responses |
| 2 | Razorpay webhook HMAC verified | ✓ | Documented in webhook lifecycle; invalid sig → 400 |
| 3 | Unrecognised webhook events return 200 | ✓ | Explicitly stated in webhook section |
| 4 | Supabase session in httpOnly cookies | ✓ | Noted in Auth header section |
| 5 | Ownership validated before mutations | ✓ | Stated for all owner-only endpoints |
| 6 | Images direct to Cloudinary | ✓ | `images` field is Cloudinary URLs; spec notes FastAPI never receives bytes |
| 7 | Parameterized queries only | ✓ | Stated in Security considerations |
| 8 | CORS restricted to FRONTEND_URL | ✓ | Stated in Global conventions |
| 9 | SERVICE_ROLE_KEY in background jobs only | ✓ | Stated correctly; webhook handler caveat noted consistent with Spec 09 |
| 10 | PASSKEY_HMAC_SECRET never logged | ✓ | Stated in Security considerations |
| 11 | hmac.compare_digest for comparisons | ✓ | Stated in Security considerations |
| 12 | Cancelled transactions never reopened | ✓ | Stated in Security considerations |
| 13 | Piracy reports hide listing immediately | ✓ | Noted as manual moderation via Supabase dashboard |

---

## Duplication check

The following content in this spec is already fully defined elsewhere. As a reference spec this is intentional, but developers should treat the originating spec as authoritative if they diverge:

- Webhook lifecycle steps 1–9 are reproduced verbatim from `PAYMENT.md` and `09-payment.md`. If either source changes, this spec will drift.
- Redis key table is a verbatim copy of the canonical constants in `CLAUDE.md`. Same drift risk.
- APScheduler job description duplicates `09-payment.md` "APScheduler — cancel abandoned transactions" section.

No action required — duplication is acceptable in a reference API spec. Flag if either source spec changes.

---

## Definition of done check

Most DoD items are specific and testable. Issues:

- Item for `DELETE /listings/{id}` will pass even with wrong `sold_at` behaviour (see M1/M8).
- No item verifies that `POST /payments/verify-passkey` returns 404 for a non-existent listing UUID (see M2).
- No item verifies that `original_price` can be null in listing responses (see M4).

---

## Implementation readiness

Two questions would arise immediately:

1. **DELETE endpoint:** "Do I set `sold_at` or `deleted_at`?" — answered by fixing M1.
2. **POST /conversations:** "Which status code do I return for an existing vs new conversation?" — answered by fixing M6.

All other endpoints have sufficient detail to implement without ambiguity.

---

## Summary

The spec is comprehensive and well-structured — every endpoint is documented with auth requirements, request shapes, response shapes, and error codes. Two correctness errors would produce broken runtime behaviour: the soft-delete endpoint incorrectly sets `sold_at` instead of `deleted_at` (violating a DB CHECK constraint), and `POST /payments/verify-passkey` is missing the 404 path for a non-existent listing. Fix those two and the minor gaps before implementation begins. The security coverage is complete.

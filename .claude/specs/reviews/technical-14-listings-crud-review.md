# Spec Review: 14-listings-crud

## Verdict
NEEDS FIXES

No blockers. Six minor gaps — two in critical sections (frontend state detection, missing service file).

---

## Blockers
No blockers.

---

## Minor gaps

### M1 — `sold_at` used in frontend but not in `ListingOut`
**Location:** "`/listings/[id]` — SSR listing detail" (line 587) and "Pydantic schemas / `ListingOut`" (lines 227–244)
**Issue:** The frontend does `const isSold = listing.sold_at !== null` to render the "This listing has been sold." banner. But `sold_at` is absent from `ListingOut`. The API will never return it. `listing.sold_at` will always be `undefined`, so `isSold` is always `false`. Sold listings will silently show the "temporarily unavailable" banner instead of the "sold" banner.
**Conflicts with:** Spec 13 (api.md) — "Fields never returned: `sold_at` — Internal — `is_available=FALSE` is enough for clients." Also conflicts with the spec's own `ListingOut` schema which does not include `sold_at`.
**Fix:** Add a computed `is_sold: bool` field to `ListingOut`, derived from `sold_at IS NOT NULL` in the serializer, or compute it in the service before returning. Update the frontend to use `listing.is_sold` instead of `listing.sold_at !== null`. Do not add `sold_at` to `ListingOut` — that would violate Spec 13.

---

### M2 — `user_service.get_user_by_id` not defined or included in files to create
**Location:** "Router" (line 434) and "Files to create" (lines 1127–1147)
**Issue:** The `create_listing` router calls `await user_service.get_user_by_id(db, seller_id)` to check `razorpay_account_id`. `user_service` is listed as an import but not defined anywhere in this spec, not in SCHEMA.md, not in the existing codebase under this spec's scope. The "Files to create" list does not include `backend/app/services/user_service.py` or a users router. Without it the router will fail at import time.
**Fix:** Either (a) define `get_user_by_id` inline in this spec with its minimal implementation (one `SELECT` by `id`), or (b) add `backend/app/services/user_service.py` to "Files to create" with the required function signature and body.

---

### M3 — `/listings/{id}/edit` page linked but not in scope
**Location:** "`/listings/[id]` — SSR listing detail" (line 649)
**Issue:** The detail page renders `<a href={`/listings/${listing.id}/edit`}>Edit listing</a>` for the owner. This route (`/listings/[id]/edit`) is not in "Scope", not in "Files to create", and not defined anywhere in the specs. Clicking it will 404.
**Fix:** Either (a) add `/listings/[id]/edit` page to scope and "Files to create" with the edit form implementation, or (b) change the link to point to `/dashboard` where the seller can manage their listings.

---

### M4 — `ListingFilters` imports `useSearchParams` but never calls it
**Location:** "ListingFilters component" (line 908)
**Issue:** `import { useRouter, useSearchParams } from 'next/navigation'` — `useSearchParams` is imported but unused. This is dead code and will trigger a lint warning.
**Fix:** Remove `useSearchParams` from the import.

---

### M5 — "Chat with seller" links to undefined route `/conversations?listing=...`
**Location:** "`/listings/[id]` — SSR listing detail" (line 643)
**Issue:** The detail page renders `<a href={`/conversations?listing=${listing.id}`}>Chat with seller</a>`. No `/conversations` frontend page is defined in any spec. Spec 10 defines the API endpoints but not the frontend page for initiating a conversation from the listing detail page.
**Fix:** Note explicitly that this link is a placeholder and will be fully implemented in the Chat spec (Spec 10 frontend). Change the `href` to match whatever route Spec 10 defines, or mark it as `TODO: update when Spec 10 frontend is implemented` to avoid silently broken links.

---

### M6 — DoD missing: check that sold listings show correct banner (not "unavailable")
**Location:** "Definition of done" (lines 1179–1212)
**Issue:** The DoD has `- [ ] /listings/[id] SSR page shows sold/unavailable banners when sold_at IS NOT NULL or is_available=FALSE` but (per M1) the frontend cannot distinguish sold from paused without `is_sold` in the response. Once M1 is fixed, this DoD item should be split into two separately testable checks: one for sold, one for paused/suspended.
**Fix:** Split into:
- `[ ] /listings/[id]` shows "This listing has been sold." when `is_sold=true`
- `[ ] /listings/[id]` shows "This listing is temporarily unavailable." when `is_available=false` and `is_sold=false`

---

## Security check

| # | Rule | Status | Note |
|---|------|--------|------|
| 1 | Seller contact info never exposed | ✓ | `ListingOut` excludes all contact fields; `passkey_hash` excluded |
| 2 | Razorpay webhook HMAC verified | — | Not applicable — webhooks handled in Spec 09 |
| 3 | Unrecognised webhook events return 200 | — | Not applicable — handled in Spec 09 |
| 4 | Supabase session in httpOnly cookies | ✓ | Frontend uses `createServerSupabaseClient` / `@supabase/ssr`; no localStorage usage |
| 5 | Ownership validated before mutations | ✓ | `str(listing.seller_id) != user["sub"]` check before every PATCH and DELETE |
| 6 | Images direct to Cloudinary | ✓ | `images` field accepts Cloudinary URLs only; FastAPI never receives bytes |
| 7 | Parameterized queries only | ✓ | All queries via SQLAlchemy ORM column methods; no f-string SQL |
| 8 | CORS restricted to FRONTEND_URL | ✓ | Noted in security considerations; enforced at app level |
| 9 | SERVICE_ROLE_KEY in background jobs only | — | Not applicable — this spec uses no service role key |
| 10 | PASSKEY_HMAC_SECRET never logged | ✓ | Passkey plaintext never logged; hash never in responses; `logger.info` only logs listing/seller UUIDs |
| 11 | hmac.compare_digest for comparisons | — | Not applicable — passkey verification handled in Spec 09; this spec only hashes, doesn't compare |
| 12 | Cancelled transactions never reopened | — | Not applicable — transaction lifecycle handled in Spec 09 |
| 13 | Piracy reports hide listing immediately | — | Not applicable — manual moderation via Supabase dashboard; no API endpoint |

---

## Duplication check

- **"Pydantic schemas / `VALID_EXAM_CATEGORIES`"** — The 19 canonical exam categories are also defined in CLAUDE.md and will be duplicated in `frontend/constants/examCategories.js`. This is expected and acceptable — constants must exist on both sides. No action needed.
- **"Database model / SQL block"** — Reproduces the `listings` table from SCHEMA.md. Flagged as intentional per the spec's own note ("Reproduced here for implementation reference"). Minor duplication; acceptable.
- **"Router / complete webhook handler reference"** — The spec correctly out-of-scopes the webhook. No duplication.

No problematic duplication detected.

---

## Definition of done check

- Item `PATCH /listings/{id}` cannot update `exam_category` or `listing_type` (fields absent from schema, ignored or 422)` — "ignored or 422" is ambiguous. Pydantic will silently ignore unknown fields by default (`model_config` does not set `extra = "forbid"`). The DoD should specify which behaviour is expected: silent ignore or 422.
- See M6 above — sold vs. paused banner split needed.
- All other DoD items are specific and verifiable.

---

## Implementation readiness

1. **`user_service.get_user_by_id`** — This function must exist before the listings router can be started. If the users spec hasn't been written yet, the developer needs the minimal function body. (See M2.)
2. **`deleted_at` migration** — The spec correctly says "check first." Developer needs to inspect `alembic/versions/` or the live DB before deciding whether to run the migration. No ambiguity.
3. **`is_sold` field** — Until M1 is fixed, the developer cannot correctly implement the frontend sold-state detection. (See M1.)

Otherwise spec is self-contained.

---

## Summary

The spec is thorough, well-grounded in SCHEMA.md and Spec 13, and covers the full CRUD surface with correct ownership guards, passkey hashing, and soft-delete semantics. The most important fix is M1: `sold_at` is absent from `ListingOut` (correctly, per Spec 13) but the frontend uses it directly, meaning sold listings will never show the "sold" banner — add a computed `is_sold: bool` to `ListingOut`. M2 (missing `user_service`) will cause an import error at startup and must be resolved before implementation begins.

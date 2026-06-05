# Spec 13: API

## Purpose

This spec is the single authoritative reference for every HTTP endpoint exposed by the FastAPI backend of Study Material Exchange India. It documents every route's method, path, authentication requirement, request body shape, response shape, HTTP status codes, and error codes — consolidating information spread across prior specs (auth, schema, passkey, payment, chat) into one queryable document. Developers building the frontend or testing the backend must be able to answer "what does this endpoint accept and return?" from this spec alone, without reading multiple other files. This is a reference document, not an implementation spec — no new code is introduced. Everything documented here must already be derivable from the existing specs; this spec resolves ambiguity and prevents drift.

---

## Depends on

- **Spec 06 — Schema:** all table definitions, column types, constraints
- **Spec 07 — Auth:** `verify_token`, JWKS setup, `user["sub"]` UUID extraction
- **Spec 08 — Passkey:** passkey check sequence, Redis attempt tracking, regeneration endpoint
- **Spec 09 — Payment:** `POST /payments/verify-passkey`, webhook, transaction status, seller onboarding
- **Spec 10 — Chat:** all `/conversations` and `/messages` endpoints

---

## Scope

**In scope:**
- Every endpoint exposed at `http://localhost:8000/v1` (dev) / `https://api.yourdomain.com/v1` (prod)
- Auth requirement for each endpoint (public vs. protected)
- Full request body schema (field names, types, constraints, required/optional)
- Full response body schema (field names, types, always-present vs. nullable)
- All HTTP success codes
- All error codes with their triggering conditions and `detail` message
- CORS policy

**Out of scope:**
- Implementation code (covered in feature specs)
- Alembic migration details (Spec 06)
- Frontend API client setup (AUTH.md)
- Supabase auth endpoints (`/auth/*`) — those go directly to Supabase, never through FastAPI
- Admin panel endpoints — none exist in v1

---

## Global conventions

### Base URLs

| Environment | Base URL |
|---|---|
| Development | `http://localhost:8000/v1` |
| Production | `https://api.yourdomain.com/v1` |

### Auth header

All protected endpoints require:
```
Authorization: Bearer <supabase_access_token>
```

The token is a Supabase-issued ES256 JWT. FastAPI verifies it against the Supabase JWKS endpoint. `user["sub"]` is the caller's UUID and is used as the identity in all DB queries.

No auth endpoints exist on FastAPI. All auth (login, logout, token refresh) goes directly to Supabase.

### CORS

In production, CORS is restricted to `FRONTEND_URL` only. The wildcard `*` is never used.

In development, `FRONTEND_URL=http://localhost:3000`.

### Content type

All request and response bodies are `application/json`.

### Prices

All prices in whole **rupees** (integers). No paise in any request or response. Paise only appear at the Razorpay API boundary internally.

### Timestamps

All timestamps are ISO 8601 UTC strings, e.g. `"2026-06-06T10:30:00.000Z"`.

### Pagination

No pagination in v1. All list endpoints return the full result set.

### Error response shape

All errors follow FastAPI's default shape:
```json
{ "detail": "Human-readable error message." }
```
For validation errors (422), FastAPI returns a structured list:
```json
{
  "detail": [
    { "loc": ["body", "field_name"], "msg": "error message", "type": "value_error" }
  ]
}
```

---

## Listings

### GET /listings

Public. No auth required.

Returns all available listings matching the query filters. Listings where `is_available = FALSE` are excluded.

**Query parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `q` | string | No | Full-text search — ILIKE match against `title` and `description` |
| `exam_category` | string | No | Must match a canonical exam category exactly (case-sensitive) |
| `subject` | string | No | ILIKE match against `subject` |
| `city` | string | No | ILIKE match against `city` |
| `condition` | string | No | Exact match — `A`, `B`, or `C` |
| `listing_type` | string | No | Exact match — `BOOK`, `NOTES`, `MODULE`, or `BUNDLE` |

**Canonical exam categories:**
```
JEE_MAINS | JEE_ADVANCED | NEET_UG | NEET_PG
UPSC_CSE | UPSC_OTHER
CA_FOUNDATION | CA_INTERMEDIATE | CA_FINAL
GATE | GMAT | GRE | IELTS | CUET
CLASS_9 | CLASS_10 | CLASS_11 | CLASS_12
OTHER
```

**Response: 200**
```json
[
  {
    "id": "uuid",
    "seller_id": "uuid",
    "title": "string",
    "description": "string | null",
    "exam_category": "string",
    "subject": "string | null",
    "listing_type": "BOOK | NOTES | MODULE | BUNDLE",
    "condition": "A | B | C",
    "asking_price": 450,
    "original_price": 600,
    "city": "string",
    "images": ["https://res.cloudinary.com/..."],
    "is_available": true,
    "views": 12,
    // original_price is nullable — null or absent when seller did not set it
    "created_at": "2026-06-01T08:00:00.000Z"
  }
]
```

Fields never returned: `passkey_hash`, `passkey_invalidated`, `passkey_invalidated_at`, `sold_at`, `deleted_at`.

**Errors:** None. Always returns 200, even if empty array.

---

### POST /listings

Protected. Requires valid Bearer token.

Creates a new listing. The seller must have a linked Razorpay account (`razorpay_account_id IS NOT NULL`) or the request is rejected. An 8-digit numeric passkey is generated and returned in the response; this is the only time the plaintext passkey is available.

**Request body:**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `title` | string | Yes | Non-empty |
| `description` | string | No | — |
| `exam_category` | string | Yes | Must be a canonical exam category |
| `subject` | string | No | Free text |
| `listing_type` | string | Yes | `BOOK`, `NOTES`, `MODULE`, or `BUNDLE` |
| `condition` | string | Yes | `A`, `B`, or `C` |
| `asking_price` | integer | Yes | Positive whole number (rupees) |
| `original_price` | integer | No | Positive whole number (rupees) |
| `city` | string | Yes | Non-empty |
| `images` | string[] | No | Cloudinary URLs, max 5 |

**Response: 201**
```json
{
  "listing": {
    "id": "uuid",
    "seller_id": "uuid",
    "title": "string",
    "description": "string | null",
    "exam_category": "string",
    "subject": "string | null",
    "listing_type": "BOOK | NOTES | MODULE | BUNDLE",
    "condition": "A | B | C",
    "asking_price": 450,
    "original_price": 600,
    "city": "string",
    "images": [],
    "is_available": true,
    "views": 0,
    "created_at": "2026-06-06T10:00:00.000Z"
  },
  "passkey": "03918472"
}
```

The `passkey` field is a plaintext 8-digit string. It is never stored. It must be shown to the seller immediately. It is not available again after this response.

**Errors:**

| Code | Condition | Detail |
|---|---|---|
| 401 | Missing or invalid token | `"Missing token"` / `"Invalid token"` |
| 403 | Seller has no linked Razorpay account | `"Complete payment setup to start selling."` |
| 422 | Invalid request body | Pydantic validation error |

---

### GET /listings/{id}

Public. No auth required.

Returns a single listing by UUID. Increments `views` counter. Returns the listing even if `is_available = FALSE` — the detail page must handle sold/paused state.

**Path parameters:**

| Parameter | Type | Description |
|---|---|---|
| `id` | UUID | Listing UUID |

**Response: 200**
```json
{
  "id": "uuid",
  "seller_id": "uuid",
  "title": "string",
  "description": "string | null",
  "exam_category": "string",
  "subject": "string | null",
  "listing_type": "BOOK | NOTES | MODULE | BUNDLE",
  "condition": "A | B | C",
  "asking_price": 450,
  "original_price": 600,
  "city": "string",
  "images": ["https://res.cloudinary.com/..."],
  "is_available": true,
  "views": 13,
  "created_at": "2026-06-01T08:00:00.000Z"
}
```
`original_price` is nullable — `null` when the seller did not provide it.
```json
```

Fields never returned: `passkey_hash`, `passkey_invalidated`, `passkey_invalidated_at`, `sold_at`, `deleted_at`.

**Errors:**

| Code | Condition | Detail |
|---|---|---|
| 404 | Listing UUID not found | `"Listing not found."` |

---

### PATCH /listings/{id}

Protected. Owner only.

Updates mutable fields on a listing. Partial update — only supplied fields are changed. `seller_id`, `passkey_hash`, and payment-related fields are not updatable through this endpoint.

**Path parameters:**

| Parameter | Type | Description |
|---|---|---|
| `id` | UUID | Listing UUID |

**Request body (all optional):**

| Field | Type | Constraints |
|---|---|---|
| `title` | string | Non-empty |
| `description` | string | — |
| `exam_category` | string | Must be a canonical exam category |
| `subject` | string | — |
| `listing_type` | string | `BOOK`, `NOTES`, `MODULE`, or `BUNDLE` |
| `condition` | string | `A`, `B`, or `C` |
| `asking_price` | integer | Positive |
| `original_price` | integer | Positive |
| `city` | string | Non-empty |
| `images` | string[] | Cloudinary URLs, max 5 |
| `is_available` | boolean | Seller can pause/unpause listing |

**Response: 200** — updated listing object (same shape as `GET /listings/{id}`)

**Errors:**

| Code | Condition | Detail |
|---|---|---|
| 401 | Missing or invalid token | `"Missing token"` / `"Invalid token"` |
| 403 | Caller is not the listing's seller | `"Not authorised."` |
| 404 | Listing UUID not found | `"Listing not found."` |
| 422 | Invalid field value | Pydantic validation error |

---

### DELETE /listings/{id}

Protected. Owner only. Soft delete.

Sets `is_available = FALSE` and `deleted_at = now()` on the listing. `sold_at` is not set — that column is reserved for webhook-confirmed payments only. The row is never hard-deleted. Conversations associated with the listing survive intact because the listing row is not removed (`ON DELETE SET NULL` on conversation FK never fires; `listing_id` remains populated).

**Path parameters:**

| Parameter | Type | Description |
|---|---|---|
| `id` | UUID | Listing UUID |

**Response: 204** — no body

**Errors:**

| Code | Condition | Detail |
|---|---|---|
| 401 | Missing or invalid token | `"Missing token"` / `"Invalid token"` |
| 403 | Caller is not the listing's seller | `"Not authorised."` |
| 404 | Listing UUID not found | `"Listing not found."` |

---

### PATCH /listings/{id}/passkey

Protected. Owner only.

Regenerates the listing's passkey. Generates a new 8-digit numeric passkey, hashes it, and overwrites the existing `passkey_hash`. The old passkey is invalidated immediately. Returns the new plaintext passkey — the only time it is visible.

Blocked when `listing.passkey_invalidated = TRUE` (listing already sold).

**Path parameters:**

| Parameter | Type | Description |
|---|---|---|
| `id` | UUID | Listing UUID |

**Request body:** None.

**Response: 200**
```json
{
  "passkey": "74920183"
}
```

**Errors:**

| Code | Condition | Detail |
|---|---|---|
| 401 | Missing or invalid token | `"Missing token"` / `"Invalid token"` |
| 403 | Caller is not the listing's seller | `"Not authorised."` |
| 400 | Listing already sold (`passkey_invalidated = TRUE`) | `"Cannot regenerate passkey for a sold listing."` |
| 404 | Listing UUID not found | `"Listing not found."` |

---

## Users

### GET /users/me

Protected. Returns the caller's profile from `public.users`.

**Request body:** None.

**Response: 200**
```json
{
  "id": "uuid",
  "full_name": "string",
  "city": "string | null",
  "avatar_url": "string | null",
  "is_verified": true,
  "seller_rating": 4.5,
  "total_sales": 3,
  "razorpay_account_id": "acc_xxx | null",
  "created_at": "2026-01-15T10:00:00.000Z"
}
```

`razorpay_account_id` presence indicates the seller has completed Razorpay Route onboarding.

**Errors:**

| Code | Condition | Detail |
|---|---|---|
| 401 | Missing or invalid token | `"Missing token"` / `"Invalid token"` |
| 404 | No public.users row for caller (trigger failure) | `"User not found."` |

---

### PATCH /users/me

Protected. Updates the caller's profile.

**Request body (all optional):**

| Field | Type | Constraints |
|---|---|---|
| `full_name` | string | Non-empty |
| `city` | string | — |
| `avatar_url` | string | Cloudinary URL |

**Response: 200** — updated user object (same shape as `GET /users/me`)

**Errors:**

| Code | Condition | Detail |
|---|---|---|
| 401 | Missing or invalid token | `"Missing token"` / `"Invalid token"` |
| 422 | Invalid field value | Pydantic validation error |

---

### GET /users/{id}

Public. No auth required.

Returns a public profile. Does not expose email, `razorpay_account_id`, or any PII beyond what is listed.

**Path parameters:**

| Parameter | Type | Description |
|---|---|---|
| `id` | UUID | User UUID |

**Response: 200**
```json
{
  "id": "uuid",
  "full_name": "string",
  "city": "string | null",
  "avatar_url": "string | null",
  "is_verified": true,
  "seller_rating": 4.5,
  "total_sales": 3,
  "created_at": "2026-01-15T10:00:00.000Z"
}
```

`razorpay_account_id` is never included in the public profile response — it is only returned by `GET /users/me` for the authenticated caller.

**Errors:**

| Code | Condition | Detail |
|---|---|---|
| 404 | User UUID not found | `"User not found."` |

---

## Conversations

### GET /conversations

Protected. Returns all conversations where the caller is the buyer or the seller, ordered by `created_at` descending.

**Request body:** None.

**Response: 200**
```json
[
  {
    "id": "uuid",
    "listing_id": "uuid | null",
    "buyer_id": "uuid",
    "seller_id": "uuid",
    "created_at": "2026-06-01T08:00:00.000Z"
  }
]
```

`listing_id` is nullable — it is `NULL` if the listing was hard-deleted (which never happens in v1; soft delete leaves `listing_id` intact).

**Errors:**

| Code | Condition | Detail |
|---|---|---|
| 401 | Missing or invalid token | `"Missing token"` / `"Invalid token"` |

---

### POST /conversations

Protected. Creates or returns an existing conversation between the caller (as buyer) and the seller of a listing. Idempotent: if a conversation for `(listing_id, buyer_id)` already exists, it is returned without creating a duplicate.

**Request body:**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `listing_id` | UUID | Yes | Must reference an existing, available listing |

**Response: 200** (both new and existing — idempotent endpoint)
```json
{
  "id": "uuid",
  "listing_id": "uuid",
  "buyer_id": "uuid",
  "seller_id": "uuid",
  "created_at": "2026-06-01T08:00:00.000Z"
}
```

**Errors:**

| Code | Condition | Detail |
|---|---|---|
| 401 | Missing or invalid token | `"Missing token"` / `"Invalid token"` |
| 403 | Caller is the listing's seller | `"You cannot message yourself about your own listing."` |
| 404 | Listing not found or not available | `"Listing not found."` |
| 422 | Missing or invalid `listing_id` | Pydantic validation error |

---

### GET /conversations/{id}/messages

Protected. Returns all messages in the conversation, ordered by `created_at` ascending. Only the buyer or seller of the conversation may call this. Results are cached in Redis for 30 seconds (`chat:{conversation_id}`).

**Path parameters:**

| Parameter | Type | Description |
|---|---|---|
| `id` | UUID | Conversation UUID |

**Response: 200**
```json
[
  {
    "id": "uuid",
    "conversation_id": "uuid",
    "sender_id": "uuid",
    "body": "string",
    "is_read": false,
    "created_at": "2026-06-01T09:15:00.000Z"
  }
]
```

Fields never returned: `email`, `phone`, `full_name`, `avatar_url`, `seller contact info`.

**Errors:**

| Code | Condition | Detail |
|---|---|---|
| 401 | Missing or invalid token | `"Missing token"` / `"Invalid token"` |
| 403 | Caller is not buyer or seller | `"Not a participant in this conversation."` |
| 404 | Conversation UUID not found | `"Conversation not found."` |

---

### POST /conversations/{id}/messages

Protected. Sends a message in the conversation. Only the buyer or seller may send. Rate-limited to 100 messages per user per conversation per hour (Redis key: `chat_rate:{conversation_id}:{sender_id}`, TTL 1 hour). Sending a message invalidates the Redis message cache for this conversation.

First message in a conversation triggers a one-time email to the seller. `first_message_notified` is set atomically and is never reset.

**Path parameters:**

| Parameter | Type | Description |
|---|---|---|
| `id` | UUID | Conversation UUID |

**Request body:**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `body` | string | Yes | Non-empty after strip, max 2000 characters |

**Response: 201**
```json
{
  "id": "uuid",
  "conversation_id": "uuid",
  "sender_id": "uuid",
  "body": "string",
  "is_read": false,
  "created_at": "2026-06-06T10:30:00.000Z"
}
```

**Errors:**

| Code | Condition | Detail |
|---|---|---|
| 401 | Missing or invalid token | `"Missing token"` / `"Invalid token"` |
| 403 | Caller is not buyer or seller | `"Not a participant in this conversation."` |
| 404 | Conversation UUID not found | `"Conversation not found."` |
| 422 | Empty body or body over 2000 chars | Pydantic validation error |
| 429 | Rate limit exceeded (100/hour) | `"Message rate limit reached. Try again later."` |

---

### PATCH /conversations/{id}/messages/read

Protected. Marks all messages sent by the other party as `is_read = TRUE`. Does not affect the caller's own messages. Invalidates the Redis message cache for this conversation.

**Path parameters:**

| Parameter | Type | Description |
|---|---|---|
| `id` | UUID | Conversation UUID |

**Request body:** None.

**Response: 204** — no body

**Errors:**

| Code | Condition | Detail |
|---|---|---|
| 401 | Missing or invalid token | `"Missing token"` / `"Invalid token"` |
| 403 | Caller is not buyer or seller | `"Not a participant in this conversation."` |
| 404 | Conversation UUID not found | `"Conversation not found."` |

---

## Payments

### POST /payments/onboard

Protected. Starts Razorpay Route seller onboarding. Creates a linked Razorpay account and returns a KYC URL. Does not set `razorpay_account_id` on the user — that happens only after KYC completes via `POST /payments/onboard/complete`.

**Request body:** None.

**Response: 200**
```json
{
  "onboarding_url": "https://razorpay.com/...",
  "razorpay_account_id": "acc_xxx"
}
```

If the seller is already onboarded:
```json
{ "message": "Already onboarded" }
```

**Errors:**

| Code | Condition | Detail |
|---|---|---|
| 401 | Missing or invalid token | `"Missing token"` / `"Invalid token"` |

---

### POST /payments/onboard/complete

Protected. Called by the frontend after Razorpay redirects back from KYC. Verifies account activation status via the Razorpay API. If activated, sets `razorpay_account_id` on `public.users`.

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `razorpay_account_id` | string | Yes | Returned by `POST /payments/onboard` |

**Response: 200**
```json
{ "status": "complete" }
```

If already complete:
```json
{ "status": "already_complete" }
```

**Errors:**

| Code | Condition | Detail |
|---|---|---|
| 400 | Razorpay account KYC not yet activated | `"Razorpay account KYC not yet complete. Please finish verification."` |
| 401 | Missing or invalid token | `"Missing token"` / `"Invalid token"` |
| 422 | Missing `razorpay_account_id` | Pydantic validation error |

---

### POST /payments/verify-passkey

Protected. Verifies the buyer's passkey against the listing's stored hash and, if correct, generates a Razorpay Payment Link. The buyer is then redirected to the Razorpay-hosted payment page.

Checks run in this exact order — stop on first failure:
1. Listing exists, `is_available = TRUE`, `passkey_invalidated = FALSE`
2. Caller is not the listing's seller
3. Redis block check: `passkey_attempts:{listing_id}:{buyer_id}` — if ≥ 3, reject
4. HMAC passkey verification (constant-time via `hmac.compare_digest`)
5. On correct passkey: idempotency check, row lock, create transaction, generate payment link

**Request body:**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `listing_id` | UUID | Yes | — |
| `passkey` | string | Yes | 8-digit numeric string |

**Response: 200**
```json
{ "payment_link_url": "https://rzp.io/..." }
```

**Errors:**

| Code | Condition | Detail |
|---|---|---|
| 404 | Listing UUID not found | `"Listing not found."` |
| 400 | Listing sold or passkey invalidated | `"This listing has already been sold."` |
| 400 | Listing paused (`is_available = FALSE`) | `"This listing is temporarily unavailable."` |
| 400 | Incorrect passkey, attempts < 3 | `"Incorrect passkey. {n} attempts remaining."` |
| 401 | Missing or invalid token | `"Missing token"` / `"Invalid token"` |
| 403 | Caller is the listing's seller | `"You cannot purchase your own listing."` |
| 403 | Buyer blocked (attempts ≥ 3) | `"You have been blocked from purchasing this listing."` |
| 409 | Listing locked by concurrent buyer | `"This listing was just sold. You have not been charged."` |
| 422 | Missing or invalid fields | Pydantic validation error |

---

### POST /payments/webhook

No auth. Razorpay server-to-server webhook.

HMAC signature (`X-Razorpay-Signature` header) is verified against `RAZORPAY_WEBHOOK_SECRET` before any processing. Unrecognised events always return 200 — never 4xx (prevents Razorpay retries).

Handles two events:
- `payment_link.paid` — confirms payment, releases transaction, closes listing
- All other events — ignored with 200

**Request body:** Razorpay webhook payload (JSON).

**Required header:** `X-Razorpay-Signature: <hmac_hex>`

**Response: 200** — always (after signature verification passes)

**Errors:**

| Code | Condition |
|---|---|
| 400 | Invalid HMAC signature |

No 4xx for unknown events or unknown transaction IDs — always 200 in those cases.

**Payment lifecycle on `payment_link.paid`:**
1. Verify signature
2. Extract `payment_link_id` and `payment_id`
3. Look up transaction by `razorpay_payment_link_id`
4. If `status = 'released'`: idempotency, return 200 with no action
5. If `status != 'initiated'`: late webhook — refund `payment_id`, return 200
6. Atomic: `UPDATE transactions SET status='released' WHERE status='initiated'`
7. Atomic: `UPDATE listings SET is_available=FALSE, sold_at=now(), passkey_invalidated=TRUE WHERE is_available=TRUE`
8. If Step 7 fails (listing already sold): refund `payment_id`, set `status='cancelled'`, return 200
9. On success: send seller sale-complete email (fire-and-forget)

---

### GET /transactions/{id}/status

Protected. Buyer polling endpoint. Returns only the transaction belonging to the caller (matched by `buyer_id`). The buyer's status page polls this every 2 seconds and stops when status is `released` or `cancelled`.

**Path parameters:**

| Parameter | Type | Description |
|---|---|---|
| `id` | UUID | Transaction UUID |

**Response: 200**
```json
{
  "status": "initiated | released | cancelled",
  "amount_rupees": 450
}
```

**Errors:**

| Code | Condition | Detail |
|---|---|---|
| 401 | Missing or invalid token | `"Missing token"` / `"Invalid token"` |
| 404 | Transaction not found or caller is not the buyer | `"Transaction not found."` |

---

## Complete endpoint table

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/listings` | Public | List/search available listings |
| `POST` | `/listings` | Protected | Create listing (passkey returned once) |
| `GET` | `/listings/{id}` | Public | Get listing detail (increments views) |
| `PATCH` | `/listings/{id}` | Protected, owner | Update listing fields |
| `DELETE` | `/listings/{id}` | Protected, owner | Soft-delete listing |
| `PATCH` | `/listings/{id}/passkey` | Protected, owner | Regenerate passkey |
| `GET` | `/users/me` | Protected | Get caller's profile |
| `PATCH` | `/users/me` | Protected | Update caller's profile |
| `GET` | `/users/{id}` | Public | Get public user profile |
| `GET` | `/conversations` | Protected | List caller's conversations |
| `POST` | `/conversations` | Protected | Create or return existing conversation |
| `GET` | `/conversations/{id}/messages` | Protected, participant | Get messages (cached 30s) |
| `POST` | `/conversations/{id}/messages` | Protected, participant | Send message (rate-limited) |
| `PATCH` | `/conversations/{id}/messages/read` | Protected, participant | Mark messages as read |
| `POST` | `/payments/onboard` | Protected | Start Razorpay seller KYC |
| `POST` | `/payments/onboard/complete` | Protected | Complete seller KYC after redirect |
| `POST` | `/payments/verify-passkey` | Protected | Verify passkey + generate payment link |
| `POST` | `/payments/webhook` | None (HMAC-verified) | Razorpay payment confirmation |
| `GET` | `/transactions/{id}/status` | Protected, buyer | Poll transaction status |

---

## Fields never returned in any response

The following fields exist in the database but must never appear in any API response:

| Field | Table | Reason |
|---|---|---|
| `passkey_hash` | `listings` | Hash of seller passkey — never exposed |
| `passkey_invalidated` | `listings` | Internal state — not needed by clients |
| `passkey_invalidated_at` | `listings` | Internal audit field |
| `sold_at` | `listings` | Internal — `is_available=FALSE` is enough for clients |
| `deleted_at` | `listings` | Internal soft-delete timestamp — not needed by clients |
| `razorpay_payment_link_id` | `transactions` | Internal Razorpay reference |
| `razorpay_payment_id` | `transactions` | Internal Razorpay reference |
| `platform_fee_rupees` | `transactions` | Internal — 0% in v1 |
| `seller_payout_rupees` | `transactions` | Only surfaced in seller email, not in API |
| `refunded_at` | `transactions` | Internal audit field |
| `released_at` | `transactions` | Internal audit field |
| `first_message_notified` | `conversations` | Internal email tracking flag |

---

## Redis keys

| Key | TTL | Purpose |
|---|---|---|
| `passkey_attempts:{listing_id}:{buyer_id}` | 7 days | Passkey attempt counter per buyer per listing |
| `abandoned_notified:{listing_id}` | 6 hours | Prevents duplicate abandoned-checkout emails per listing |
| `chat_rate:{conversation_id}:{sender_id}` | 1 hour | Message rate limit counter |
| `chat:{conversation_id}` | 30 seconds | Cached message list for GET /conversations/{id}/messages |

---

## APScheduler jobs

One job exists. Runs every 5 minutes inside FastAPI process (no separate worker).

**Job: cancel_abandoned_transactions**
- Query: `transactions WHERE status='initiated' AND created_at < now() - 15 minutes`
- Action: `status = 'cancelled'`, seller email with 6h cooldown per listing (`abandoned_notified:{listing_id}`)
- Log: every run, count found, count cancelled

No Celery. No separate worker process. APScheduler runs in-process with FastAPI via `AsyncIOScheduler`.

---

## Files to create

None. This is a reference spec only.

---

## Files to modify

None. This is a reference spec only.

---

## New dependencies

No new dependencies.

---

## Security considerations

All thirteen security rules from CLAUDE.md apply to the API surface collectively:

- **Rule 1** — Seller contact info is never in any API response. `MessageOut` contains only `sender_id` (UUID), `body`, `is_read`, `created_at`. No `email`, `phone`, `full_name`.
- **Rule 2** — Razorpay webhook HMAC verified before any processing. Invalid signature → 400. No action taken.
- **Rule 3** — Unknown webhook events → 200. Never 4xx. Prevents Razorpay retry storms.
- **Rule 4** — Supabase session in httpOnly cookies on frontend. FastAPI receives only the Bearer token, never a cookie.
- **Rule 5** — All owner mutations (`PATCH /listings/{id}`, `DELETE /listings/{id}`, `PATCH /listings/{id}/passkey`) verify `listing.seller_id == user["sub"]` before proceeding.
- **Rule 6** — Image uploads go directly to Cloudinary from the browser. FastAPI never receives image bytes. `images` field in listing requests is an array of already-uploaded Cloudinary URLs.
- **Rule 7** — All DB operations use SQLAlchemy ORM with parameterized queries. No string-interpolated SQL anywhere.
- **Rule 8** — CORS restricted to `FRONTEND_URL` in production. Never `*`.
- **Rule 9** — `SUPABASE_SERVICE_ROLE_KEY` used only in `supabase_admin.py` for background jobs and webhook handler. Never in request handlers that return data to the client.
- **Rule 10** — `PASSKEY_HMAC_SECRET` never logged, never in any response. `passkey_hash` never in any response.
- **Rule 11** — `hmac.compare_digest` used in `verify_passkey`. Never `==`.
- **Rule 12** — No cancelled transaction is ever reopened. Late webhooks always trigger refund.
- **Rule 13** — Listing hidden immediately on piracy report via Supabase dashboard SQL. No API endpoint for this — manual moderation only in v1.

---

## Definition of done

- [ ] Every endpoint in the complete table above responds to a valid request with the documented status code and response shape
- [ ] Every endpoint returns the documented error code and detail string for each failure condition listed
- [ ] `GET /listings` with no query params returns all `is_available=TRUE` listings; with `?exam_category=JEE_MAINS` returns only JEE_MAINS listings
- [ ] `POST /listings` without a Razorpay account returns 403 with `"Complete payment setup to start selling."`
- [ ] `POST /listings` response contains a `passkey` field with an 8-digit numeric string; calling `GET /listings/{id}` on the same listing does not return `passkey_hash` or `passkey`
- [ ] `PATCH /listings/{id}` by a non-owner returns 403; owner receives 200 with updated fields
- [ ] `DELETE /listings/{id}` sets `deleted_at=now()` and `is_available=FALSE` in DB; `sold_at` remains `NULL`; running the Spec 06 state breakdown query counts this listing under "deleted" not "sold"; `GET /listings` no longer returns it
- [ ] `GET /users/{id}` response does not contain `razorpay_account_id`
- [ ] `GET /users/me` response contains `razorpay_account_id` (null until onboarding complete)
- [ ] `GET /conversations` returns only conversations where caller is buyer or seller — cannot see others' conversations
- [ ] `POST /conversations` with caller = seller returns 403
- [ ] `POST /conversations` called twice with the same `listing_id` returns the same `id` both times (idempotent)
- [ ] `GET /conversations/{id}/messages` by a non-participant returns 403
- [ ] `POST /conversations/{id}/messages` with empty body returns 422; with body over 2000 chars returns 422
- [ ] `POST /conversations/{id}/messages` 101st message in one hour returns 429
- [ ] `PATCH /conversations/{id}/messages/read` marks other party's messages `is_read=TRUE`; caller's own messages are unaffected
- [ ] `POST /payments/verify-passkey` with a non-existent `listing_id` UUID returns 404 `"Listing not found."`
- [ ] `POST /payments/verify-passkey` with 3 wrong passkeys returns 403 on third attempt; subsequent calls with correct passkey also return 403 (blocked)
- [ ] `POST /payments/webhook` with wrong HMAC signature returns 400; with unknown event returns 200
- [ ] `GET /transactions/{id}/status` by a user who is not the buyer returns 404
- [ ] None of the fields listed in "Fields never returned" appear in any API response (inspect response bodies directly)
- [ ] CORS response headers on OPTIONS requests to any endpoint show only `FRONTEND_URL` in `Access-Control-Allow-Origin`, not `*`

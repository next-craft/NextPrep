# Spec 02: User Flows

## Purpose

This spec documents every user journey in Study Material Exchange India — step by step — covering browse, list, chat, buy, and sell. Because the platform is a peer-to-peer in-person marketplace (no shipping, no courier, no delivery tracking), the flows are structured around the physical meetup as the trust anchor. The passkey system replaces escrow: the seller hands the buyer a code, the buyer enters it online, and payment happens only after the meetup is confirmed. This spec exists so that both developers share an identical mental model of what a user experiences at each screen, what happens in the backend at each step, and where error states occur.

---

## Depends on

- Spec 01: Overview (project scope, stack, constraints)
- Supabase project configured with Google OAuth and DB trigger (`handle_new_user`) from AUTH.md
- DB schema applied via Alembic (SCHEMA.md)

---

## Scope

**In scope:**
- All user-facing flows: sign in, browse listings, create a listing, chat between buyer and seller, buy (passkey + payment), sell (listing management, passkey, payout).
- All error states and edge cases within each flow.
- Exact screen copy for key UI moments (passkey reveal, payment link, sold confirmation).
- Seller Razorpay onboarding requirement.

**Out of scope:**
- Admin moderation flows (manual via Supabase dashboard — see CLAUDE.md)
- Rating submission flow (post-transaction, documented separately)
- Password auth (not built — Google OAuth only)
- Mobile app (not in v1)
- Shipping / delivery (not in v1)

---

## 1. Authentication Flow

### 1.1 First-time sign in

1. User lands on `/` (marketing page) or any listing page.
2. User clicks "Sign in with Google" button.
3. Frontend calls:
   ```javascript
   await supabase.auth.signInWithOAuth({
     provider: 'google',
     options: { redirectTo: `${window.location.origin}/auth/callback` }
   })
   ```
4. Google OAuth consent screen shown.
5. On success, Supabase redirects to `/auth/callback`.
6. Supabase DB trigger `on_auth_user_created` fires and inserts a row into `public.users`:
   - `full_name` from Google profile
   - `avatar_url` from Google profile
   - `is_verified = TRUE` (Google OAuth emails are verified)
7. Session stored in httpOnly cookies by `@supabase/ssr` middleware.
8. User redirected to `/listings` (marketplace home).

### 1.2 Returning user sign in

Same flow — Supabase issues a new session. No new `public.users` row (trigger is `INSERT` only, not `UPSERT`).

### 1.3 Sign out

1. User clicks "Sign out" in dashboard or nav.
2. Frontend calls `await supabase.auth.signOut()`.
3. Session cookie cleared.
4. User redirected to `/`.

### 1.4 Protected page access when unauthenticated

- Server Component reads session via `createServerSupabaseClient()`.
- If no user: `redirect('/login')`.
- Applies to: `/dashboard`, `/listings/new`, `/chat/[id]`, `/transactions/[id]/status`.
- Public pages never redirect: `/listings`, `/listings/[id]`, `/users/[id]`.

---

## 2. Browse Flow

### 2.1 Listing index — `/listings`

Rendered as SSR (React Server Component). Google can index it.

1. Page fetches listings via `GET /v1/listings` with any active query params.
2. Backend executes `search_listings()` — WHERE + ILIKE only (see SCHEMA.md).
3. Listings rendered as cards showing:
   - First image (Cloudinary URL, `next/image`)
   - Title
   - `formatPrice(asking_price)` — e.g. "₹450"
   - Condition badge: A / B / C
   - Listing type badge: BOOK / NOTES / MODULE / BUNDLE
   - City
   - Exam category

#### Filter sidebar / chips
Available filters (all optional, combinable):
- `q` — free text search (title + description)
- `exam_category` — dropdown from canonical list (see CLAUDE.md)
- `listing_type` — BOOK / NOTES / MODULE / BUNDLE
- `condition` — A / B / C
- `city` — exact match from predefined city list (dropdown in UI, ILIKE on backend for resilience)
- `subject` — free text ILIKE

Filters applied as URL query params. Page re-renders server-side on change.

#### No results state
"No listings found for your filters. Try removing a filter or broadening your search."

#### Empty marketplace state (zero listings)
"Be the first to list study material in your city."

### 2.2 Listing detail — `/listings/[id]`

Rendered as SSR. Google can index it.

1. Page fetches `GET /v1/listings/{id}`.
2. If listing not found or `is_available = FALSE` and `sold_at` is not null: show "This listing is no longer available."
3. If listing `is_available = FALSE` and `sold_at` is null (paused/suspended): show "This listing is temporarily unavailable."
4. Page shows:
   - Image carousel (up to 5 Cloudinary images)
   - Title
   - `formatPrice(asking_price)` — large, prominent
   - Original price if set: "Original price: ₹800" (struck through)
   - Condition: full label — "A — Like new", "B — Good", "C — Acceptable"
   - Listing type: BOOK / NOTES / MODULE / BUNDLE
   - Exam category
   - Subject (if set)
   - City
   - Description
   - Seller card: avatar, name, city, `seller_rating` (if set), `total_sales`
   - "Chat with seller" button (authenticated users only)
   - "Buy Now" button (authenticated users only; hidden from listing owner)
   - View count (backend increments `views` on each GET)

5. If user is the listing owner: show "Edit listing" and "Manage passkey" buttons instead of Buy Now / Chat.

---

## 3. List (Sell) Flow

### 3.1 Seller Razorpay onboarding (one-time prerequisite)

Before a seller can create any listing, they must connect a Razorpay account via Razorpay Route.

- Dashboard shows banner: "Complete payment setup to start selling."
- Button: "Set up payouts" → opens Razorpay Route onboarding flow.
- Until onboarding is complete: "Create Listing" button is disabled.
- After KYC approved by Razorpay: button enabled, banner hidden.

This is checked on the dashboard and the listing creation page.

### 3.2 Create listing — `/listings/new`

Protected route. Redirects to `/login` if unauthenticated.

**Form fields:**

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| Title | text | yes | max 120 chars |
| Description | textarea | no | max 1000 chars |
| Exam category | select | yes | canonical list |
| Subject | text + dropdown | no | free text, dropdown defaults |
| Listing type | select | yes | BOOK / NOTES / MODULE / BUNDLE |
| Condition | select | yes | A / B / C with full labels |
| Asking price | integer | yes | whole rupees, ≥ 1 |
| Original price | integer | no | whole rupees |
| City | select | yes | predefined dropdown of major Indian cities |
| Images | upload | no | max 5, direct to Cloudinary |

**Image upload:**
- Cloudinary upload widget used directly in browser.
- Returns Cloudinary URLs stored in `images TEXT[]` column.
- Never routed through FastAPI.

**Submission:**
1. Frontend sends `POST /v1/listings` with Bearer token.
2. Backend creates listing row.
3. Backend generates passkey:
   ```python
   passkey = str(secrets.randbelow(100_000_000)).zfill(8)
   passkey_hash = hash_passkey(passkey, str(listing.id))
   ```
4. `passkey_hash` stored. Plaintext `passkey` returned in API response only once.
5. User redirected to listing success screen.

### 3.3 Passkey reveal screen

Shown immediately after listing creation. Not accessible again.

```
Your listing is live!

Your passkey is:
  0 3 9 1  8 4 7 2

Give this code to the buyer only when they are ready to pay during the meetup.
The order is: meet → inspect → share passkey → pay.
Do not share it over chat — buyers must enter it in the app.

⚠️ You won't be able to see this code again. Copy or memorise it now.

[Copy passkey]   [Go to my listing]
```

### 3.4 Listing management (seller dashboard)

Seller dashboard at `/dashboard` shows:
- All their listings with current status (available / paused / sold)
- For each listing: edit, pause/resume, regenerate passkey, delete options

**Edit listing** (`PATCH /v1/listings/{id}`):
- Can update title, description, asking_price, condition, images.
- Cannot change listing_type or exam_category after creation (prevents bait-and-switch).

**Pause listing:**
- Sets `is_available = FALSE`, `sold_at = NULL`.
- Listing disappears from search.
- Existing conversations preserved.

**Resume listing:**
- Sets `is_available = TRUE`.
- Listing reappears in search.

**Delete listing (`DELETE /v1/listings/{id}`):**
- Soft delete: `is_available = FALSE`, `sold_at = now()`.
- Conversations archived, not deleted (dispute history).

**Regenerate passkey:**
- Calls backend endpoint that generates new passkey, new hash, overwrites old hash.
- Old passkey becomes immediately invalid.
- New plaintext passkey shown once on screen (same reveal UI as creation).
- Available only while `passkey_invalidated = FALSE`.

---

## 4. Chat Flow

### 4.1 Starting a conversation (buyer)

1. Authenticated buyer on `/listings/[id]` clicks "Chat with seller".
2. Frontend calls `POST /v1/conversations` with `listing_id`.
3. If conversation already exists for this buyer+listing: backend returns existing conversation.
4. UNIQUE constraint: `UNIQUE(listing_id, buyer_id)` — one conversation per buyer per listing.
5. Buyer redirected to `/chat/[conversation_id]`.
6. Backend sends email to seller on first message only (tracked via `first_message_notified`).

### 4.2 Chat page — `/chat/[id]`

Protected route. Polling every 4 seconds via TanStack Query:

```javascript
const { data } = useQuery({
  queryKey: ['messages', conversationId],
  queryFn: () => api.get(`/v1/conversations/${conversationId}/messages`),
  refetchInterval: 4000,
})
```

**What users see:**
- Conversation thread (buyer and seller messages, oldest first)
- Listing summary card at top (title, price, image thumbnail)
- Message input + send button
- Read receipts via `is_read` flag
- "Buy Now" button if user is buyer and listing is still available

**Rate limit:**
- 100 messages per user per conversation per hour (Redis key: `chat_rate:{conversation_id}:{sender_id}`)
- On limit hit: "You've sent too many messages. Please wait before sending more."

**What is never shown in chat responses:**
- Seller phone number
- Seller email address
- Any contact information
Backend must never return these fields in conversation or message responses.

### 4.3 Message read status

- `PATCH /v1/conversations/{id}/messages/read` marks all messages as read for the calling user.
- Called when user opens the chat tab and when new messages arrive via polling.

### 4.4 Seller notification

- On first message in a new conversation:
  - Backend checks `first_message_notified = FALSE`.
  - Sends email via Resend: "Someone is interested in [listing title]".
  - Sets `first_message_notified = TRUE`.
- No email on subsequent messages.

---

## 5. Buy Flow

### 5.1 Buy Now (pure UI event)

1. Authenticated buyer on listing page (or chat page) clicks "Buy Now".
2. **No backend call. No DB write. No transaction created.**
3. Passkey input field appears inline on the listing page.
4. Listing remains visible and available to all other buyers.

### 5.2 In-person meetup

The buyer and seller arrange meetup via chat. The exact sequence at the meetup:

1. **Meet** — buyer and seller meet in person.
2. **Inspect** — buyer physically examines the material. If not satisfied, buyer walks away. No passkey entered, no payment triggered.
3. **Share passkey** — if buyer is satisfied and ready to pay, seller reads out the 8-digit passkey.
4. **Pay** — buyer enters the passkey in the app, gets redirected to Razorpay, and completes payment.

**The passkey is evidence that the seller authorized the purchase during the meetup flow.** The seller only shares the passkey once the buyer has inspected the material and confirmed they want it. The buyer has no incentive to enter the passkey before they've seen the goods. Payment cannot happen without the passkey, and the passkey is only useful after inspection.

### 5.3 Passkey validation — `POST /v1/payments/verify-passkey`

Request body:
```json
{ "listing_id": "<uuid>", "passkey": "03918472" }
```

Backend checks run in this order (stop on first failure):

**Check 1 — Is listing available?**
```python
if not listing or not listing.is_available or listing.passkey_invalidated:
    raise HTTPException(400, "This listing has already been sold.")
```

**Check 2 — Is buyer blocked?**
```python
attempts_key = f"passkey_attempts:{listing_id}:{buyer_id}"
if attempts >= 3:
    raise HTTPException(403, "You have been blocked from purchasing this listing.")
```

**Check 3 — Verify passkey**
```python
if not verify_passkey(submitted_passkey, listing_id, listing.passkey_hash):
    # increment Redis counter, TTL 7 days
    remaining = max(0, 3 - new_count)
    raise HTTPException(400, f"Incorrect passkey. {remaining} attempts remaining.")
```

Error copy shown in UI:
- Wrong passkey: "Incorrect passkey. 2 attempts remaining."
- Blocked: "You have been blocked from purchasing this listing."
- Already sold: "This listing has already been sold."

### 5.4 Payment initiation (on correct passkey)

On successful passkey verification, the same backend request:
1. Checks for existing `initiated` transaction (idempotency — returns same link).
2. Acquires row lock on listing (`SELECT FOR UPDATE SKIP LOCKED`).
3. Creates `Transaction` row with `status = 'initiated'`.
4. Creates Razorpay Payment Link with 15-minute expiry.
5. Stores `razorpay_payment_link_id` and `razorpay_payment_link_url` in transaction.
6. Returns `{ "payment_link_url": "https://rzp.io/..." }` to frontend.

Frontend immediately redirects buyer to Razorpay payment page.

### 5.5 Payment processing

1. Buyer completes payment on Razorpay (UPI, net banking, card, wallet).
2. Razorpay redirects buyer to `{FRONTEND_URL}/transactions/{id}/status` (callback URL).
3. **This callback URL triggers no DB writes.**
4. Page shows: "Payment processing… please wait."
5. Page polls `GET /v1/transactions/{id}/status` every 2 seconds.

### 5.6 Razorpay webhook (authoritative confirmation)

Razorpay sends `POST /v1/payments/webhook` server-to-server. Handler:
1. Verifies HMAC signature.
2. Confirms event is `payment_link.paid`.
3. Finds transaction by `razorpay_payment_link_id`.
4. Idempotency: if already `released`, returns 200.
5. Late webhook: if `status != 'initiated'`, refunds immediately, returns 200.
6. Atomically updates transaction to `status = 'released'`.
7. Atomically updates listing: `is_available = FALSE`, `sold_at = now()`, `passkey_invalidated = TRUE`.
8. If Step 7 listing update finds no rows (concurrent payment won): refunds this payment, sets transaction to `cancelled`.
9. Sends sale-complete email to buyer and seller.
10. Razorpay Route automatically pays seller 100% (`seller_payout_rupees`).

### 5.7 Buyer success screen

Polling detects `status = 'released'`:

```
Payment confirmed! 🎉

You've successfully purchased:
[Listing title]
₹450

The seller has been notified. Arrange pickup if you haven't already.

[View my purchases]
```

### 5.8 Payment abandonment (15-minute window)

If buyer doesn't pay within 15 minutes:
- APScheduler job (every 5 minutes) sets `status = 'cancelled'`.
- Listing remains available.
- Passkey remains valid — buyer can retry.
- No money charged.
- Seller receives abandoned checkout email (max one per listing per 6 hours).

---

## 6. Sell Flow (Seller Perspective)

### 6.1 Seller receives interested buyer notification

- Seller gets email: "Someone is interested in [listing title]."
- Seller opens `/dashboard` to see the conversation.
- Seller responds via chat to arrange meetup.

### 6.2 At the meetup

- Seller shows the material.
- If buyer is satisfied, buyer enters passkey in app.
- **Seller does not do anything at this step** — passkey entry is buyer-initiated.

### 6.3 Seller receives sale notification

After webhook confirms payment:
- Seller gets email: "Your listing '[title]' has been sold for ₹450."
- Razorpay Route sends 100% (`seller_payout_rupees`) to seller's linked account automatically.
- No manual payout action required.

### 6.4 Seller dashboard post-sale

- Listing shows as "Sold" in dashboard.
- `total_sales` incremented.
- Listing no longer appears in search results.
- Conversation preserved (archived).

---

## 7. Dashboard Flow

Dashboard at `/dashboard` — client-rendered, authenticated.

**Tabs:**
- "Selling" — all listings the user has created, grouped by status (active / paused / sold)
- "Buying" — all conversations where user is buyer, with listing status visible
- "Transactions" — all transactions (as buyer and seller)

**Selling tab — per listing:**
- Thumbnail, title, price, condition
- Status badge
- Unread message count (red badge)
- Actions: Edit | Pause/Resume | Regenerate passkey | Delete

**Buying tab — per conversation:**
- Listing thumbnail and title
- Last message preview
- Unread badge
- Listing status: Available / Sold / Unavailable
- "Buy Now" button if listing still available and user hasn't bought it

**Transactions tab — per transaction:**
- Listing title
- Amount
- Status: Initiated / Released / Cancelled
- Date

---

## 8. Edge Cases and Error States

### Buyer tries to buy own listing
- "Buy Now" button hidden from listing owner (check `seller_id == current_user.id` client-side and server-side).
- Backend rejects if attempted anyway: 403 "You cannot purchase your own listing."

### Buyer runs out of passkey attempts
- After 3 wrong attempts: Redis key `passkey_attempts:{listing_id}:{buyer_id}` blocks further attempts for 7 days.
- UI shows: "You have been blocked from purchasing this listing."
- No way to reset without contacting support (manual Redis key deletion).

### Two buyers pay simultaneously (concurrent payment race)
- Both enter correct passkey and get payment links.
- Both pay.
- First webhook to complete Step 7 (atomic listing UPDATE) wins.
- Second buyer's payment: listing UPDATE returns no rows → buyer immediately refunded.
- Second buyer sees on polling: "Payment could not be completed. You have not been charged."

### Listing deleted while buyer in checkout
- Buyer holds a payment link from before deletion.
- If buyer pays: webhook Step 7 finds `is_available = FALSE` → refunds immediately.

### Passkey regenerated after buyer received link
- Payment link already exists → buyer can still complete payment.
- But if webhook fires after passkey regenerated: transaction is `initiated`, listing is `is_available = TRUE` and `passkey_invalidated = FALSE` (regenerating passkey doesn't invalidate mid-flight transactions) → payment succeeds normally.

### Payment link expires (15 minutes)
- Razorpay rejects payment attempt.
- APScheduler cancels the transaction.
- Buyer sees: "Your payment window has expired. You can try again."
- Buyer may re-enter passkey to get a new link (attempt counter not consumed).

### Seller hasn't set up Razorpay
- "Create Listing" disabled in UI.
- If attempted via API: backend returns 403 "Complete payment setup before creating listings."

---

## Files to create

```
frontend/app/(auth)/login/page.jsx
frontend/app/(auth)/callback/page.jsx
frontend/app/(marketplace)/listings/page.jsx
frontend/app/(marketplace)/listings/new/page.jsx
frontend/app/(marketplace)/listings/[id]/page.jsx
frontend/app/dashboard/page.jsx
frontend/app/chat/[id]/page.jsx
frontend/app/transactions/[id]/status/page.jsx
frontend/components/listings/ListingCard.jsx
frontend/components/listings/ListingGrid.jsx
frontend/components/listings/ListingFilters.jsx
frontend/components/listings/BuyNowButton.jsx
frontend/components/listings/PasskeyInput.jsx
frontend/components/chat/MessageThread.jsx
frontend/components/chat/MessageInput.jsx
frontend/components/dashboard/SellingTab.jsx
frontend/components/dashboard/BuyingTab.jsx
frontend/components/dashboard/TransactionsTab.jsx
frontend/constants/examCategories.js
frontend/constants/listingTypes.js
frontend/constants/subjects.js
frontend/constants/conditions.js
frontend/constants/cities.js
```

---

## Files to modify

```
frontend/middleware.js — add auth session refresh (already in AUTH.md)
frontend/lib/supabase/client.js — Supabase browser client (already in AUTH.md)
frontend/lib/supabase/server.js — Supabase server client (already in AUTH.md)
frontend/lib/api.js — Axios instance with auth interceptor (already in AUTH.md)
```

---

## New dependencies

No new dependencies beyond the stack already defined in CLAUDE.md.

```
@supabase/ssr          — Supabase auth for Next.js App Router
axios                  — HTTP client with interceptors
@tanstack/react-query  — client state, polling, mutations
```

---

## Security considerations

1. **Never expose seller contact info** — `email`, `phone` must never appear in conversation or listing API responses. Backend must explicitly exclude these fields from all serialized responses.
2. **Supabase session in httpOnly cookies** — never localStorage. `@supabase/ssr` handles this. Never call `localStorage.setItem` with session data.
3. **Validate listing ownership before every mutation** — `listing.seller_id == user["sub"]` checked in every `PATCH` and `DELETE` handler.
4. **Passkey plaintext never logged** — only `passkey_hash` stored. Plaintext returned once in creation response, never persisted or logged.
5. **`hmac.compare_digest` for passkey verification** — never `==`.
6. **Buy Now is a pure UI event** — no backend call prevents premature transaction creation and listing state pollution.
7. **CORS: allow only `FRONTEND_URL`** — never `*` in production.
8. **Webhook HMAC verified before processing** — any request without valid signature returns 400.
9. **Return 200 for unrecognised webhook events** — never 4xx, prevents Razorpay retry storms.

---

## Definition of done

- [ ] Unauthenticated user can browse `/listings` and `/listings/[id]` without logging in
- [ ] Google OAuth sign-in redirects to `/auth/callback` and creates a `public.users` row
- [ ] Authenticated user can create a listing with all required fields
- [ ] Passkey is shown exactly once after listing creation and cannot be retrieved again
- [ ] Listing appears in search results on `/listings` immediately after creation
- [ ] Buyer can open a chat with seller; seller receives email notification on first message only
- [ ] Chat polling updates every 4 seconds without page refresh
- [ ] Rate limit of 100 messages/hour per user per conversation enforced (returns error on 101st)
- [ ] Buyer entering correct passkey receives a Razorpay payment link within the same request
- [ ] Buyer entering wrong passkey 3 times is blocked (Redis key set, subsequent attempts rejected)
- [ ] Razorpay webhook `payment_link.paid` sets transaction `status = 'released'` and listing `is_available = FALSE`
- [ ] Concurrent payment race: second buyer's payment is refunded, first buyer's transaction is `released`
- [ ] Abandoned transaction (>15 min) set to `cancelled` by APScheduler; listing stays available
- [ ] Seller payout of 100% triggered via Razorpay Route on `released` transaction
- [ ] Listing does not appear in search after `is_available = FALSE`
- [ ] Seller can regenerate passkey; old passkey immediately rejected
- [ ] Seller contact info (email, phone) never appears in any API response
- [ ] `/dashboard` shows correct selling / buying / transaction tabs with live data
- [ ] "Create Listing" button disabled until Razorpay Route onboarding complete
- [ ] Owner of listing does not see "Buy Now" or "Chat with seller" on their own listing

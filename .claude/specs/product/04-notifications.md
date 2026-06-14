# Spec 04: Notifications

## Purpose

This spec is the single source of truth for **every email the platform sends** — its exact
trigger, recipient, cooldown, and template copy. NextPrep is an in-person, India-only
study-material marketplace; it has no in-app inbox and no push channel, so transactional
email is the only way the platform reaches a user outside of an active session. The email
subsystem is already implemented in backend code, but its design has lived scattered across
Spec 09 (payment), Spec 10 (chat), Spec 13 (api), and `DECISIONS.md`, and Spec 03
(content-policy) explicitly **deferred** the "seller notification on removal" email to this
notifications spec. This document consolidates all of that: it enumerates the emails, pins
down who receives each one and when, documents the cooldown / single-send guards that protect
sellers from inbox spam, restates the fire-and-forget and service-role email-resolution rules
that every send obeys, and supplies a concrete template for the previously-deferred removal
email (its trigger remains deferred — see below). It exists so that no future change to a
notification has to reverse-engineer the rules from three other specs.

## Depends on

- **Spec 06 — Schema:** `conversations.first_message_notified` (the first-message single-send
  flag) and the `transactions` table (`status`, `created_at`, `listing_id`, `seller_id`,
  `seller_payout_rupees`).
- **Spec 09 — Payment:** the Razorpay webhook handler (sale-complete email, Step 9) and the
  APScheduler `cancel_abandoned_transactions` job (abandoned-checkout email + cooldown).
- **Spec 10 — Chat:** the first-message notification flow and the atomic flag flip.
- **Spec 03 — Content policy:** the "Seller notification on removal" policy this spec
  implements as a template.
- **`fetch_user_email` (AUTH.md / DECISIONS.md):** service-role resolution of a user's email
  from `auth.users`, since `public.users` has no email column.
- **Resend config:** `RESEND_API_KEY` env var (already required in `backend/app/core/config.py`).

## Scope

**In scope:**
- The four seller-facing transactional emails: first-message, sale-complete,
  abandoned-checkout, and listing-removed.
- For each: exact trigger, recipient, cooldown / single-send guard, exact subject + HTML body,
  and dispatch mechanism.
- The cross-cutting rules every send obeys: Resend as provider, fire-and-forget semantics,
  service-role recipient resolution, and mandatory logging.

**Out of scope (and why):**
- **Buyer-facing emails** — v1 has none. The buyer drives every step interactively (chat,
  passkey, payment redirect); there is nothing to notify them about asynchronously.
- **In-app / push / SMS notifications** — not in v1 (DECISIONS.md). Email only.
- **Marketing, digest, or re-engagement email** — not in v1 scope.
- **Auth / login email** (magic links, verification, password reset) — Supabase Auth owns
  identity and sends those directly; the platform never sends auth mail.
- **The trigger for the removal email** — deferred (see "Email 4"). Moderation is manual via
  the Supabase dashboard; building an automated moderation trigger or admin panel is forbidden
  by CLAUDE.md "What NOT to build in v1".
- **JWKS caching, Celery** — explicitly out per CLAUDE.md. Email jobs run inside the existing
  APScheduler / FastAPI process.

## Email provider & sending model

- **Provider:** Resend (free tier). Configured once at module import in
  `backend/app/services/notification_service.py`:

  ```python
  import resend
  from app.core.config import RESEND_API_KEY

  resend.api_key = RESEND_API_KEY
  ```

  `RESEND_API_KEY` is a required env var (backend only, never exposed to the client).

- **From address:** `NextPrep <no-reply@yourdomain.com>` for every email. There is no reply
  inbox — all replies are expected to happen in-app.

- **Format:** HTML body only (`"html": ...`). No plaintext multipart in v1.

- **Fire-and-forget:** every send function is `async`, wraps the Resend call in
  `try/except`, logs success at `INFO` and failure at `ERROR`, and **never re-raises**. A
  notification is a best-effort side effect; a failed or slow email must never block or roll
  back the DB outcome that triggered it (a stored message, a committed payment, a cancelled
  transaction). A missed email is strictly preferable to a blocked core flow or a spammed
  seller.

- **Plain values, not ORM rows:** every send function takes plain scalars
  (`UUID`, `int`, `str`) rather than a SQLAlchemy model instance, because the sends run after
  the originating DB session has closed (BackgroundTask) or from a job that built its work
  list via bulk `UPDATE ... RETURNING` and holds no live rows.

## Recipient resolution — `fetch_user_email`

Every email goes to a **seller**, addressed by email. `public.users` has **no email column** —
Supabase Auth owns identity — so the address is resolved at send time from `auth.users` using
the service-role client:

```python
# backend/app/core/supabase_admin.py
async def fetch_user_email(user_id: str) -> str | None:
    """Resolve a user's email from auth.users via the service role.
    public.users has no email column — Supabase Auth owns identity."""
    admin = get_supabase_admin()
    try:
        response = admin.auth.admin.get_user_by_id(user_id)
        return response.user.email if response.user else None
    except Exception as e:
        logger.error("Failed to fetch email for user=%s: %s", user_id, str(e))
        return None
```

**Service-role usage is restricted (CLAUDE.md Rule 9).** `SUPABASE_SERVICE_ROLE_KEY` is used
to resolve email in exactly the two approved server-internal contexts, never inside a
user-facing request/response path:

1. **The Razorpay webhook handler** — HMAC-signature-authenticated, not user-facing
   (sale-complete email).
2. **The chat first-message notification** — dispatched as a post-response `BackgroundTask`,
   so the lookup runs after the response is sent, off the request path.

The abandoned-checkout email resolves email inside the APScheduler job, which is also
server-internal (no request scope at all). The service-role value is **never logged, returned,
or exposed to the client**. If `fetch_user_email` returns `None`, the caller logs a warning
and skips the send — it never blocks the surrounding flow.

## Email 1 — First message ("Someone is interested in your listing")

- **Trigger:** the first message in a brand-new conversation (the buyer's opening message).
  No email is sent on any subsequent message in that conversation.
- **Recipient:** the listing's **seller**.
- **Single-send guard:** the `conversations.first_message_notified` boolean. The flag is
  flipped atomically *before* dispatch, using a conditional `UPDATE ... RETURNING`, so two
  concurrent first messages racing on a new conversation cannot both send:

  ```python
  # backend/app/services/chat_service.py
  notify_first = False
  if not conversation.first_message_notified:
      result = await db.execute(
          update(Conversation)
          .where(
              Conversation.id == conversation_id,
              Conversation.first_message_notified == False,  # noqa: E712
          )
          .values(first_message_notified=True)
          .returning(Conversation.id)
      )
      notify_first = result.scalar_one_or_none() is not None
  ```

  If the send later fails, the flag stays `TRUE` and the email is **not** retried — one
  notification is sufficient; a missed email beats spamming the seller.

- **Dispatch:** post-response `BackgroundTask`, so neither the email-resolution lookup nor the
  Resend call sits in the request/response path:

  ```python
  # backend/app/services/chat_service.py
  if notify_first:
      background_tasks.add_task(
          _notify_first_message,
          str(conversation_id),
          str(conversation.seller_id),
      )

  async def _notify_first_message(conversation_id_str: str, recipient_user_id_str: str) -> None:
      recipient_email = await supabase_admin.fetch_user_email(recipient_user_id_str)
      if recipient_email:
          await notification_service.send_new_message_email(UUID(conversation_id_str), recipient_email)
      else:
          logger.warning("Could not resolve seller email: conversation=%s", conversation_id_str)
  ```

- **Cooldown:** none (the DB flag is the guard; exactly one per conversation, ever).
- **Template** (`send_new_message_email`):
  - **Subject:** `Someone is interested in your listing`
  - **HTML body:** `<p>A buyer has sent you a message about your listing on NextPrep. Log in to reply.</p>`
- **Code location:** `backend/app/services/notification_service.py::send_new_message_email`.

## Email 2 — Sale complete ("Your listing has been sold!")

- **Trigger:** the Razorpay webhook confirms payment (`payment_link.paid`), the transaction is
  moved to `released` and committed, and **Step 9** of the webhook handler dispatches the
  email.
- **Recipient:** the **seller**.
- **Single-send guard:** the transaction's terminal status. The webhook selects a single
  winner via an atomic status transition, so a duplicate or replayed webhook does not re-send.
- **Dispatch:** post-response `BackgroundTask`, so a slow Resend / Supabase-Admin call cannot
  delay the webhook's `200` (which would risk a Razorpay retry):

  ```python
  # backend/app/routers/payments.py
  background_tasks.add_task(
      _notify_seller_of_sale, transaction.id, transaction.seller_id, transaction.seller_payout_rupees
  )

  async def _notify_seller_of_sale(transaction_id: UUID, seller_id: UUID, seller_payout_rupees: int) -> None:
      seller_email = await fetch_user_email(str(seller_id))
      if seller_email:
          await notification_service.send_sale_complete(transaction_id, seller_payout_rupees, seller_email)
      else:
          logger.warning("Could not resolve seller email for transaction=%s", transaction_id)
  ```

- **Cooldown:** none (terminal event, fires once).
- **Template** (`send_sale_complete`):
  - **Subject:** `Your listing has been sold!`
  - **HTML body:** `<p>Your listing has been purchased. ₹{seller_payout_rupees} will be credited to your Razorpay account.</p>`
    where `{seller_payout_rupees}` is the whole-rupee payout (no paise — paise exist only at
    the Razorpay API boundary).
- **Code location:** `backend/app/services/notification_service.py::send_sale_complete`.

## Email 3 — Abandoned checkout ("A buyer didn't complete checkout")

- **Trigger:** the APScheduler job `cancel_abandoned_transactions`, which runs **every 5
  minutes** and finds transactions still in status `initiated` whose `created_at` is older
  than the **15-minute** payment window. Each is moved to `cancelled` (no refund — no money
  was captured), and the seller is notified that a buyer started but did not complete a
  purchase.
- **Recipient:** the **seller**.
- **Cooldown:** **6 hours per listing**, enforced by the Redis key
  `abandoned_notified:{listing_id}` with TTL **21600 seconds**. The claim is atomic — `SET ...
  NX` — so two abandoned transactions for the same listing in a single job run cannot both
  pass the cooldown and double-send:

  ```python
  # backend/app/jobs/scheduler.py
  for listing_id, seller_id in cancelled:
      notified_key = f"abandoned_notified:{listing_id}"
      # Atomic claim — SET ... NX so two abandoned transactions for the same
      # listing in one run can't both pass the cooldown and double-send.
      claimed = await redis.set(notified_key, "1", ex=21600, nx=True)
      if not claimed:
          continue
      seller_email = await fetch_user_email(str(seller_id))
      if not seller_email:
          # The cooldown is already claimed for 6h — note the loss explicitly
          # so an email-resolution outage is visible rather than silent.
          logger.warning("Abandoned-checkout notify skipped (no email): listing=%s", listing_id)
          continue
      await notification_service.send_abandoned_checkout_email(listing_id, seller_email)
  ```

  Note the deliberate ordering: the cooldown is claimed *before* email resolution, so if
  `fetch_user_email` fails the slot is already consumed for 6h and the loss is logged
  explicitly rather than silently retried on the next 5-minute tick.

- **Dispatch:** inside the APScheduler job (server-internal, no request scope).
- **Template** (`send_abandoned_checkout_email`):
  - **Subject:** `A buyer didn't complete checkout`
  - **HTML body:** `<p>A buyer started a purchase but did not complete payment. Your listing is still available.</p>`
- **Code location:** `backend/app/services/notification_service.py::send_abandoned_checkout_email`.

## Email 4 — Listing removed ("Your listing was removed from NextPrep")

Spec 03 (content-policy) records the policy: *"when a seller's listing is hidden or removed by
moderation, the seller is informed that their listing was removed and why (category, not
reporter identity)."* This spec supplies the template.

- **Recipient:** the **seller** of the removed listing.
- **Trigger — DEFERRED.** v1 moderation is manual: a developer hides/removes a listing via the
  Supabase dashboard (`UPDATE listings SET is_available = FALSE, deleted_at = now() WHERE id =
  '<id>'`) and closes out the report rows. There is **no automated trigger, scheduler job, or
  route** for this email in v1, because automated moderation and an admin panel are both
  forbidden by CLAUDE.md "What NOT to build in v1". The send function is specified and added to
  `notification_service.py` so the copy is canonical, but it is **not wired to any trigger** —
  invoking it is a future manual step (and a candidate for a later moderation-tooling spec).
- **Cooldown:** none planned (removal is a one-time, manually-initiated event per listing).
- **Reason category, never reporter identity.** The body names the violated content-policy
  category only — one of `PIRACY`, `CONTACT_INFO`, `SPAM`, `NOT_STUDY_MATERIAL`, `PROHIBITED`,
  `ABUSIVE`, `OTHER` (the values in `frontend/constants/reportReasons.js`). The reporter's
  identity, the report count, and the reporter list are **never** disclosed.
- **Template** (`send_listing_removed_email` — to be added):
  - **Subject:** `Your listing was removed from NextPrep`
  - **HTML body:** `<p>Your listing was removed from NextPrep because it violated our content policy ({reason_category}). If you believe this was a mistake, you can list compliant material again.</p>`
    where `{reason_category}` is the human-readable category label.
- **Function signature to add** (mirrors the existing three — plain values, async,
  fire-and-forget, logs send at `INFO` / failure at `ERROR`):

  ```python
  async def send_listing_removed_email(listing_id: UUID, seller_email: str, reason_category: str) -> None:
      ...
  ```

## Cooldown & idempotency summary

| Email | Guard | Mechanism |
|---|---|---|
| First message | `conversations.first_message_notified` | Atomic `UPDATE ... WHERE first_message_notified = FALSE RETURNING id` before dispatch — exactly one per conversation. |
| Sale complete | Transaction terminal status (`released`) | Atomic webhook winner-selection — fires once, replays don't re-send. |
| Abandoned checkout | `abandoned_notified:{listing_id}` (Redis, TTL 21600) | Atomic `SET ... NX ex=21600` — max one email per listing per 6 hours. |
| Listing removed | — | One-time manual action per listing; no automated re-send path. |

**Relevant Redis key (already in CLAUDE.md canonical list):**

```
abandoned_notified:{listing_id}    integer, TTL 6 hours (21600s)
```

No new Redis keys are introduced by this spec.

## Logging

CLAUDE.md mandates: **log every email send.** Every send function does so:

- **Success:** `logger.info(...)` keyed by the relevant entity UUID — e.g.
  `"Sale complete email sent: transaction=%s"`, `"First-message email sent: conversation=%s"`,
  `"Abandoned checkout email sent: listing=%s"`.
- **Send failure:** `logger.error(...)` with the entity UUID and `str(e)` — never the email
  body, never the recipient address.
- **Unresolved recipient:** `logger.warning(...)` when `fetch_user_email` returns `None`
  (chat, payment, scheduler all do this).
- **Never logged:** the recipient email address, the email body, `SUPABASE_SERVICE_ROLE_KEY`,
  `RESEND_API_KEY`, or any PII beyond the entity UUID (CLAUDE.md logging rules).

Every module that sends or dispatches email uses `logger = logging.getLogger(__name__)`; no
`print()`.

## Files to create

- `.claude/specs/product/04-notifications.md` — this spec.

## Files to modify

- `backend/app/services/notification_service.py` — **add** `send_listing_removed_email(listing_id, seller_email, reason_category)`, following the exact pattern of the existing three functions (async, `try/except` around `resend.Emails.send`, `from` = `NextPrep <no-reply@yourdomain.com>`, `INFO` on success / `ERROR` on failure, never re-raise). The existing `send_sale_complete`, `send_new_message_email`, and `send_abandoned_checkout_email` are already implemented and are **unchanged** — this spec documents their canonical behavior, it does not rewrite them.

No other backend files change: the first-message dispatch (`chat_service.py`), sale-complete
dispatch (`payments.py`), abandoned-checkout job (`scheduler.py`), email resolution
(`supabase_admin.py`), and config (`config.py`) already match this spec.

## New dependencies

No new dependencies. `resend` and the service-role Supabase client are already in use, and
`RESEND_API_KEY` is already a required env var.

## Security considerations

- **Rule 1 — never expose seller contact info in any API response.** Email addresses are
  resolved server-side via `fetch_user_email` and used only as the Resend recipient. They are
  never returned in any endpoint response, never logged, and never surfaced to the buyer.
- **Rule 9 — service-role key restricted.** `SUPABASE_SERVICE_ROLE_KEY` resolves recipient
  email only in the approved server-internal contexts (HMAC-authenticated webhook handler; the
  post-response chat `BackgroundTask`; the APScheduler job) — never inside a user-facing
  request/response path, and never injected into a request-scoped dependency.
- **Logging rules.** No email body, recipient address, service-role key, or Resend key is ever
  logged; logs key off entity UUIDs only.
- **Content-policy (Spec 03).** The removal email names the violated *category* only — never
  the reporter's identity, the report count, or the reporter list.
- Otherwise standard security rules apply.

## Definition of done

- [ ] `.claude/specs/product/04-notifications.md` exists on branch `spec/04-notifications`.
- [ ] All four emails are documented with trigger, recipient, cooldown / single-send guard,
      and exact subject + HTML body.
- [ ] The first-message, sale-complete, and abandoned-checkout subjects and bodies in the spec
      match the strings in `backend/app/services/notification_service.py` verbatim.
- [ ] The abandoned-checkout cooldown is documented as `abandoned_notified:{listing_id}`,
      TTL 21600s, claimed via atomic `SET ... NX`.
- [ ] The first-message single-send guard is documented as the atomic
      `UPDATE ... WHERE first_message_notified = FALSE RETURNING id`.
- [ ] The removal email has a full template (subject + body) and a specified function signature
      `send_listing_removed_email(listing_id, seller_email, reason_category)`, with its trigger
      explicitly marked **deferred** (no scheduler/route/script built).
- [ ] The removal email body names a content-policy category and never the reporter identity.
- [ ] The "log every email send" rule and the "never log PII beyond UUID" rule are documented.
- [ ] No new dependency is introduced.
- [ ] Nothing from CLAUDE.md "What NOT to build in v1" appears in scope (no admin panel,
      automated moderation, push/in-app notifications, buyer emails, Celery, or JWKS caching).

# Spec Review: 10-chat

## Verdict
BLOCKED

---

## Blockers

### B1 — `conversations.listing_id` FK is `ON DELETE CASCADE` instead of `ON DELETE SET NULL`

**Location:** "Backend — SQLAlchemy models" (Conversation model) and "Alembic migration"

**Issue:** The spec defines `conversations.listing_id` with `ondelete="CASCADE"` in the SQLAlchemy model:
```python
listing_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("listings.id", ondelete="CASCADE"), nullable=False)
```
And in the migration:
```python
sa.ForeignKeyConstraint(['listing_id'], ['listings.id'], ondelete='CASCADE'),
```
With CASCADE, deleting a listing would delete all its conversations. This destroys chat history and dispute records.

**Conflicts with:** `.claude/docs/SCHEMA.md` — "Conversations are archived (not deleted) when listing is deleted — needed for dispute history." And `Spec 06 — Schema`, "conversations" section — `listing_id UUID REFERENCES listings(id) ON DELETE SET NULL` and "Column notes: `listing_id` uses `ON DELETE SET NULL` — conversation row survives listing deletion. `listing_id` becomes NULL. This is intentional: dispute history and chat history must be preserved."

**Fix:** Change both the SQLAlchemy model and Alembic migration to `ondelete="SET NULL"`. The `listing_id` column must also be nullable (`nullable=True`, no `NOT NULL` annotation) to allow the NULL state after listing deletion.

---

### B2 — Alembic migration re-creates tables already created in Spec 06

**Location:** "Alembic migration" section

**Issue:** The spec creates a new Alembic migration that runs `op.create_table('conversations', ...)` and `op.create_table('messages', ...)`. Both tables are already created in Spec 06's migration `alembic/versions/0001_initial_schema.py`. Running this migration against a DB that has already run `0001_initial_schema.py` would fail immediately with `psycopg.errors.DuplicateTable: relation "conversations" already exists`.

**Conflicts with:** `Spec 06 — Schema`, "Alembic Migration" section — `op.create_table('conversations', ...)` and `op.create_table('messages', ...)` are both present, along with their indexes and FKs.

**Fix:** Remove the "Alembic migration" section and the migration file from "Files to create". No new migration is needed for this spec — the tables already exist. If the `conversations` / `messages` models in the codebase differ from Spec 06 (e.g. due to the CASCADE vs SET NULL issue above), a new migration should only contain `ALTER TABLE` statements for those columns, not a full table re-creation.

---

### B3 — SQLAlchemy models for `Conversation` and `Message` re-created with conflicting FK semantics

**Location:** "Backend — SQLAlchemy models" section and "Files to create"

**Issue:** The spec lists `backend/app/models/conversation.py` and `backend/app/models/message.py` as files to create. Both files are already defined and fully specified in Spec 06. The spec 10 versions introduce conflicting FK semantics (`CASCADE` vs `SET NULL` on `listing_id`) and use `Mapped[]` typed syntax rather than the `Column()` style used in Spec 06. A developer implementing this spec would either overwrite the Spec 06 model files (breaking B1) or face a conflict they cannot resolve without referencing both specs.

**Conflicts with:** `Spec 06 — Schema`, "SQLAlchemy Models" section — `backend/app/models/conversation.py` and `backend/app/models/message.py` are both listed as files to create, with full model definitions using `Column()` style.

**Fix:** Remove `backend/app/models/conversation.py` and `backend/app/models/message.py` from "Files to create" and "Backend — SQLAlchemy models". Reference Spec 06 instead: "Models already defined in Spec 06 — use as-is." If the Mapped[] style is preferred, note that as a style change to make in Spec 06's models, not a new definition here.

---

## Minor gaps

### M1 — `get_messages` returns inconsistent types (ORM objects vs dicts)

**Location:** "Backend — conversation service", `get_messages` function

**Issue:** When the cache is cold, `get_messages` returns `result.scalars().all()` — a list of `Message` ORM objects. When the cache is warm, it returns `json.loads(cached)` — a list of plain dicts. The FastAPI router declares `response_model=list[MessageOut]` which handles both at serialization time, but the function's own return annotation `list[Message]` is incorrect for the cache-warm path. This will cause type-checker confusion and could lead to subtle bugs if the function is called from a context that doesn't go through FastAPI serialization.

**Fix:** Either always return dicts (serialize before caching and after DB fetch, skip ORM objects entirely), or return ORM objects from both paths by deserializing cache hits back into `MessageOut` Pydantic objects before returning.

---

### M2 — `send_message` uses module-level Redis import; other endpoints use `Depends(get_redis)`

**Location:** "Backend — conversation service", `send_message` and `get_messages` functions

**Issue:** `chat_service.py` accesses Redis via `from app.core.redis import redis` as a module-level import. The passkey endpoint in Spec 08 uses `redis=Depends(get_redis)` injected into the router and passed to the service. This inconsistency means if the Redis connection is not ready at module import time (e.g. during testing or cold boot), the chat service will fail differently than the passkey service.

**Fix:** Either pass Redis as an argument to each service function (matching Spec 08's pattern), or document why chat uses module-level access while passkey uses DI.

---

### M3 — `ConversationOut` exposes `first_message_notified`

**Location:** "Backend — Pydantic schemas", `ConversationOut`

**Issue:** `first_message_notified` is an internal tracking flag used to prevent duplicate emails. Including it in the public response leaks implementation details to clients with no user-facing value.

**Fix:** Remove `first_message_notified` from `ConversationOut`. It does not need to be client-visible.

---

### M4 — DoD item for contact-info leakage is untestable as written

**Location:** "Definition of done", last item

**Issue:** "DB confirms no contact info leakage in API responses (manual inspection of GET /conversations/{id}/messages response)" — "manual inspection" is not a verifiable criterion. Two developers cannot agree on pass/fail for this.

**Fix:** Replace with: "No `email`, `phone`, or `avatar_url` fields appear in `GET /conversations/{id}/messages` response — confirm by reading the `MessageOut` schema definition."

---

### M5 — Security Rule 9 — `SUPABASE_SERVICE_ROLE_KEY` used in a request handler

**Location:** "Backend — conversation service", `send_message` function; "Security considerations"

**Issue:** `send_message` calls `supabase_admin.fetch_user_email` (which uses `SUPABASE_SERVICE_ROLE_KEY`) inside a regular authenticated request handler. CLAUDE.md Rule 9 states: "`SUPABASE_SERVICE_ROLE_KEY` — background jobs only, never in request handlers." The spec's security section acknowledges this but argues it is "server-side only" — this does not satisfy the rule.

**Note:** The same violation exists in Spec 09's webhook handler (`handle_webhook` calls `fetch_user_email`). This appears to be a pre-existing project-level design tension, not introduced solely by this spec. However, this spec extends that pattern to a regular auth'd request (not even a webhook). Flag for project-level resolution before implementation begins on either spec.

**Fix for this spec:** Either accept the violation and amend the rule in CLAUDE.md to "background jobs and server-only request handlers," or restructure the first-message email to be sent from a background task (e.g. `asyncio.create_task`) that runs outside the request-response cycle.

---

### M6 — `get_or_create_conversation` does not check `listing.deleted_at`

**Location:** "Backend — conversation service", `get_or_create_conversation`

**Issue:** The function checks `not listing.is_available` and raises 404 "Listing not found." A deleted listing (`is_available=FALSE`, `deleted_at IS NOT NULL`) would correctly fail this check, but the error message "Listing not found." is inaccurate — the listing exists but is deleted. Not a correctness issue but a UX gap.

**Fix (MINOR):** Return 410 Gone or a more accurate message like "This listing is no longer available." Alternatively, explicitly check `listing.deleted_at IS NOT NULL` and return a distinct error.

---

## Security check

| # | Rule | Status | Note |
|---|------|--------|------|
| 1 | Seller contact info never exposed | ✓ | MessageOut contains no contact fields; bodies are free text (content moderation concern, not API concern) |
| 2 | Razorpay webhook HMAC verified | — | Not applicable to chat |
| 3 | Unrecognised webhook events return 200 | — | Not applicable to chat |
| 4 | Supabase session in httpOnly cookies | ✓ | All endpoints use `verify_token` dependency |
| 5 | Ownership validated before mutations | ✓ | `_assert_participant` called in all read/write service functions |
| 6 | Images direct to Cloudinary | — | Chat has no image uploads |
| 7 | Parameterized queries only | ✓ | All queries use SQLAlchemy ORM; no f-string SQL |
| 8 | CORS restricted to FRONTEND_URL | — | Established in Spec 07, not this spec's responsibility |
| 9 | SERVICE_ROLE_KEY in background jobs only | ✗ | `fetch_user_email` called from `send_message` request handler. Same violation pre-exists in Spec 09 webhook handler. Project-level design decision needed. |
| 10 | PASSKEY_HMAC_SECRET never logged | — | Not applicable to chat |
| 11 | hmac.compare_digest for comparisons | — | No hash comparisons in chat |
| 12 | Cancelled transactions never reopened | — | Not applicable to chat |
| 13 | Piracy reports hide listing immediately | — | Moderation is manual via Supabase dashboard; not a chat concern |

---

## Duplication check

- **SQLAlchemy models** (`backend/app/models/conversation.py`, `backend/app/models/message.py`): fully defined in Spec 06 and re-defined here with conflicting FK semantics. See B3.
- **Alembic migration** for `conversations` and `messages`: fully defined in Spec 06 `0001_initial_schema.py` and re-created here. See B2.
- **`conversations` and `messages` table schemas** in "Data model" section: already fully defined in `.claude/docs/SCHEMA.md` and Spec 06. Reproducing them here is acceptable as a reference, but the reproduction introduces a B1-level error in the FK definition.

---

## Definition of done check

- Item: "Redis cache key `chat:{conversation_id}` is present after first GET and absent after a send or mark-read" — testable and specific. ✓
- Item: "polls every 4 seconds (verify in browser network tab)" — testable. ✓
- Item: "DB confirms no contact info leakage (manual inspection)" — untestable. See M4.
- Item: "Alembic migration runs cleanly: `alembic upgrade head` ... `alembic downgrade -1` drops both tables" — this item will fail after B2 is fixed (tables won't be created by this migration). Must be revised after the blocker is resolved.

---

## Implementation readiness

1. **After fixing B2:** Is there any new migration needed at all for this spec? The answer is no — all schema for chat already exists in `0001_initial_schema.py`. The developer must confirm this before starting.

2. **After fixing B1/B3:** Which model file is authoritative — Spec 06's `Column()` style or Spec 10's `Mapped[]` style? The project should pick one style and apply it consistently.

3. **M5 resolution needed:** Should `first_message_notified` email use the service role in a request handler (current approach), or be restructured as an async background task? This decision affects both this spec and Spec 09.

---

## Summary

The spec covers the chat feature comprehensively — polling design, rate limiting, Redis cache invalidation, and the first-message email are all well-specified. The three blockers are all structural conflicts with Spec 06: the `conversations.listing_id` FK must be `SET NULL` (not `CASCADE`) to preserve conversation history on listing deletion, and the Alembic migration and SQLAlchemy model files must not duplicate what Spec 06 already defines. Fix these three issues before implementation begins — the chat logic itself is sound.

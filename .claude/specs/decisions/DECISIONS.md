# DECISIONS.md — Architecture Decisions Log

Every significant decision recorded with reasoning. Prevents re-litigating settled questions.
If you want to change a decision, add a new row — don't delete the old one.

---

| Date | Decision | Reason |
|------|----------|--------|
| Month 1 | Broadened from textbook to study material marketplace | Notes and modules are often more valuable than books to students. Expands supply immediately without any architectural change. |
| Month 1 | Disallowed pirated/photocopied content explicitly | Copyright liability risk. Printed PDFs and bulk photocopies are common but create legal exposure. Policy stated in project overview and T&C. |
| Month 1 | `listing_type` CHECK constraint at DB level | Low effort, prevents invalid values from any code path including direct DB writes |
| Month 1 | `UNIQUE(transaction_id, rated_by)` on seller_ratings | Prevents duplicate ratings without application-level guards |
| Month 1 | Moderation via Supabase dashboard, no admin panel | V1 volume is low enough for manual moderation. Admin panel is premature. |
| Month 1 | `listing_type` field (BOOK/NOTES/MODULE/BUNDLE) | Allows filtering without fragmenting search results into separate sections |
| Month 1 | Unified search stream across listing types | Fragmented sections hurt liquidity. Student searching "JEE Physics" wants all material types in one stream. |
| Month 1 | Meetup-only exchange, no shipping | Simplifies trust model, no logistics dependency, OLX behaviour already familiar |
| Month 1 | Single account for buying and selling | OLX model — simpler UX, one dashboard |
| Month 1 | JavaScript over TypeScript | Faster to build, team preference |
| Month 1 | OAuth only (Google), no email/password | Eliminates password hashing, email OTP, account recovery flows |
| Month 1 | `is_verified` = OAuth email verified, not Aadhaar | Aadhaar integration is out of scope for v1 |
| Month 1 | Prices in rupees not paise | Simpler for Indian study material prices (whole numbers). Paise only at Razorpay API boundary. |
| Month 1 | Platform fee floor not round | `math.floor` avoids float edge cases when fee is introduced |
| Month 1 | Subject as free text with dropdown defaults | Enforcing a fixed subject list is too rigid for the variety of Indian exam material |
| Month 1 | Removed `is_featured` | Simplifies v1, featured listings deferred |
| Month 1 | CLASS_11_12 split into CLASS_9/10/11/12 | More accurate categorisation, students think by class not band |
| Month 1 | WHERE + ILIKE search, no vector/similarity | Sufficient for v1 volume, zero additional infrastructure |
| Month 1 | Parameterized queries only | SQL injection prevention at ORM level |
| Month 1 | Chat rate limit 100/hour not 30 | 30 was too restrictive for active negotiation conversations |
| Month 1 | Email only on first message per conversation | Prevents seller inbox spam, one notification is enough |
| Month 1 | 8-digit passkey not 6-digit | 100M combinations vs 1M — meaningfully harder to guess |
| Month 1 | HMAC-SHA256 not Argon2 for passkey | Passkey is not a user password. Rate-limited by Redis. HMAC is fast and sufficient. |
| Month 1 | `hmac.compare_digest` not `==` | Constant-time comparison prevents timing attacks |
| Month 1 | Passkey on listing not on transaction | Seller needs passkey before knowing which buyer will show up |
| Month 1 | Passkey generated at listing creation | Seller must have passkey ready before any buyer arrives. Secure — passkey is hashed, not plaintext. |
| Month 1 | DB constraint narrowed | Only block `is_available=TRUE AND sold_at IS NOT NULL`. Paused/suspended listings valid with `is_available=FALSE AND sold_at=NULL`. |
| Month 1 | Late webhooks always refund, never reopen | Reopening cancelled transactions creates race conditions. Refund is safe and unconditional. |
| Month 1 | Seller email cooldown 6h per listing | Prevents inbox spam from multiple abandoned checkouts on same listing |
| Month 1 | Payment link expiry 15 minutes | Synchronised with APScheduler cancellation window. Razorpay rejects late payments automatically. |
| Month 1 | No `disputed` transaction status | Disputed state is per-buyer-per-listing, tracked in Redis. No transaction exists until payment succeeds. |
| Month 1 | Three transaction statuses only | `initiated`, `released`, `cancelled`. Simple, unambiguous, matches the actual flow. |
| Month 1 | `UNIQUE INDEX ... WHERE status='initiated'` | Prevents payment link spam — same buyer can't generate infinite links for same listing |
| Month 1 | `FOR UPDATE SKIP LOCKED` at payment initiation | Minor concurrent write guard. Real protection is the atomic listing UPDATE in webhook Step 8. |
| Month 1 | Webhook Step 8 as winner-selection | Atomic `UPDATE ... WHERE is_available=TRUE RETURNING id` — only one concurrent payment can succeed. |
| Month 1 | Refund on concurrent payment | Second buyer's payment comes in after listing already sold. Refund immediately, no manual action needed. |
| Month 1 | Supabase Auth over custom JWT | Eliminates auth router, password hashing, token issuance. FastAPI only verifies. |
| Month 1 | JWKS over static JWT secret | ES256 asymmetric — handles Supabase key rotation automatically |
| Month 1 | SSR for public pages, TanStack Query for client state | SEO on listing pages via RSC; polling impossible with SSR |
| Month 1 | Polling over WebSockets for chat | Simpler infra; 4s delay acceptable for marketplace chat |
| Month 1 | Razorpay over Stripe | Native UPI, net banking, wallets for India |
| Month 1 | Razorpay Route for seller payouts | Money never sits with platform. 0% fee config means instant 100% to seller. |
| Month 1 | Supabase Postgres over MongoDB | Relational data; payment logic needs ACID transactions |
| Month 1 | psycopg3 over psycopg2 | Built for async Python; FastAPI is async |
| Month 1 | APScheduler over Celery | One job doesn't justify a separate worker process |
| Month 1 | Cloudinary over S3 | Free tier, auto image optimisation, no IAM setup |
| Month 1 | Resend over SES | Free tier, 10-min setup, only 2 email types needed |
| Month 1 | JWKS caching deferred to month 2 | Low traffic makes it unnecessary in v1. Adds complexity now. |
| Month 1 | No in-app notifications v1 | Email sufficient. Reduces frontend complexity significantly. |
| Month 1 | Split CLAUDE.md into core + docs/ | Claude Code warned 50.6k chars > 40k performance threshold. Core CLAUDE.md now ~12k chars. |
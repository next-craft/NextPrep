# Spec Review: 07-auth

## Verdict
NEEDS FIXES

No blockers. Seven minor gaps — three of which are in implementation-critical sections
(error handling, response interceptor, cross-spec path conflict) that would cause real
developer confusion or silent failures if unaddressed.

---

## Blockers
No blockers.

---

## Minor gaps

### M1 — `get_jwks()` network failure becomes HTTP 500, not 401/503
**Location:** "Backend — `backend/app/core/security.py`"
**Issue:** `get_jwks()` calls `requests.get(JWKS_URL).json()` with no error handling. If
the Supabase JWKS endpoint is unreachable (network blip, Supabase outage), this raises
`requests.ConnectionError` or similar — not `JWTError`. The `except JWTError` block does
not catch it, so FastAPI returns an unhandled HTTP 500 instead of a clean 401 or 503.
AUTH.md says "Do not rewrite or simplify this function", so this is a known v1 limitation,
but a developer should know before they start that auth failures during Supabase downtime
produce 500s, not 401s, and plan their logging accordingly.
**Fix:** Add a note directly in the spec explaining this behaviour: "If Supabase is
unreachable, `get_jwks()` raises a network exception that is not caught by `except JWTError`.
This will return HTTP 500 in v1. Log at ERROR level in `backend/app/core/logging.py`
monitoring. Do not fix by rewriting `verify_token` — JWKS error handling is deferred to
month 2 alongside caching."

---

### M2 — Auth callback file path conflicts with Spec 02 "Files to create"
**Location:** "Files to create"
**Issue:** This spec correctly defines `frontend/app/(auth)/auth/callback/route.js` (URL:
`/auth/callback`). Spec 02 (`02-user-flows.md`) "Files to create" lists
`frontend/app/(auth)/callback/page.jsx` — which produces URL `/callback`, not
`/auth/callback`. Both specs use `redirectTo: .../auth/callback` in their `signInWithOAuth`
calls. A developer starting from spec 02's file list would create the wrong file at the
wrong path and the OAuth redirect would 404.
**Fix:** Add a note in this spec's "Files to create" section: "NOTE: Spec 02 lists this
file incorrectly as `app/(auth)/callback/page.jsx`. The correct path is
`app/(auth)/auth/callback/route.js` (URL: `/auth/callback`) and it must be a Route Handler
(`route.js`), not a page component, because `exchangeCodeForSession` must run server-side
before any HTML is rendered."

---

### M3 — `api.js` has no 401 response interceptor
**Location:** "Frontend — `frontend/lib/api.js`"
**Issue:** The Axios instance has a request interceptor that attaches the token, but no
response interceptor. If a token expires between the request interceptor running and the
FastAPI response arriving (race during long requests, or a clock skew edge case), FastAPI
returns 401. The frontend has no defined behaviour — TanStack Query surfaces it as an
error but there is no redirect-to-login or token-refresh logic. A developer implementing
this would either silently show a generic error or leave the user stuck.
**Fix:** Add a response interceptor section:
```javascript
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Session expired or invalid — redirect to login
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)
```
Or at minimum, document: "On 401 from FastAPI, the caller (TanStack Query mutation) is
responsible for redirecting to `/login`. No global interceptor is required if all mutations
handle errors via `onError`." Pick one — a developer needs to know which.

---

### M4 — `security.py` and `config.py` both independently load the same env vars
**Location:** "Backend — `backend/app/core/security.py`" and "Backend — `backend/app/core/config.py`"
**Issue:** `security.py` calls `load_dotenv()` and defines `SUPABASE_URL` and
`PASSKEY_HMAC_SECRET` via `os.getenv()`. `config.py` also calls `load_dotenv()` and
defines those same names. Any module that imports `from app.core.config import SUPABASE_URL`
and any module that calls `security.verify_token()` has two independent env var reads that
could diverge if `config.py` is refactored. AUTH.md is authoritative for `security.py` so
that file stays as-is, but the spec should clarify: `config.py` is for application-wide
config; `security.py` loads its own because AUTH.md says it must stand alone. Otherwise a
developer will "clean up the duplication" by having `security.py` import from `config.py`
and break the "Do not rewrite" contract.
**Fix:** Add a note in the `config.py` section: "Do not refactor `security.py` to import
from `config.py`. `security.py` is canonical as written in AUTH.md and must remain
self-contained."

---

### M5 — No DoD item for logout clearing the session
**Location:** "Definition of done"
**Issue:** The spec documents `supabase.auth.signOut()` and the sign-out flow, but there
is no DoD item verifying that logout works end-to-end: session cookies cleared, protected
routes reject the user afterward.
**Fix:** Add:
- `[ ] After `supabase.auth.signOut()`, a Server Component calling `supabase.auth.getUser()` returns `null` and the protected page redirects to `/login``
- `[ ] After logout, browser DevTools → Application → Cookies shows Supabase session cookies removed`

---

### M6 — `Files to modify` lists `frontend/constants/` with "no changes"
**Location:** "Files to modify"
**Issue:** `frontend/constants/ — no changes; auth uses no constants from here` is not a
file modification — it's a negative statement. It adds noise to an otherwise useful section
and a developer might mistakenly open that directory looking for something to change.
**Fix:** Remove the `frontend/constants/` line entirely. Files to modify should only list
files that actually change.

---

### M7 — DB trigger SQL duplicated across AUTH.md, Spec 06, and Spec 07
**Location:** "Supabase Project Setup — Step 3"
**Issue:** The full trigger SQL (`handle_new_user` function + `on_auth_user_created` trigger)
appears identically in `AUTH.md`, `spec 06-schema.md`, and now `spec 07-auth.md`. Three
copies means three places to update if the schema ever changes (e.g., adding a new column
to the INSERT). Spec 06 is the canonical schema spec and already owns this trigger.
**Fix:** Replace the full SQL block in this spec with a reference: "The DB trigger SQL
(`handle_new_user` + `on_auth_user_created`) is fully defined in Spec 06 (Schema),
'Trigger — auto-create public.users on signup'. Run it once in the Supabase SQL editor.
Do not duplicate it here." Keep the trigger failure detection query since it's operational
context for the auth flow.

---

## Security check

| # | Rule | Status | Note |
|---|------|--------|------|
| 1 | Seller contact info never exposed | — | Not applicable — no seller data returned in auth responses |
| 2 | Razorpay webhook HMAC verified | — | Not applicable to auth spec |
| 3 | Unrecognised webhook events return 200 | — | Not applicable to auth spec |
| 4 | Supabase session in httpOnly cookies | ✓ | `@supabase/ssr` enforced; localStorage explicitly prohibited |
| 5 | Ownership validated before mutations | — | No mutations in auth layer |
| 6 | Images direct to Cloudinary | — | Not applicable to auth spec |
| 7 | Parameterized queries only | — | No DB queries in auth layer |
| 8 | CORS restricted to FRONTEND_URL | ✓ | Stated in security considerations; `backend/app/main.py` in files-to-modify |
| 9 | SERVICE_ROLE_KEY in background jobs only | ✓ | Explicitly called out; not present in any auth file |
| 10 | PASSKEY_HMAC_SECRET never logged | ✓ | Logging section explicitly lists it as never-log |
| 11 | hmac.compare_digest for comparisons | ✓ | `verify_passkey` uses it; `verify_token` uses jose library internally |
| 12 | Cancelled transactions never reopened | — | Not applicable to auth spec |
| 13 | Piracy reports hide listing immediately | — | Not applicable to auth spec |

---

## Duplication check

- **DB trigger SQL** — appears in full in `AUTH.md`, `06-schema.md`, and `07-auth.md`. Spec 06 is the canonical owner. See M7.
- **Backend `.env` and frontend `.env.local` blocks** — reproduced verbatim from `CLAUDE.md`. Acceptable for implementation convenience (a developer shouldn't need to context-switch to find env vars), but maintainers should note that CLAUDE.md is authoritative.

---

## Definition of done check

- M5 above: no DoD item for logout.
- No DoD item for: "Callback route returns redirect to `/login?error=auth_failed` when `code` param is missing or `exchangeCodeForSession` fails" — the spec documents this path in the code but doesn't verify it.
- All other DoD items are specific and testable.

---

## Implementation readiness

1. **`backend/app/main.py` CORS setup** — The spec says "modify `main.py` — set up CORS with `FRONTEND_URL` only" but shows no code. A developer creating this file from scratch has no template. Add the FastAPI CORS middleware snippet:
   ```python
   from fastapi.middleware.cors import CORSMiddleware
   app.add_middleware(
       CORSMiddleware,
       allow_origins=[FRONTEND_URL],
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```
   Without this, the first API call from the browser will silently fail with a CORS error that looks like a network error — easy to misdiagnose.

2. **How do Server Components call protected FastAPI endpoints?** The spec says `api.js` is "not used in Server Components" but doesn't show an alternative. If the dashboard or any SSR page needs to call a protected endpoint server-side, what is the pattern? This would need `getSession()` from `createServerSupabaseClient()` to extract the token, then a direct `fetch` with the Authorization header. Add a "Server Component protected API call" example or explicitly state "no Server Component in this project calls a protected FastAPI endpoint — all protected calls originate from Client Components via api.js".

Both are MINOR — implementation can proceed with reasonable assumptions, but would save a developer time.

---

## Summary

The spec is structurally sound and faithfully reproduces the canonical auth implementation from AUTH.md. The most important fix is M2 (callback route path conflict with spec 02) — a developer starting fresh from both specs would create the wrong file. M3 (no 401 response interceptor) and the missing `main.py` CORS snippet are the next priority, as both would cause hard-to-diagnose failures during integration testing. The duplication issues (M4, M7) are cleanup-grade and can be addressed alongside the required fixes.

# Spec 07: Auth

## Purpose

This spec covers the complete authentication layer for Study Material Exchange India. Auth is handled entirely by Supabase — Google OAuth only, no email/password. FastAPI never issues, signs, or refreshes tokens; it only verifies JWTs that Supabase already issued. The frontend uses `@supabase/ssr` to manage sessions in httpOnly cookies and forwards the Supabase access token as a `Bearer` header on every protected API request. A single Postgres trigger in Supabase auto-creates a `public.users` row on first Google OAuth signup, pulling the user's name, avatar, and email-verified status from Google's OAuth metadata. This spec documents every file, function, and configuration decision required to implement auth end-to-end — from the Google OAuth button to a verified `user["sub"]` UUID in a FastAPI route handler.

---

## Depends on

- Spec 01 (Overview) — Google OAuth only, no email/password, one account per user
- Spec 06 (Schema) — `public.users` table definition, DB trigger
- `.claude/docs/AUTH.md` — canonical `verify_token`, passkey hashing, Supabase client setup, DB trigger SQL

---

## Scope

**In scope:**
- Google OAuth login and logout flows (frontend)
- Supabase session management in httpOnly cookies via `@supabase/ssr`
- Next.js middleware for session refresh on every request
- `lib/supabase/client.js` (Client Components) and `lib/supabase/server.js` (Server Components)
- `lib/api.js` — Axios instance with auth interceptor that attaches `Bearer` token
- Auth callback route — `app/(auth)/auth/callback/route.js`
- Login page — `app/(auth)/login/page.jsx`
- Backend `verify_token` dependency function in `backend/app/core/security.py`
- Passkey hashing and verification in `backend/app/core/security.py`
- DB trigger `on_auth_user_created` — runs once in Supabase dashboard
- Environment variables required for auth on both frontend and backend
- How Server Components check auth and redirect unauthenticated users
- How Client Components get the access token for API calls
- Error handling and logging for JWT failures

**Out of scope:**
- Email/password auth — not in v1, never
- Phone OTP — not in v1
- Aadhaar verification — not in v1
- JWKS caching — deferred to month 2
- Session refresh token rotation details (handled by Supabase, not application code)
- Razorpay Route seller onboarding (separate spec)
- Row Level Security in Supabase (ownership enforced in application code, not DB policy)
- Any `/auth/*` FastAPI routes — there are none

---

## How Auth Works (End-to-End)

```
User clicks "Sign in with Google"
→ supabase.auth.signInWithOAuth({ provider: 'google' })
→ Supabase redirects to Google consent screen
→ Google redirects back to /auth/callback with a code
→ Supabase exchanges code for session (access_token + refresh_token)
→ @supabase/ssr stores session in httpOnly cookies
→ Next.js middleware runs supabase.auth.getUser() on every request to refresh session
→ Server Components / Client Components read session from cookies

For protected API calls:
→ Client reads session: supabase.auth.getSession()
→ Attaches: Authorization: Bearer <access_token>
→ FastAPI receives token
→ verify_token() fetches Supabase JWKS, verifies ES256 signature, returns payload
→ Route handler receives user = { "sub": "<uuid>", "email": "...", ... }
→ user["sub"] is the user UUID — used in all DB queries
```

No FastAPI routes handle any part of this flow. Auth is purely between the browser and Supabase.

---

## Supabase Project Setup

These steps are done once in the Supabase dashboard before any code is deployed.

### 1 — Enable Google OAuth provider

In Supabase dashboard → Authentication → Providers → Google:
- Enable Google provider
- Set **Client ID** and **Client Secret** from Google Cloud Console
- Set **Redirect URL** in Google Cloud Console: `https://<your-supabase-project>.supabase.co/auth/v1/callback`

### 2 — Configure redirect URLs (Supabase dashboard)

Authentication → URL Configuration:
- **Site URL:** `http://localhost:3000` (development) / `https://yourdomain.com` (production)
- **Redirect URLs:** add `http://localhost:3000/auth/callback` and `https://yourdomain.com/auth/callback`

### 3 — Run DB trigger SQL (once, in Supabase SQL editor)

This SQL is NOT in Alembic — Alembic cannot access the `auth` schema.

```sql
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.users (id, full_name, avatar_url, is_verified)
    VALUES (
        NEW.id,
        COALESCE(NEW.raw_user_meta_data->>'full_name', 'User'),
        NEW.raw_user_meta_data->>'avatar_url',
        COALESCE((NEW.raw_user_meta_data->>'email_verified')::boolean, FALSE)
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();
```

**Why `SECURITY DEFINER`:** The trigger runs as the function owner (postgres superuser), not the calling role. Required to write to `public.users` from a trigger on `auth.users`.

**What gets populated:**
- `id` — same UUID as `auth.users.id`
- `full_name` — from Google's `full_name` OAuth metadata. Falls back to `'User'`.
- `avatar_url` — from Google profile photo
- `is_verified` — `TRUE` for Google users (Google verifies email). Not Aadhaar, not manual OTP.
- `city`, `seller_rating`, `total_sales` — left at defaults; updated later via profile editing

**Trigger failure detection:**

```sql
-- Run in Supabase SQL editor after initial setup — should return 0 rows
SELECT id FROM auth.users au
WHERE NOT EXISTS (
    SELECT 1 FROM public.users pu WHERE pu.id = au.id
);
```

If this returns rows, the trigger did not fire — re-run the trigger SQL above.

---

## Backend — `backend/app/core/security.py`

Do not rewrite or simplify the `verify_token` function. The implementation below is canonical.

```python
# backend/app/core/security.py
from fastapi import Header, HTTPException
from jose import jwt, JWTError
from dotenv import load_dotenv
import requests
import hmac
import hashlib
import logging
import os

logger = logging.getLogger(__name__)
load_dotenv()

SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
PASSKEY_HMAC_SECRET = os.getenv("PASSKEY_HMAC_SECRET")


def get_jwks():
    return requests.get(JWKS_URL).json()


def verify_token(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing token")

    try:
        token = authorization.split(" ")[1]
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")

        jwks = get_jwks()
        key = next(
            (k for k in jwks["keys"] if k["kid"] == kid),
            None
        )

        if not key:
            logger.warning("JWKS public key not found for kid=%s", kid)
            raise HTTPException(status_code=401, detail="Public key not found")

        payload = jwt.decode(
            token,
            key,
            algorithms=["ES256"],
            audience="authenticated"
        )
        return payload

    except JWTError as e:
        logger.warning("JWT verification failed: %s", str(e))
        raise HTTPException(status_code=401, detail="Invalid token")


def hash_passkey(passkey: str, listing_id: str) -> str:
    message = f"{passkey}{listing_id}".encode()
    return hmac.new(
        PASSKEY_HMAC_SECRET.encode(),
        message,
        hashlib.sha256
    ).hexdigest()


def verify_passkey(submitted: str, listing_id: str, stored_hash: str) -> bool:
    expected = hash_passkey(submitted, listing_id)
    return hmac.compare_digest(expected, stored_hash)
```

**Key decisions:**
- Algorithm is **ES256** (asymmetric) — not HS256. Supabase signs with ES256.
- `get_jwks()` makes a live network call per request in v1. JWKS caching is deferred to month 2 (see DECISIONS.md). Acceptable at low traffic.
- `payload["sub"]` is the user UUID — used in all DB queries as the primary user identifier.
- `payload["email"]` is available from the JWT when needed server-side.
- `hmac.compare_digest` prevents timing attacks on passkey verification. Never use `==`.
- `PASSKEY_HMAC_SECRET` must be 32+ random bytes hex. Never logged. Never in responses.

**Usage in protected routes:**

```python
from app.core.security import verify_token
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db

@router.post("/listings")
async def create_listing(
    data: ListingCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token),
):
    seller_id = user["sub"]  # always the user UUID
    return await listing_service.create(db, seller_id, data)
```

**What does NOT exist in FastAPI:**
- No `/auth/register`
- No `/auth/login`
- No `/auth/refresh`
- No `/auth/logout`
- No password hashing
- No JWT creation or signing

---

## Backend — `backend/app/core/config.py`

```python
# backend/app/core/config.py
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")
PASSKEY_HMAC_SECRET = os.getenv("PASSKEY_HMAC_SECRET")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
```

---

## Frontend — Supabase Client Files

### `frontend/lib/supabase/client.js` — for Client Components

```javascript
// frontend/lib/supabase/client.js
import { createBrowserClient } from '@supabase/ssr'

export const createClient = () =>
  createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  )
```

### `frontend/lib/supabase/server.js` — for Server Components

```javascript
// frontend/lib/supabase/server.js
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

export const createServerSupabaseClient = () => {
  const cookieStore = cookies()
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    {
      cookies: {
        get: (name) => cookieStore.get(name)?.value,
      },
    }
  )
}
```

### `frontend/middleware.js` — session refresh on every request

```javascript
// frontend/middleware.js
import { createServerClient } from '@supabase/ssr'
import { NextResponse } from 'next/server'

export async function middleware(request) {
  const response = NextResponse.next({ request: { headers: request.headers } })

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    {
      cookies: {
        get: (name) => request.cookies.get(name)?.value,
        set: (name, value, options) =>
          response.cookies.set({ name, value, ...options }),
        remove: (name, options) =>
          response.cookies.set({ name, value: '', ...options }),
      },
    }
  )

  // Refresh session — keeps access_token alive, rotates refresh_token
  await supabase.auth.getUser()

  return response
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}
```

The middleware runs on every request. `getUser()` refreshes the session silently if the access token is expired. No redirect logic here — redirects are handled in individual page components.

---

## Frontend — Auth Actions

### Login (Google OAuth)

```javascript
// Called from login page or any "Sign in" button
const supabase = createClient()

await supabase.auth.signInWithOAuth({
  provider: 'google',
  options: {
    redirectTo: `${window.location.origin}/auth/callback`,
  },
})
```

### Auth Callback Route

```javascript
// frontend/app/(auth)/auth/callback/route.js
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'

export async function GET(request) {
  const { searchParams, origin } = new URL(request.url)
  const code = searchParams.get('code')
  const next = searchParams.get('next') ?? '/'

  if (code) {
    const cookieStore = cookies()
    const supabase = createServerClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
      {
        cookies: {
          get: (name) => cookieStore.get(name)?.value,
          set: (name, value, options) => cookieStore.set({ name, value, ...options }),
          remove: (name, options) => cookieStore.set({ name, value: '', ...options }),
        },
      }
    )

    const { error } = await supabase.auth.exchangeCodeForSession(code)

    if (!error) {
      return NextResponse.redirect(`${origin}${next}`)
    }
  }

  // Auth failed — redirect to login with error
  return NextResponse.redirect(`${origin}/login?error=auth_failed`)
}
```

### Logout

```javascript
const supabase = createClient()
await supabase.auth.signOut()
// redirect to /login or / after signOut
```

### Get session token in Client Components (for FastAPI calls)

```javascript
const supabase = createClient()
const { data: { session } } = await supabase.auth.getSession()
const accessToken = session?.access_token
// → Authorization: Bearer <accessToken>
```

### Auth check in Server Components

```javascript
import { createServerSupabaseClient } from '@/lib/supabase/server'
import { redirect } from 'next/navigation'

// In any Server Component or page that requires auth:
const supabase = createServerSupabaseClient()
const { data: { user } } = await supabase.auth.getUser()

if (!user) redirect('/login')

// user.id is the UUID — same as user["sub"] in FastAPI
```

---

## Frontend — `frontend/lib/api.js`

Axios instance that automatically attaches the Supabase access token to every request.

```javascript
// frontend/lib/api.js
import axios from 'axios'
import { createClient } from '@/lib/supabase/client'

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
})

api.interceptors.request.use(async (config) => {
  const supabase = createClient()
  const { data: { session } } = await supabase.auth.getSession()
  if (session?.access_token) {
    config.headers.Authorization = `Bearer ${session.access_token}`
  }
  return config
})

export default api
```

Used in Client Components and TanStack Query mutation functions. Not used in Server Components — those call the backend directly with the server-side session when needed.

---

## Frontend — Login Page

```jsx
// frontend/app/(auth)/login/page.jsx
'use client'
import { createClient } from '@/lib/supabase/client'

export default function LoginPage() {
  const supabase = createClient()

  const handleGoogleLogin = async () => {
    await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
      },
    })
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="flex flex-col items-center gap-6 p-8">
        <h1 className="text-2xl font-semibold">NextPrep</h1>
        <p className="text-muted-foreground text-sm">
          Buy and sell JEE, NEET, UPSC, and CA books — from students, for students.
        </p>
        <button
          onClick={handleGoogleLogin}
          className="flex items-center gap-2 rounded-md border px-4 py-2 text-sm font-medium hover:bg-accent"
        >
          Continue with Google
        </button>
      </div>
    </div>
  )
}
```

---

## Environment Variables

### Backend `.env`

```
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db
REDIS_URL=redis://default:pass@host:6379
RAZORPAY_KEY_ID=rzp_live_xxx
RAZORPAY_KEY_SECRET=xxx
RAZORPAY_WEBHOOK_SECRET=xxx
PASSKEY_HMAC_SECRET=<32+ random bytes hex>
CLOUDINARY_CLOUD_NAME=xxx
CLOUDINARY_API_KEY=xxx
CLOUDINARY_API_SECRET=xxx
RESEND_API_KEY=re_xxx
FRONTEND_URL=http://localhost:3000
ENVIRONMENT=development
```

### Frontend `.env.local`

```
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
NEXT_PUBLIC_API_URL=http://localhost:8000/v1
API_URL=http://localhost:8000/v1
```

**Hard rules:**
- `RAZORPAY_KEY_SECRET`, `SUPABASE_SERVICE_ROLE_KEY`, `PASSKEY_HMAC_SECRET` — backend only, never frontend, never committed
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` — safe to expose in browser. It is the public anon key, not the service role key.
- `SUPABASE_SERVICE_ROLE_KEY` — background jobs only (not used in auth flow at all). Never in request handlers.

---

## Logging

Every JWT failure must be logged. Every successful token verification must NOT log the token.

```python
# In verify_token — already included in the canonical implementation above:

# On missing key:
logger.warning("JWKS public key not found for kid=%s", kid)

# On JWTError:
logger.warning("JWT verification failed: %s", str(e))

# Never log:
# - The token string
# - payload contents beyond the user UUID
# - PASSKEY_HMAC_SECRET
```

---

## Files to create

```
frontend/lib/supabase/client.js
frontend/lib/supabase/server.js
frontend/lib/api.js
frontend/middleware.js
frontend/app/(auth)/login/page.jsx
frontend/app/(auth)/auth/callback/route.js
backend/app/core/security.py
backend/app/core/config.py
```

## Files to modify

```
backend/app/main.py             — import security, set up CORS with FRONTEND_URL only
frontend/constants/             — no changes; auth uses no constants from here
```

## New dependencies

### Frontend (npm)
```
@supabase/ssr         — Supabase Auth for Next.js App Router
@supabase/supabase-js — Supabase JS client (peer dep of @supabase/ssr)
axios                 — HTTP client with interceptor support
```

### Backend (pip)
```
python-jose[cryptography]  — JWT decode with ES256 support (jose library)
python-dotenv              — load .env in development
requests                   — synchronous JWKS fetch (get_jwks is sync; acceptable in v1)
```

Add to `backend/pyproject.toml` under `[project] dependencies`.

---

## Security considerations

The following security rules from CLAUDE.md apply directly to this spec:

- **Rule 3** — Return 200 for unrecognised webhook events. Auth is not in the webhook handler, but the pattern of returning 200 for unknown events applies across all Supabase Auth webhooks if any are added later.
- **Rule 4** — Supabase session in httpOnly cookies, never localStorage. `@supabase/ssr` handles this automatically — do not use `createBrowserClient` with `localStorage` storage option.
- **Rule 8** — CORS: allow only `FRONTEND_URL` in production, never `*`. Set in `backend/app/main.py` using `FRONTEND_URL` env var.
- **Rule 9** — `SUPABASE_SERVICE_ROLE_KEY` — background jobs only. Never used in `verify_token`, never in request handlers. Not needed for auth verification at all.
- **Rule 10** — `PASSKEY_HMAC_SECRET` never logged, never in responses. Already enforced by only using it inside `hash_passkey` and `verify_passkey`.
- **Rule 11** — `hmac.compare_digest` for all hash comparisons. `verify_passkey` uses this; `verify_token` does not compare hashes directly — jose library handles signature verification internally.
- **Rule 2 (implied)** — Never log JWT strings. `logger.warning("JWT verification failed: %s", str(e))` logs the exception message, not the token itself.

---

## Definition of done

- [ ] `frontend/lib/supabase/client.js` exists and exports `createClient`
- [ ] `frontend/lib/supabase/server.js` exists and exports `createServerSupabaseClient`
- [ ] `frontend/middleware.js` exists, calls `supabase.auth.getUser()`, and exports the `config` matcher
- [ ] `frontend/lib/api.js` exists, creates an Axios instance with `NEXT_PUBLIC_API_URL` as base URL, and attaches `Authorization: Bearer <token>` via interceptor
- [ ] `frontend/app/(auth)/login/page.jsx` exists and renders a "Continue with Google" button that triggers `signInWithOAuth`
- [ ] `frontend/app/(auth)/auth/callback/route.js` exists and exchanges the OAuth code for a session via `exchangeCodeForSession`
- [ ] Clicking "Continue with Google" redirects to Google consent screen
- [ ] After Google consent, browser is redirected to `/auth/callback`, session cookies are set, and user is redirected to `/`
- [ ] After login, a Server Component calling `supabase.auth.getUser()` returns the correct user object (not null)
- [ ] After login, `api.js` interceptor attaches `Authorization: Bearer <token>` — verifiable in browser DevTools Network tab
- [ ] `backend/app/core/security.py` exists with the canonical `verify_token` function
- [ ] `verify_token` is used as a FastAPI `Depends` on at least one protected route and returns `{"sub": "<uuid>", "email": "...", ...}` for a valid Supabase token
- [ ] A request with no `Authorization` header returns HTTP 401 with `{"detail": "Missing token"}`
- [ ] A request with a malformed or expired token returns HTTP 401 with `{"detail": "Invalid token"}`
- [ ] JWT failures are logged at WARNING level — verify in Railway/local logs
- [ ] JWT strings are never logged — confirm by grepping for `logger.*token` in `security.py`
- [ ] DB trigger `on_auth_user_created` fires on first Google login and creates a `public.users` row
- [ ] After first login, `SELECT * FROM public.users WHERE id = '<new-user-uuid>'` returns a row with `full_name` from Google, `is_verified = TRUE`
- [ ] `SUPABASE_SERVICE_ROLE_KEY` does not appear in `security.py` or any auth-related file
- [ ] `PASSKEY_HMAC_SECRET` is loaded from env and never logged — grep confirms no `log.*PASSKEY` in codebase
- [ ] CORS in `backend/app/main.py` allows only `FRONTEND_URL`, not `*`, in production environment

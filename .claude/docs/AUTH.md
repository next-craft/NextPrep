# AUTH.md — Authentication Implementation

Auth is fully handled by Supabase. Google OAuth only. No email/password. No custom JWT.
FastAPI only verifies tokens Supabase already issued.

---

## How it works

Supabase signs JWTs with ES256 (asymmetric). The backend fetches Supabase's public keys
from the JWKS endpoint and verifies incoming tokens against them.
Key rotation is handled automatically — no code change needed.

---

## Backend — canonical `verify_token`

Do not rewrite or simplify this function.

```python
# backend/app/core/security.py
from fastapi import Header, HTTPException
from jose import jwt, JWTError
from dotenv import load_dotenv
import requests
import logging
import os

logger = logging.getLogger(__name__)
load_dotenv()

SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"


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
```

**Key details:**
- Algorithm is ES256 (asymmetric) — not HS256
- `payload["sub"]` is the user UUID — use in all DB queries
- `payload["email"]` is available if needed
- `get_jwks()` makes a live network call per request in v1 — acceptable for low traffic
- JWKS caching deferred to month 2

**Usage in protected routes:**
```python
from app.core.security import verify_token
from fastapi import Depends

@router.post("/listings")
async def create_listing(
    data: ListingCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(verify_token),
):
    seller_id = user["sub"]
    return await listing_service.create(db, seller_id, data)
```

**What does NOT exist in the backend:**
- No `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`
- No password hashing
- No JWT creation or signing
- No email/password flows

---

## Passkey hashing (also in security.py)

```python
import hmac
import hashlib

PASSKEY_HMAC_SECRET = os.getenv("PASSKEY_HMAC_SECRET")

def hash_passkey(passkey: str, listing_id: str) -> str:
    message = f"{passkey}{listing_id}".encode()
    return hmac.new(
        PASSKEY_HMAC_SECRET.encode(),
        message,
        hashlib.sha256
    ).hexdigest()

def verify_passkey(submitted: str, listing_id: str, stored_hash: str) -> bool:
    expected = hash_passkey(submitted, listing_id)
    return hmac.compare_digest(expected, stored_hash)  # constant-time, prevents timing attacks
```

HMAC-SHA256 chosen over Argon2 because the passkey is not a user password — it's
a short-lived, system-generated token rate-limited by Redis. Speed is appropriate here.
`hmac.compare_digest` prevents timing attacks. Never use `==` for hash comparison.

---

## Frontend — Supabase Auth setup

```javascript
// lib/supabase/client.js — for Client Components
import { createBrowserClient } from '@supabase/ssr'

export const createClient = () =>
  createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  )
```

```javascript
// lib/supabase/server.js — for Server Components
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

export const createServerSupabaseClient = () => {
  const cookieStore = cookies()
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    { cookies: { get: (name) => cookieStore.get(name)?.value } }
  )
}
```

```javascript
// middleware.js — refreshes session on every request
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
        set: (name, value, options) => response.cookies.set({ name, value, ...options }),
        remove: (name, options) => response.cookies.set({ name, value: '', ...options }),
      },
    }
  )
  await supabase.auth.getUser()
  return response
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}
```

```javascript
// Auth actions — call Supabase directly, never go through FastAPI

// Google OAuth login
await supabase.auth.signInWithOAuth({
  provider: 'google',
  options: { redirectTo: `${window.location.origin}/auth/callback` }
})

// Logout
await supabase.auth.signOut()

// Get token for FastAPI calls (Client Components)
const { data: { session } } = await supabase.auth.getSession()
const accessToken = session?.access_token  // → Authorization: Bearer <token>

// Get user in Server Component
const supabase = createServerSupabaseClient()
const { data: { user } } = await supabase.auth.getUser()
if (!user) redirect('/login')
```

```javascript
// lib/api.js — Axios instance with auth interceptor
import axios from 'axios'
import { createClient } from '@/lib/supabase/client'

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL
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

---

## Database trigger — auto-create public.users on signup

Run this SQL in Supabase dashboard once during setup.

```sql
CREATE TABLE public.users (
  id            UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  full_name     TEXT NOT NULL,
  city          TEXT,
  avatar_url    TEXT,
  is_verified   BOOLEAN DEFAULT FALSE,
  seller_rating NUMERIC(3,2),
  total_sales   INTEGER DEFAULT 0,
  created_at    TIMESTAMPTZ DEFAULT now()
);

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

`is_verified` = Google OAuth email verified. Not Aadhaar. Not manual email OTP.
Google verifies email automatically so most users will have `is_verified = TRUE`.
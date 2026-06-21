import { createServerClient } from '@supabase/ssr'
import { NextResponse } from 'next/server'

// Next.js only runs middleware from a root `middleware.js` exporting `middleware`.
// Refreshes the Supabase session cookie on every matched navigation.
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

  await supabase.auth.getUser()

  return response
}

export const config = {
  // Exclude static assets and the OAuth callback (which runs its own
  // exchangeCodeForSession — no need for a redundant getUser round-trip there).
  matcher: ['/((?!_next/static|_next/image|favicon.ico|auth/callback).*)'],
}

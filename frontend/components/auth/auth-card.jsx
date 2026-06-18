'use client'

/* ──────────────────────────────────────────────────────────────────────
   AuthCard — the focused glass sign-in surface (right column).

   States: idle → loading (redirecting to Google) → error (?error=auth_failed
   from the OAuth callback, which the old page silently dropped).

   On mobile the brand panel is hidden, so the card carries a compact
   headline + mini proof strip of its own (lg:hidden) for a dedicated,
   non-stacked small-screen experience.
   ────────────────────────────────────────────────────────────────────── */

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { createClient } from '@/lib/supabase/client'
import { Loader2, ShieldCheck, KeyRound, MapPin, BadgeCheck, AlertCircle } from 'lucide-react'
import { m, useReducedMotion, Stagger, StaggerItem } from '@/components/shared/motion'
import { AnimatePresence } from 'framer-motion'
import { SPRING_SOFT, EASE } from '@/lib/motion'

function GoogleIcon({ className = 'h-5 w-5' }) {
  return (
    <svg viewBox="0 0 48 48" className={className} aria-hidden="true">
      <path
        fill="#FFC107"
        d="M43.611 20.083H42V20H24v8h11.303c-1.649 4.657-6.08 8-11.303 8-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 12.955 4 4 12.955 4 24s8.955 20 20 20 20-8.955 20-20c0-1.341-.138-2.65-.389-3.917z"
      />
      <path
        fill="#FF3D00"
        d="M6.306 14.691l6.571 4.819C14.655 15.108 18.961 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 16.318 4 9.656 8.337 6.306 14.691z"
      />
      <path
        fill="#4CAF50"
        d="M24 44c5.166 0 9.86-1.977 13.409-5.192l-6.19-5.238C29.211 35.091 26.715 36 24 36c-5.202 0-9.619-3.317-11.283-7.946l-6.522 5.025C9.505 39.556 16.227 44 24 44z"
      />
      <path
        fill="#1976D2"
        d="M43.611 20.083H42V20H24v8h11.303c-.792 2.237-2.231 4.166-4.087 5.571.001-.001 6.189 5.238 6.189 5.238l-.025-.018C36.971 39.205 44 34 44 24c0-1.341-.138-2.65-.389-3.917z"
      />
    </svg>
  )
}

const SECURITY = [
  { icon: ShieldCheck, label: 'Encrypted session' },
  { icon: KeyRound, label: 'Passkey deals' },
  { icon: MapPin, label: 'India only' },
]

export default function AuthCard() {
  const supabase = createClient()
  const reduced = useReducedMotion()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)

  // The OAuth callback redirects here with ?error=auth_failed on failure.
  // Read it client-side (no useSearchParams → no Suspense boundary needed).
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('error')) setError(true)
  }, [])

  const handleGoogleLogin = async () => {
    setError(false)
    setLoading(true)
    const { error: oauthError } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    })
    // On success the browser is already navigating to Google; only reached on a
    // synchronous failure to even start the redirect.
    if (oauthError) {
      setLoading(false)
      setError(true)
    }
  }

  return (
    <m.div
      initial={reduced ? { opacity: 0 } : { opacity: 0, scale: 0.96, y: 16 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={SPRING_SOFT}
      className="relative z-10 w-full max-w-md"
    >
      {/* soft glow pooled beneath the card */}
      <div
        aria-hidden
        className="absolute -inset-4 -z-10 rounded-[2rem] opacity-70 blur-2xl"
        style={{ background: 'radial-gradient(circle at 50% 30%, rgba(197,131,65,0.28), transparent 70%)' }}
      />

      <div className="rounded-3xl border border-white/50 bg-card/75 p-8 shadow-warm-lg backdrop-blur-xl sm:p-10">
        {/* inner top highlight for glass depth */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-px rounded-t-3xl bg-gradient-to-r from-transparent via-white/80 to-transparent"
        />

        <Stagger gap={0.07} delay={0.1}>
          {/* wordmark */}
          <StaggerItem as="div" className="flex items-center justify-between">
            <Link
              href="/"
              className="font-display text-2xl font-semibold tracking-tight"
              aria-label="NextPrep home"
            >
              Next<span className="text-primary">Prep</span>
            </Link>
            <span className="rounded-full border border-border bg-secondary px-2.5 py-0.5 text-[11px] font-medium text-secondary-foreground">
              🇮🇳 India
            </span>
          </StaggerItem>

          {/* mobile-only value line (brand panel is hidden < lg) */}
          <StaggerItem
            as="p"
            className="mt-6 text-sm leading-relaxed text-muted-foreground lg:hidden"
          >
            Buy &amp; sell JEE, NEET, UPSC &amp; CA study material with verified students near you.
          </StaggerItem>

          <StaggerItem
            as="h2"
            className="mt-6 font-display text-3xl font-semibold tracking-tight text-foreground"
          >
            Continue to NextPrep
          </StaggerItem>
          <StaggerItem as="p" className="mt-2 text-sm leading-relaxed text-muted-foreground">
            One account for buying and selling. Sign in to pick up where you left off.
          </StaggerItem>

          {/* error state */}
          <AnimatePresence>
            {error && (
              <m.div
                role="alert"
                initial={reduced ? { opacity: 0 } : { opacity: 0, height: 0, y: -6 }}
                animate={{ opacity: 1, height: 'auto', y: 0 }}
                exit={reduced ? { opacity: 0 } : { opacity: 0, height: 0, y: -6 }}
                transition={{ duration: 0.25, ease: EASE.warm }}
                className="mt-5 flex items-start gap-2.5 overflow-hidden rounded-xl border border-destructive/30 bg-destructive/10 px-3.5 py-3 text-sm text-destructive"
              >
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>Sign-in didn&apos;t complete. Please try again.</span>
              </m.div>
            )}
          </AnimatePresence>

          {/* primary CTA */}
          <StaggerItem
            as="button"
            type="button"
            onClick={handleGoogleLogin}
            disabled={loading}
            aria-busy={loading}
            whileHover={reduced || loading ? undefined : { scale: 1.015, y: -1 }}
            whileTap={reduced || loading ? undefined : { scale: 0.985 }}
            className="group mt-7 flex h-14 w-full items-center justify-center gap-3 rounded-2xl border border-light_bronze-500/60 bg-card text-base font-semibold text-foreground shadow-warm transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-70"
          >
            {loading ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin text-primary" />
                Securing your session…
              </>
            ) : (
              <>
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-white shadow-sm transition-transform group-hover:scale-105">
                  <GoogleIcon className="h-5 w-5" />
                </span>
                Continue with Google
              </>
            )}
          </StaggerItem>

          <StaggerItem as="p" className="mt-4 flex items-start gap-2 text-xs leading-relaxed text-muted-foreground">
            <BadgeCheck className="mt-0.5 h-4 w-4 shrink-0 text-success" />
            No password to remember. Google only confirms you&apos;re a real student — we never see
            your inbox or your contacts.
          </StaggerItem>

          {/* security row */}
          <StaggerItem
            as="div"
            className="mt-7 grid grid-cols-3 gap-2 border-t border-border pt-6"
          >
            {SECURITY.map((s) => {
              const Icon = s.icon
              return (
                <span
                  key={s.label}
                  className="flex flex-col items-center gap-1.5 text-center text-[11px] font-medium text-muted-foreground"
                >
                  <Icon className="h-4 w-4 text-primary" />
                  {s.label}
                </span>
              )
            })}
          </StaggerItem>
        </Stagger>
      </div>

      {/* terms */}
      <p className="mt-6 px-2 text-center text-xs leading-relaxed text-muted-foreground">
        By continuing you agree to our{' '}
        <Link href="/terms" className="link-underline font-medium text-foreground">
          Terms
        </Link>{' '}
        and{' '}
        <Link href="/privacy" className="link-underline font-medium text-foreground">
          Privacy Policy
        </Link>
        .
      </p>
    </m.div>
  )
}

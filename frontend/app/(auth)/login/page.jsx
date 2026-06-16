'use client'
import { useState } from 'react'
import Link from 'next/link'
import { createClient } from '@/lib/supabase/client'
import { MapPin, KeyRound, ShieldCheck } from 'lucide-react'
import { m, useReducedMotion, Stagger, StaggerItem } from '@/components/shared/motion'
import { SPRING_SOFT } from '@/lib/motion'

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

export default function LoginPage() {
  const supabase = createClient()
  const reduced = useReducedMotion()
  const [loading, setLoading] = useState(false)

  const handleGoogleLogin = async () => {
    setLoading(true)
    await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
      },
    })
  }

  return (
    <div className="container flex min-h-[calc(100vh-4rem)] items-center justify-center py-12">
      <m.div
        initial={reduced ? { opacity: 0 } : { opacity: 0, scale: 0.94, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={SPRING_SOFT}
        className="card w-full max-w-md p-8 text-center"
      >
        <Stagger gap={0.07} delay={0.12}>
          <StaggerItem>
            <Link href="/" className="font-display text-2xl font-semibold tracking-tight">
              Next<span className="text-primary">Prep</span>
            </Link>
          </StaggerItem>
          <StaggerItem as="h1" className="mt-6 font-display text-2xl font-semibold">
            Welcome
          </StaggerItem>
          <StaggerItem as="p" className="mt-2 text-sm text-muted-foreground">
            Buy and sell JEE, NEET, UPSC &amp; CA study material — from students, for students.
          </StaggerItem>

          <StaggerItem
            as="button"
            onClick={handleGoogleLogin}
            disabled={loading}
            whileHover={{ scale: 1.015 }}
            whileTap={{ scale: 0.98 }}
            className="btn-primary mt-8 w-full"
          >
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white">
              <GoogleIcon className="h-4 w-4" />
            </span>
            {loading ? 'Redirecting…' : 'Continue with Google'}
          </StaggerItem>

          <StaggerItem as="p" className="mt-4 text-xs text-muted-foreground">
            We use Google only to verify you&apos;re a real student. No passwords, no spam.
          </StaggerItem>
        </Stagger>

        <Stagger
          gap={0.08}
          delay={0.4}
          className="mt-8 grid grid-cols-3 gap-3 border-t border-border pt-6 text-xs text-muted-foreground"
        >
          <StaggerItem as="span" className="flex flex-col items-center gap-1.5">
            <MapPin className="h-4 w-4 text-primary" /> Meet locally
          </StaggerItem>
          <StaggerItem as="span" className="flex flex-col items-center gap-1.5">
            <KeyRound className="h-4 w-4 text-primary" /> Passkey pay
          </StaggerItem>
          <StaggerItem as="span" className="flex flex-col items-center gap-1.5">
            <ShieldCheck className="h-4 w-4 text-primary" /> Verified
          </StaggerItem>
        </Stagger>
      </m.div>
    </div>
  )
}

'use client'
import { useState } from 'react'
import Link from 'next/link'
import { createClient } from '@/lib/supabase/client'
import { MapPin, KeyRound, ShieldCheck } from 'lucide-react'
import { m, useReducedMotion, Stagger, StaggerItem } from '@/components/shared/motion'
import { SPRING_SOFT } from '@/lib/motion'

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden="true">
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.4 29.3 35 24 35c-7.2 0-13-5.8-13-13s5.8-13 13-13c3.3 0 6.3 1.2 8.6 3.3l5.7-5.7C34.9 3.5 29.7 1.5 24 1.5 11.6 1.5 1.5 11.6 1.5 24S11.6 46.5 24 46.5 46.5 36.4 46.5 24c0-1.2-.1-2.4-.4-3.5z" />
      <path fill="#FF3D00" d="M3.7 12.7l6.6 4.8C12.1 14 17.6 11 24 11c3.3 0 6.3 1.2 8.6 3.3l5.7-5.7C34.9 5 29.7 3 24 3 16 3 9 7.4 3.7 12.7z" transform="translate(-1.5 -1.5)" />
      <path fill="#4CAF50" d="M24 46.5c5.6 0 10.7-1.9 14.6-5.2l-6.7-5.5C29.7 37.4 27 38.5 24 38.5c-5.3 0-9.7-2.6-11.3-7l-6.6 5.1C9 42.5 16 46.5 24 46.5z" transform="translate(0 0)" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.3-2.3 4.2-4.2 5.5l6.7 5.5C41.9 35.6 46.5 30.5 46.5 24c0-1.2-.1-2.4-.9-3.5z" transform="translate(0 0)" />
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
            <GoogleIcon /> {loading ? 'Redirecting…' : 'Continue with Google'}
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

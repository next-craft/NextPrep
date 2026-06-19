'use client'

/* ──────────────────────────────────────────────────────────────────────
   Login — "The Reading Room"

   Editorial split-screen sign-in:
     • Left  (lg+)  : BrandShowcase — value + proof
     • Right (all)  : AuthCard — focused Google sign-in with live states
     • Behind both  : the shared Atmosphere (same living aurora as the rest
                      of the site), which tracks the pointer itself.

   Reduced-motion users get a still, fully legible page (the Atmosphere gates
   its own pointer listener and infinite loops).
   ────────────────────────────────────────────────────────────────────── */

import Atmosphere from '@/components/shared/atmosphere'
import AuthNavbar from '@/components/auth/auth-navbar'
import BrandShowcase from '@/components/auth/brand-showcase'
import AuthCard from '@/components/auth/auth-card'

export default function LoginPage() {
  return (
    <section className="relative isolate flex min-h-screen w-full items-center overflow-hidden">
      <Atmosphere />
      <AuthNavbar />

      <div className="relative z-10 mx-auto grid w-full max-w-7xl grid-cols-1 items-center gap-8 px-5 pb-12 pt-24 lg:grid-cols-2 lg:gap-6 lg:px-10 lg:py-12">
        <BrandShowcase />
        <div className="flex justify-center lg:justify-end">
          <AuthCard />
        </div>
      </div>
    </section>
  )
}

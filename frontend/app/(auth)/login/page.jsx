'use client'

/* ──────────────────────────────────────────────────────────────────────
   Login — "The Reading Room"

   Editorial split-screen sign-in:
     • Left  (lg+)  : BrandShowcase — value + proof + drifting listing cards
     • Right (all)  : AuthCard — focused Google sign-in with live states
     • Behind both  : AuthAtmosphere — living warm aurora + particles

   A single pointer listener feeds normalized motion values down to the
   atmosphere and floating cards, so the whole scene shares one cheap source
   of parallax. Reduced-motion users get a still, fully legible page (the
   pointer handler no-ops, infinite loops are gated in each child).
   ────────────────────────────────────────────────────────────────────── */

import { useCallback } from 'react'
import { useMotionValue, useSpring } from 'framer-motion'
import { useReducedMotion } from '@/components/shared/motion'
import { SPRING_SOFT } from '@/lib/motion'
import AuthAtmosphere from '@/components/auth/auth-atmosphere'
import AuthNavbar from '@/components/auth/auth-navbar'
import BrandShowcase from '@/components/auth/brand-showcase'
import AuthCard from '@/components/auth/auth-card'

export default function LoginPage() {
  const reduced = useReducedMotion()

  // Raw pointer position normalized to [-0.5, 0.5]; smoothed by a soft spring.
  const rawX = useMotionValue(0)
  const rawY = useMotionValue(0)
  const px = useSpring(rawX, SPRING_SOFT)
  const py = useSpring(rawY, SPRING_SOFT)

  const handlePointerMove = useCallback(
    (e) => {
      if (reduced) return
      const { innerWidth, innerHeight } = window
      rawX.set(e.clientX / innerWidth - 0.5)
      rawY.set(e.clientY / innerHeight - 0.5)
    },
    [reduced, rawX, rawY]
  )

  return (
    <section
      onPointerMove={handlePointerMove}
      className="relative isolate flex min-h-screen w-full items-center overflow-hidden"
    >
      <AuthAtmosphere px={px} py={py} />
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

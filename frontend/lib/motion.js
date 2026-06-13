/* ──────────────────────────────────────────────────────────────────────
   NextPrep — motion system
   Warm, weighty, paper-like motion. Things settle gently, like cards on a
   desk. Spring where natural, eased where precise. Shared tokens + variants
   so motion stays consistent across the whole app.

   Only `transform` / `opacity` are ever animated (60fps, no layout thrash).
   ────────────────────────────────────────────────────────────────────── */

// Durations (seconds)
export const DURATION = {
  fast: 0.15,
  base: 0.3,
  slow: 0.5,
}

// Easings
export const EASE = {
  // warm ease-out — overshoot-free, settles softly
  warm: [0.22, 1, 0.36, 1],
  inOut: [0.4, 0, 0.2, 1],
}

// Springs for interactive / weighty elements
export const SPRING = { type: 'spring', stiffness: 260, damping: 30 }
export const SPRING_SOFT = { type: 'spring', stiffness: 200, damping: 26 }
export const SPRING_SNAPPY = { type: 'spring', stiffness: 380, damping: 28 }

// ── Base variants ──────────────────────────────────────────────────────
export const fadeIn = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { duration: DURATION.base, ease: EASE.warm } },
}

export const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: DURATION.base, ease: EASE.warm } },
}

export const scaleIn = {
  hidden: { opacity: 0, scale: 0.96 },
  show: { opacity: 1, scale: 1, transition: { duration: DURATION.base, ease: EASE.warm } },
}

export const slideDown = {
  hidden: { opacity: 0, y: -10 },
  show: { opacity: 1, y: 0, transition: { duration: DURATION.base, ease: EASE.warm } },
}

// ── Stagger ──────────────────────────────────────────────────────────────
export const staggerContainer = (stagger = 0.06, delayChildren = 0) => ({
  hidden: {},
  show: { transition: { staggerChildren: stagger, delayChildren } },
})

export const staggerItem = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: DURATION.base, ease: EASE.warm } },
}

// Reduced-motion equivalents — fade only, no transform
export const fadeOnly = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { duration: DURATION.fast } },
}

// viewport config for scroll-reveal
export const VIEWPORT = { once: true, margin: '-64px' }

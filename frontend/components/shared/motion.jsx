'use client'

/* ──────────────────────────────────────────────────────────────────────
   NextPrep — reusable motion primitives (client-only)

   All components consume the shared tokens/variants in lib/motion.js and
   respect prefers-reduced-motion (fade-only, no transform) via Motion's
   useReducedMotion(). LazyMotion + domMax keeps the bundle lean while still
   supporting layout animations (ImageUploader reorder, row exit, etc).
   ────────────────────────────────────────────────────────────────────── */

import { LazyMotion, domMax, m, useReducedMotion } from 'framer-motion'
import { DURATION, EASE, VIEWPORT } from '@/lib/motion'

/** App-wide feature provider. Mounted once near the root. */
export function MotionProvider({ children }) {
  return (
    <LazyMotion features={domMax} strict={false}>
      {children}
    </LazyMotion>
  )
}

/**
 * Reveal — fade (+ optional upward settle) on mount or when scrolled into view.
 * Animates transform/opacity only. Reduced motion → fade only.
 */
export function Reveal({
  children,
  className,
  as = 'div',
  delay = 0,
  y = 12,
  duration = DURATION.base,
  inView = false,
  once = true,
  style,
  ...rest
}) {
  const reduced = useReducedMotion()
  const Comp = m[as] || m.div
  const hidden = reduced ? { opacity: 0 } : { opacity: 0, y }
  const shown = { opacity: 1, y: 0 }
  const transition = { duration, ease: EASE.warm, delay }
  const trigger = inView
    ? { whileInView: shown, viewport: { ...VIEWPORT, once } }
    : { animate: shown }

  return (
    <Comp
      className={className}
      style={style}
      initial={hidden}
      transition={transition}
      {...trigger}
      {...rest}
    >
      {children}
    </Comp>
  )
}

/**
 * Stagger — container that reveals its <StaggerItem> children in sequence,
 * on mount or in view. Reduced motion collapses the stagger to 0.
 */
export function Stagger({
  children,
  className,
  as = 'div',
  gap = 0.06,
  delay = 0,
  inView = false,
  once = true,
  style,
  ...rest
}) {
  const reduced = useReducedMotion()
  const Comp = m[as] || m.div
  const container = {
    hidden: {},
    show: {
      transition: { staggerChildren: reduced ? 0 : gap, delayChildren: reduced ? 0 : delay },
    },
  }
  const trigger = inView
    ? { whileInView: 'show', viewport: { ...VIEWPORT, once } }
    : { animate: 'show' }

  return (
    <Comp
      className={className}
      style={style}
      variants={container}
      initial="hidden"
      {...trigger}
      {...rest}
    >
      {children}
    </Comp>
  )
}

/** StaggerItem — one child of <Stagger>. */
export function StaggerItem({ children, className, as = 'div', y = 12, style, ...rest }) {
  const reduced = useReducedMotion()
  const Comp = m[as] || m.div
  const variants = {
    hidden: reduced ? { opacity: 0 } : { opacity: 0, y },
    show: { opacity: 1, y: 0, transition: { duration: DURATION.base, ease: EASE.warm } },
  }
  return (
    <Comp className={className} style={style} variants={variants} {...rest}>
      {children}
    </Comp>
  )
}

export { m, useReducedMotion }

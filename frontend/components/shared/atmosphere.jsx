'use client'

/* ──────────────────────────────────────────────────────────────────────
   Atmosphere — the single, canonical living background for NextPrep.

   This is the exact background used on /login, now shared site-wide so every
   page sits on the same warm aurora. Layers, back to front:
     1. base wash        — warm cornsilk → papaya vertical gradient
     2. aurora blobs     — 4 large blurred radial glows, slow infinite drift
     3. light sweep      — a soft diagonal highlight that travels across
     4. particle field   — 16 deterministic motes that rise + twinkle
     5. grid + vignette  — faint engraved grid, edge darkening for depth

   Self-contained: it tracks the pointer itself (no parent plumbing) and
   applies a subtle parallax. Only transform / opacity animate. Reduced-motion
   disables the pointer listener and all infinite loops. Decorative only.

   Fixed at z-index -10 so it sits in front of the body background but behind
   the body grain (-1) and all content; scrolling content drifts over it.
   ────────────────────────────────────────────────────────────────────── */

import { useEffect } from 'react'
import { m, useReducedMotion } from '@/components/shared/motion'
import { useMotionValue, useSpring, useTransform } from 'framer-motion'
import { SPRING_SOFT } from '@/lib/motion'

// 16 fixed motes — deterministic so SSR markup matches the client (no hydration drift)
const PARTICLES = [
  { x: '6%', y: '24%', s: 6, delay: 0.0, dur: 14 },
  { x: '14%', y: '66%', s: 4, delay: 1.4, dur: 17 },
  { x: '22%', y: '40%', s: 3, delay: 3.1, dur: 12 },
  { x: '31%', y: '82%', s: 5, delay: 0.7, dur: 19 },
  { x: '42%', y: '16%', s: 3, delay: 2.2, dur: 15 },
  { x: '53%', y: '72%', s: 7, delay: 4.0, dur: 21 },
  { x: '61%', y: '32%', s: 4, delay: 1.0, dur: 16 },
  { x: '69%', y: '58%', s: 3, delay: 3.6, dur: 13 },
  { x: '78%', y: '26%', s: 5, delay: 0.4, dur: 18 },
  { x: '85%', y: '74%', s: 4, delay: 2.7, dur: 20 },
  { x: '92%', y: '46%', s: 6, delay: 1.8, dur: 15 },
  { x: '48%', y: '52%', s: 3, delay: 5.0, dur: 22 },
  { x: '36%', y: '60%', s: 4, delay: 2.0, dur: 14 },
  { x: '74%', y: '12%', s: 3, delay: 3.3, dur: 17 },
  { x: '18%', y: '8%', s: 4, delay: 4.5, dur: 19 },
  { x: '64%', y: '88%', s: 5, delay: 0.9, dur: 16 },
]

function Blob({ className, gradient, animate, transition }) {
  return (
    <m.div
      className={`absolute rounded-full blur-3xl ${className}`}
      style={{ background: gradient, willChange: 'transform' }}
      animate={animate}
      transition={transition}
    />
  )
}

export default function Atmosphere() {
  const reduced = useReducedMotion()

  // Self-contained pointer parallax. Stays at 0 (no listener) under reduced motion.
  const rawX = useMotionValue(0)
  const rawY = useMotionValue(0)
  const px = useSpring(rawX, SPRING_SOFT)
  const py = useSpring(rawY, SPRING_SOFT)

  useEffect(() => {
    if (reduced) return
    const onMove = (e) => {
      rawX.set(e.clientX / window.innerWidth - 0.5)
      rawY.set(e.clientY / window.innerHeight - 0.5)
    }
    window.addEventListener('pointermove', onMove, { passive: true })
    return () => window.removeEventListener('pointermove', onMove)
  }, [reduced, rawX, rawY])

  // Layered depth: blobs drift opposite the cursor, particles ride a touch more.
  const blobX = useTransform(px, [-0.5, 0.5], [22, -22])
  const blobY = useTransform(py, [-0.5, 0.5], [22, -22])
  const dotX = useTransform(px, [-0.5, 0.5], [-36, 36])
  const dotY = useTransform(py, [-0.5, 0.5], [-36, 36])

  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      {/* 1 · base wash */}
      <div className="absolute inset-0 bg-gradient-to-b from-cornsilk via-cornsilk to-papaya_whip" />

      {/* 2 · aurora blobs (one parallax layer holding all four) */}
      <m.div className="absolute inset-0" style={{ x: blobX, y: blobY }}>
        <Blob
          className="-left-[12%] -top-[18%] h-[60vh] w-[60vh]"
          gradient="radial-gradient(circle at 30% 30%, rgba(197,131,65,0.55), rgba(197,131,65,0) 68%)"
          animate={reduced ? undefined : { x: [0, 36, -12, 0], y: [0, -24, 16, 0], scale: [1, 1.08, 0.96, 1] }}
          transition={reduced ? undefined : { duration: 26, repeat: Infinity, ease: 'easeInOut' }}
        />
        <Blob
          className="-right-[14%] top-[6%] h-[58vh] w-[58vh]"
          gradient="radial-gradient(circle at 60% 40%, rgba(172,187,123,0.5), rgba(172,187,123,0) 70%)"
          animate={reduced ? undefined : { x: [0, -30, 14, 0], y: [0, 20, -14, 0], scale: [1, 0.94, 1.1, 1] }}
          transition={reduced ? undefined : { duration: 30, repeat: Infinity, ease: 'easeInOut' }}
        />
        <Blob
          className="bottom-[-20%] left-[24%] h-[62vh] w-[62vh]"
          gradient="radial-gradient(circle at 50% 50%, rgba(242,208,121,0.45), rgba(242,208,121,0) 72%)"
          animate={reduced ? undefined : { x: [0, 22, -18, 0], y: [0, -16, 22, 0], scale: [1, 1.06, 0.92, 1] }}
          transition={reduced ? undefined : { duration: 34, repeat: Infinity, ease: 'easeInOut' }}
        />
        <Blob
          className="bottom-[2%] right-[18%] h-[42vh] w-[42vh]"
          gradient="radial-gradient(circle at 50% 50%, rgba(217,139,106,0.32), rgba(217,139,106,0) 70%)"
          animate={reduced ? undefined : { x: [0, -18, 16, 0], y: [0, 18, -12, 0], scale: [1, 1.1, 0.95, 1] }}
          transition={reduced ? undefined : { duration: 28, repeat: Infinity, ease: 'easeInOut' }}
        />
      </m.div>

      {/* 3 · travelling light sweep */}
      {!reduced && (
        <m.div
          className="absolute -inset-y-1/2 left-0 w-[40%] -rotate-12 blur-2xl"
          style={{
            background:
              'linear-gradient(90deg, rgba(255,253,246,0) 0%, rgba(255,253,246,0.55) 50%, rgba(255,253,246,0) 100%)',
            willChange: 'transform',
          }}
          animate={{ x: ['-30vw', '130vw'] }}
          transition={{ duration: 13, repeat: Infinity, ease: 'easeInOut', repeatDelay: 4 }}
        />
      )}

      {/* 4 · particle field */}
      <m.div className="absolute inset-0" style={{ x: dotX, y: dotY }}>
        {PARTICLES.map((p, i) => (
          <m.span
            key={i}
            className="absolute rounded-full bg-light_bronze-300"
            style={{
              left: p.x,
              top: p.y,
              width: p.s,
              height: p.s,
              opacity: 0.4,
              boxShadow: '0 0 8px rgba(150,98,46,0.5)',
            }}
            animate={reduced ? { opacity: 0.25 } : { y: [0, -26, 0], opacity: [0.15, 0.6, 0.15] }}
            transition={
              reduced ? undefined : { duration: p.dur, repeat: Infinity, ease: 'easeInOut', delay: p.delay }
            }
          />
        ))}
      </m.div>

      {/* 5 · engraved grid + vignette for depth */}
      <div
        className="absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage:
            'linear-gradient(rgba(50,33,15,1) 1px, transparent 1px), linear-gradient(90deg, rgba(50,33,15,1) 1px, transparent 1px)',
          backgroundSize: '56px 56px',
          maskImage: 'radial-gradient(ellipse at center, black 35%, transparent 80%)',
          WebkitMaskImage: 'radial-gradient(ellipse at center, black 35%, transparent 80%)',
        }}
      />
      <div
        className="absolute inset-0"
        style={{
          background: 'radial-gradient(ellipse at center, transparent 55%, rgba(50,33,15,0.10) 100%)',
        }}
      />
    </div>
  )
}

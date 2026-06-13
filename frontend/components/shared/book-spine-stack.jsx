'use client'

/* Landing-page hero decoration. Each spine springs in with a slight rotation
   settle, then drifts in a gentle idle float (paper resting on a desk, caught
   in a draft). Rotation is driven by Motion — not Tailwind — so the inline
   transform from the float/entrance never fights a `rotate-*` class. */

import { m, useReducedMotion } from '@/components/shared/motion'
import { SPRING_SOFT } from '@/lib/motion'

const SPINES = [
  { label: 'HC Verma · Physics', cls: 'bg-light_bronze-400 text-light_bronze-100', rotate: -6, mt: '0' },
  { label: 'NCERT · Class 12', cls: 'bg-tea_green-500 text-tea_green-100', rotate: 3, mt: '-1.5rem' },
  { label: 'Allen · NEET Bio', cls: 'bg-papaya_whip-400 text-light_bronze-100', rotate: -2, mt: '0' },
]

export default function BookSpineStack() {
  const reduced = useReducedMotion()

  return (
    <div className="relative hidden h-72 lg:block">
      <m.div
        className="absolute left-1/2 top-1/2 h-64 w-64 -translate-x-1/2 -translate-y-1/2 rounded-full bg-tea_green-700/50 blur-2xl"
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.8, ease: 'easeOut' }}
      />
      <div className="relative mx-auto flex h-full max-w-sm items-center justify-center gap-4">
        {SPINES.map((s, i) => (
          <m.div
            key={s.label}
            style={{ marginTop: s.mt }}
            animate={
              reduced ? undefined : { y: [0, -7, 0] }
            }
            transition={
              reduced
                ? undefined
                : { duration: 4.5 + i * 0.6, repeat: Infinity, ease: 'easeInOut', delay: i * 0.3 }
            }
          >
            <m.div
              className={`flex h-52 w-32 flex-col justify-end rounded-lg border border-light_bronze-700 p-4 shadow-warm-lg ${s.cls}`}
              initial={reduced ? { opacity: 0 } : { opacity: 0, y: 28, scale: 0.92, rotate: 0 }}
              animate={reduced ? { opacity: 1 } : { opacity: 1, y: 0, scale: 1, rotate: s.rotate }}
              transition={{ ...SPRING_SOFT, delay: 0.15 + i * 0.12 }}
            >
              <span className="font-display text-sm font-semibold leading-tight">{s.label}</span>
            </m.div>
          </m.div>
        ))}
      </div>
    </div>
  )
}

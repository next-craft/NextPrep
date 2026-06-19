'use client'

/* Landing-page hero decoration — a single render of the three exam books
   (JEE Physics, NCERT Class 12, NEET Bio). Floats in with a soft settle, then
   drifts gently, like books resting in mid-air. Reduced-motion → still.
   A warm drop-shadow grounds the transparent PNG over the aurora. */

import Image from 'next/image'
import { m, useReducedMotion } from '@/components/shared/motion'
import { EASE } from '@/lib/motion'

export default function BookSpineStack() {
  const reduced = useReducedMotion()

  return (
    <div className="relative hidden h-72 items-center justify-center lg:flex">
      {/* warm glow pooled behind the books */}
      <m.div
        aria-hidden
        className="absolute left-1/2 top-1/2 h-56 w-80 -translate-x-1/2 -translate-y-1/2 rounded-full bg-tea_green-700/50 blur-3xl"
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.8, ease: 'easeOut' }}
      />

      {/* entrance settle */}
      <m.div
        className="relative w-full max-w-[560px]"
        initial={reduced ? { opacity: 0 } : { opacity: 0, y: 28, scale: 0.94 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.7, ease: EASE.warm, delay: 0.1 }}
      >
        {/* idle float */}
        <m.div
          animate={reduced ? undefined : { y: [0, -10, 0] }}
          transition={reduced ? undefined : { duration: 6, repeat: Infinity, ease: 'easeInOut' }}
        >
          <Image
            src="/hero/books.png"
            alt="JEE Physics, NCERT Class 12 and NEET Biology study books"
            width={2752}
            height={1536}
            sizes="(min-width: 1024px) 560px, 0px"
            className="h-auto w-full object-contain drop-shadow-[0_24px_32px_rgba(50,33,15,0.28)]"
          />
        </m.div>
      </m.div>
    </div>
  )
}

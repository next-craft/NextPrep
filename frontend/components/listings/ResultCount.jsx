'use client'

/* Animates the "{n} results" count — a gentle count-up on mount and a smooth
   number transition when the filtered set size changes. Reduced motion shows
   the final value instantly. */

import { useEffect, useRef, useState } from 'react'
import { animate } from 'framer-motion'
import { useReducedMotion } from '@/components/shared/motion'
import { EASE } from '@/lib/motion'

export default function ResultCount({ count, className }) {
  const reduced = useReducedMotion()
  const [display, setDisplay] = useState(reduced ? count : 0)
  const from = useRef(0)

  useEffect(() => {
    if (reduced) {
      setDisplay(count)
      return
    }
    const controls = animate(from.current, count, {
      duration: 0.5,
      ease: EASE.warm,
      onUpdate: (v) => setDisplay(Math.round(v)),
    })
    from.current = count
    return () => controls.stop()
  }, [count, reduced])

  return (
    <span className={className}>
      {display} {count === 1 ? 'result' : 'results'}
    </span>
  )
}

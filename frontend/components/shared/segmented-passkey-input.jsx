'use client'
import { useEffect, useRef } from 'react'
import { useAnimationControls } from 'framer-motion'
import { cn } from '@/lib/utils'
import { m, useReducedMotion } from '@/components/shared/motion'

/**
 * 8-digit numeric passkey entry. Single controlled input styled as a large
 * monospace field (mobile numeric keyboard, accessible, robust). Sanitises to
 * digits and caps at 8. Each newly typed digit gives the field a subtle scale
 * pulse — emphasis without ever stealing focus.
 */
export default function SegmentedPasskeyInput({
  value,
  onChange,
  disabled = false,
  autoFocus = false,
  id = 'passkey',
  className,
}) {
  const reduced = useReducedMotion()
  const controls = useAnimationControls()
  const prevLen = useRef(value.length)

  useEffect(() => {
    if (!reduced && value.length > prevLen.current) {
      controls.start({ scale: [1, 1.015, 1], transition: { duration: 0.2 } })
    }
    prevLen.current = value.length
  }, [value, reduced, controls])

  const handle = (e) => {
    const digits = e.target.value.replace(/\D/g, '').slice(0, 8)
    onChange(digits)
  }

  return (
    <m.input
      animate={controls}
      id={id}
      name={id}
      value={value}
      onChange={handle}
      disabled={disabled}
      autoFocus={autoFocus}
      inputMode="numeric"
      autoComplete="one-time-code"
      maxLength={8}
      placeholder="••••••••"
      aria-label="8-digit passkey"
      className={cn(
        'h-14 w-full rounded-lg border border-input bg-card text-center font-mono text-2xl font-semibold tracking-[0.5em] text-foreground shadow-sm transition-colors placeholder:tracking-[0.4em] placeholder:text-light_bronze-700 focus-visible:border-ring disabled:cursor-not-allowed disabled:opacity-50',
        className
      )}
    />
  )
}

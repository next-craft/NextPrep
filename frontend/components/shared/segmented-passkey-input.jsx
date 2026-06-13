'use client'
import { cn } from '@/lib/utils'

/**
 * 8-digit numeric passkey entry. Single controlled input styled as a large
 * monospace field (mobile numeric keyboard, accessible, robust). Sanitises to
 * digits and caps at 8.
 */
export default function SegmentedPasskeyInput({
  value,
  onChange,
  disabled = false,
  autoFocus = false,
  id = 'passkey',
  className,
}) {
  const handle = (e) => {
    const digits = e.target.value.replace(/\D/g, '').slice(0, 8)
    onChange(digits)
  }

  return (
    <input
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

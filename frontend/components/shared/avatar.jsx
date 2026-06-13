'use client'
import { useState } from 'react'
import { cn, initials } from '@/lib/utils'

/** Google avatar with graceful initials fallback (on missing src or load error). */
export default function Avatar({ src, name, size = 40, className }) {
  const [errored, setErrored] = useState(false)
  const show = src && !errored

  return (
    <span
      className={cn(
        'inline-flex shrink-0 select-none items-center justify-center overflow-hidden rounded-full border border-border bg-tea_green-600 font-semibold text-tea_green-100',
        className
      )}
      style={{ width: size, height: size }}
    >
      {show ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt={name || 'avatar'}
          width={size}
          height={size}
          referrerPolicy="no-referrer"
          className="h-full w-full object-cover"
          onError={() => setErrored(true)}
        />
      ) : (
        <span style={{ fontSize: Math.round(size * 0.4) }}>{initials(name)}</span>
      )}
    </span>
  )
}

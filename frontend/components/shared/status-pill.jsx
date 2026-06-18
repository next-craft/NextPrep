'use client'

/* ──────────────────────────────────────────────────────────────────────
   NextPrep — "living status" indicators

   Replaces the flat green/red availability badges with status markers that
   *behave* like their meaning, in the warm paper-&-ink palette:

     • Available — soft green pill, a breathing radar dot (the listing is live)
     • Paused    — amber pill, a quiet pause glyph (on hold)
     • Sold      — terracotta pill, a check that stamps in (a completed deal,
                   framed as an accomplishment rather than an error)

   Transform/opacity only; the radar ping is neutralised under
   prefers-reduced-motion by the global CSS reset, and the mount pop is gated
   on useReducedMotion(). Drop-in for ConversationList, the chat header and
   the dashboard selling tab.
   ────────────────────────────────────────────────────────────────────── */

import { Check, Pause, ArrowDownLeft, ArrowUpRight } from 'lucide-react'
import { m, useReducedMotion } from '@/components/shared/motion'
import { SPRING, SPRING_SNAPPY } from '@/lib/motion'
import { cn } from '@/lib/utils'

// status keys come from listingStatus(): 'active' | 'paused' | 'sold'
const STATUS_META = {
  active: { label: 'Available', dot: '#5b8a3c', cls: 'bg-[#eaf1de] text-[#3f6733] ring-[#cad8b0]' },
  paused: { label: 'Paused', dot: '#b07d1e', cls: 'bg-[#fbf1d6] text-[#8a5e12] ring-[#ecd6a0]' },
  sold: { label: 'Sold', dot: '#b3452f', cls: 'bg-[#f7e6e0] text-[#8f3322] ring-[#e4b3a6]' },
}

export default function StatusPill({ status = 'active', className }) {
  const reduced = useReducedMotion()
  const meta = STATUS_META[status] ?? STATUS_META.active
  const live = status === 'active'
  const sold = status === 'sold'
  const paused = status === 'paused'

  return (
    <m.span
      initial={reduced ? { opacity: 0 } : { opacity: 0, scale: 0.85, y: 2 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={SPRING}
      className={cn(
        'inline-flex select-none items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px]',
        'font-semibold uppercase leading-none tracking-wide shadow-sm ring-1 ring-inset',
        meta.cls,
        className
      )}
    >
      <span className="relative flex h-3 w-3 items-center justify-center">
        {sold ? (
          <m.span
            initial={reduced ? false : { scale: 0, rotate: -35 }}
            animate={{ scale: 1, rotate: 0 }}
            transition={{ ...SPRING_SNAPPY, delay: 0.08 }}
            className="flex items-center justify-center"
          >
            <Check className="h-3 w-3" strokeWidth={3.25} />
          </m.span>
        ) : paused ? (
          <Pause className="h-2.5 w-2.5" strokeWidth={0} fill="currentColor" />
        ) : (
          <>
            {/* breathing radar — signals the listing is live */}
            <span
              className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-50"
              style={{ backgroundColor: meta.dot }}
            />
            <span
              className="relative inline-flex h-1.5 w-1.5 rounded-full"
              style={{ backgroundColor: meta.dot }}
            />
          </>
        )}
      </span>
      {meta.label}
    </m.span>
  )
}

// ── Verified transaction tag ───────────────────────────────────────────
// A transaction row only exists once a passkey is confirmed at the meetup,
// so the marker reads as a completed, *verified* exchange — directional
// (purchased ↙ / sold ↗) with a check that pops in.
const ROLE_META = {
  buyer: { label: 'Purchased', Icon: ArrowDownLeft, cls: 'bg-[#eaf1de] text-[#3f6733] ring-[#cad8b0]' },
  seller: { label: 'Sold', Icon: ArrowUpRight, cls: 'bg-[#f3e9da] text-[#7a531c] ring-[#e7d4bf]' },
}

export function VerifiedTag({ role = 'buyer', className }) {
  const reduced = useReducedMotion()
  const meta = ROLE_META[role] ?? ROLE_META.buyer
  const { Icon } = meta

  return (
    <m.span
      initial={reduced ? { opacity: 0 } : { opacity: 0, scale: 0.85, y: 2 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={SPRING}
      className={cn(
        'inline-flex select-none items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px]',
        'font-semibold uppercase leading-none tracking-wide shadow-sm ring-1 ring-inset',
        meta.cls,
        className
      )}
    >
      <m.span
        initial={reduced ? false : { scale: 0, rotate: -25 }}
        animate={{ scale: 1, rotate: 0 }}
        transition={{ ...SPRING_SNAPPY, delay: 0.08 }}
        className="flex items-center justify-center"
      >
        <Icon className="h-3 w-3" strokeWidth={2.75} />
      </m.span>
      {meta.label}
      <Check className="h-3 w-3 opacity-70" strokeWidth={3} />
    </m.span>
  )
}

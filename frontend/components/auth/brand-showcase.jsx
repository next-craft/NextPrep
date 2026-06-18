'use client'

/* ──────────────────────────────────────────────────────────────────────
   BrandShowcase — the left "stage" of the Reading Room.

   Earns the sign-in click by communicating value before the ask, using only
   factual product content (no invented metrics or live counters):
     • eyebrow (what NextPrep is)     • editorial headline + subhead
     • rotating example-search pill   • how-it-works (3 real steps)
     • trust row (real product guarantees)
   ────────────────────────────────────────────────────────────────────── */

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Search, MessageCircle, KeyRound, BadgeCheck, MapPin } from 'lucide-react'
import { m, useReducedMotion, Stagger, StaggerItem } from '@/components/shared/motion'
import { AnimatePresence } from 'framer-motion'
import { EASE } from '@/lib/motion'

// Example queries for the search pill — illustrative search terms, not claims.
const QUERIES = [
  'HC Verma Vol 2',
  'Allen NEET modules',
  'UPSC GS handwritten notes',
  'CA Foundation test series',
  'NCERT Class 12 set',
]

// How it works — each step is a real product guarantee.
const STEPS = [
  { icon: Search, label: 'Find or list', sub: 'Books, notes & modules' },
  { icon: MessageCircle, label: 'Chat & agree', sub: 'Settle the price directly' },
  { icon: KeyRound, label: 'Meet & confirm', sub: 'Verified by passkey' },
]

const TRUST = [
  { icon: BadgeCheck, label: 'Verified sellers' },
  { icon: MapPin, label: 'In-person, India' },
  { icon: KeyRound, label: 'Passkey-confirmed' },
]

function Rotator({ items, reduced, className }) {
  const [i, setI] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setI((n) => (n + 1) % items.length), 2600)
    return () => clearInterval(id)
  }, [items.length])

  return (
    <span className={`relative inline-block ${className}`}>
      <AnimatePresence mode="wait" initial={false}>
        <m.span
          key={i}
          initial={reduced ? { opacity: 0 } : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={reduced ? { opacity: 0 } : { opacity: 0, y: -12 }}
          transition={{ duration: 0.32, ease: EASE.warm }}
          className="inline-block"
        >
          {items[i]}
        </m.span>
      </AnimatePresence>
    </span>
  )
}

export default function BrandShowcase() {
  const reduced = useReducedMotion()

  return (
    <div className="relative hidden flex-col justify-center px-10 py-16 lg:flex xl:px-16">
      <Stagger gap={0.09} delay={0.15} className="relative z-10 max-w-lg">
        {/* eyebrow — what this is */}
        <StaggerItem
          as="div"
          className="inline-flex w-fit items-center gap-2 rounded-full border border-border bg-card/70 px-3 py-1 text-xs font-medium text-muted-foreground backdrop-blur"
        >
          <BadgeCheck className="h-3.5 w-3.5 text-success" />
          Student-to-student · India only
        </StaggerItem>

        {/* headline */}
        <StaggerItem
          as="h1"
          className="mt-6 font-display text-5xl font-semibold leading-[1.04] tracking-tight text-foreground xl:text-6xl"
        >
          Where toppers
          <br />
          <span className="italic text-primary">pass it on.</span>
        </StaggerItem>

        <StaggerItem as="p" className="mt-5 max-w-md text-lg leading-relaxed text-muted-foreground">
          Buy and sell JEE, NEET, UPSC &amp; CA study material with students near you. No shipping,
          no middlemen — just one fair handover.
        </StaggerItem>

        {/* rotating example-search pill → browse */}
        <StaggerItem as="div" className="mt-8">
          <Link
            href="/listings"
            className="group flex w-full max-w-sm items-center gap-3 rounded-2xl border border-border bg-card/70 px-4 py-3 text-left shadow-warm backdrop-blur transition-colors hover:border-light_bronze-500"
          >
            <Search className="h-5 w-5 shrink-0 text-primary" />
            <span className="flex-1 text-sm text-foreground">
              Find <Rotator items={QUERIES} reduced={reduced} className="font-medium text-primary" />
            </span>
            <span className="text-xs font-medium text-muted-foreground transition-transform group-hover:translate-x-0.5">
              Browse →
            </span>
          </Link>
        </StaggerItem>

        {/* how it works — three real steps */}
        <StaggerItem as="ol" className="mt-10 flex gap-3">
          {STEPS.map((s, i) => {
            const Icon = s.icon
            return (
              <li
                key={s.label}
                className="flex-1 rounded-2xl border border-border/70 bg-card/50 p-3.5 backdrop-blur-sm"
              >
                <div className="flex items-center gap-2">
                  <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <Icon className="h-4 w-4" />
                  </span>
                  <span className="font-mono text-xs text-muted-foreground">0{i + 1}</span>
                </div>
                <p className="mt-2.5 text-sm font-semibold text-foreground">{s.label}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">{s.sub}</p>
              </li>
            )
          })}
        </StaggerItem>

        {/* trust row */}
        <StaggerItem as="ul" className="mt-8 flex flex-wrap gap-x-6 gap-y-2">
          {TRUST.map((t) => {
            const Icon = t.icon
            return (
              <li key={t.label} className="flex items-center gap-2 text-sm text-muted-foreground">
                <Icon className="h-4 w-4 text-success" /> {t.label}
              </li>
            )
          })}
        </StaggerItem>
      </Stagger>
    </div>
  )
}

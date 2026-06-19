'use client'

/* "How it works" — a hand-drawn journey. Glass step-cards (no numbers) sit in
   an alternating zigzag on desktop, joined by dashed curvy connectors; on
   mobile they stack down a dashed vertical path. The dashed strokes + warm
   bronze ink echo the site's sketch/paper aesthetic. Reduced-motion → still. */

import { Search, MessageCircle, MapPin, KeyRound, CheckCircle2 } from 'lucide-react'
import { m, useReducedMotion } from '@/components/shared/motion'
import { EASE, VIEWPORT } from '@/lib/motion'

const STEPS = [
  { icon: Search, title: 'Browse', body: 'Find books, notes & modules for your exam.' },
  { icon: MessageCircle, title: 'Chat', body: 'Message the seller and agree to meet.' },
  { icon: MapPin, title: 'Meet', body: 'Inspect the material and settle payment in person.' },
  { icon: KeyRound, title: 'Passkey', body: 'The seller shares an 8-digit code once you’ve paid.' },
  { icon: CheckCircle2, title: 'Confirm', body: 'Enter the code to confirm and rate the seller.' },
]

// dashed, round-capped, warm bronze — same ink for every connector
const STROKE = {
  stroke: '#c58341',
  strokeWidth: 2.5,
  strokeDasharray: '2 13',
  strokeLinecap: 'round',
  fill: 'none',
}

function StepCard({ step, i, reduced }) {
  const Icon = step.icon
  return (
    <m.div
      initial={reduced ? { opacity: 0 } : { opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ ...VIEWPORT }}
      transition={{ duration: 0.4, ease: EASE.warm, delay: i * 0.08 }}
      whileHover={reduced ? undefined : { y: -4 }}
      className="card flex w-full max-w-[15rem] flex-col items-center justify-center gap-2.5 p-4 text-center lg:h-48 lg:w-36"
    >
      <span className="flex h-11 w-11 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
        <Icon className="h-5 w-5" />
      </span>
      <p className="font-display text-lg font-semibold">{step.title}</p>
      <p className="text-sm leading-snug text-muted-foreground">{step.body}</p>
    </m.div>
  )
}

// desktop connector: a gentle dashed S-curve between alternating top/bottom
// card centers, arriving flat into the next card.
function CurveConnector({ down }) {
  const yTop = 96
  const yBot = 136
  const [y1, y2] = down ? [yTop, yBot] : [yBot, yTop]
  return (
    <div className="hidden w-14 shrink-0 lg:block">
      <m.svg
        viewBox="0 0 56 232"
        className="h-[232px] w-full"
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ ...VIEWPORT }}
        transition={{ duration: 0.5, ease: EASE.warm, delay: 0.2 }}
      >
        {/* flatten near both ends so the line leaves/arrives horizontally */}
        <path d={`M0 ${y1} C20 ${y1} 36 ${y2} 56 ${y2}`} {...STROKE} />
      </m.svg>
    </div>
  )
}

// mobile connector: a short dashed vertical sweep between stacked cards
function VConnector() {
  return (
    <m.svg
      viewBox="0 0 40 56"
      className="h-12 w-10 lg:hidden"
      initial={{ opacity: 0 }}
      whileInView={{ opacity: 1 }}
      viewport={{ ...VIEWPORT }}
      transition={{ duration: 0.4, ease: EASE.warm }}
    >
      <path d="M20 0 C8 18 32 38 20 56" {...STROKE} />
    </m.svg>
  )
}

export default function HowItWorks() {
  const reduced = useReducedMotion()
  const last = STEPS.length - 1

  return (
    <section className="cv-auto container py-14">
      <m.h2
        initial={reduced ? { opacity: 0 } : { opacity: 0, y: 12 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ ...VIEWPORT }}
        transition={{ duration: 0.4, ease: EASE.warm }}
        className="text-center font-display text-2xl font-semibold sm:text-3xl"
      >
        How it works
      </m.h2>
      <m.p
        initial={reduced ? { opacity: 0 } : { opacity: 0, y: 12 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ ...VIEWPORT }}
        transition={{ duration: 0.4, ease: EASE.warm, delay: 0.05 }}
        className="mx-auto mt-2 max-w-md text-center text-muted-foreground"
      >
        From finding the right book to confirming the exchange — five simple steps.
      </m.p>

      {/* desktop: alternating zigzag joined by dashed S-curves */}
      <div className="mt-12 hidden h-[232px] items-stretch justify-center lg:flex">
        {STEPS.map((step, i) => (
          <div key={step.title} className="contents">
            <div className={`flex w-36 ${i % 2 ? 'items-end' : 'items-start'}`}>
              <StepCard step={step} i={i} reduced={reduced} />
            </div>
            {i < last && <CurveConnector down={i % 2 === 0} />}
          </div>
        ))}
      </div>

      {/* mobile/tablet: vertical dashed path */}
      <div className="mt-10 flex flex-col items-center lg:hidden">
        {STEPS.map((step, i) => (
          <div key={step.title} className="flex w-full flex-col items-center">
            <StepCard step={step} i={i} reduced={reduced} />
            {i < last && <VConnector reduced={reduced} />}
          </div>
        ))}
      </div>
    </section>
  )
}

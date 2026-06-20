'use client'
import { useEffect, useRef, useState } from 'react'
import { MapPin, BadgeCheck, Star, CalendarDays } from 'lucide-react'
import Avatar from '@/components/shared/avatar'
import { m, useReducedMotion } from '@/components/shared/motion'
import { EASE, SPRING, SPRING_SNAPPY } from '@/lib/motion'
import { formatDate } from '@/lib/utils'

/**
 * Public-profile identity panel. A warm glass header that gives the seller
 * weight: ringed avatar with a verified seal, name, location/joined meta, and a
 * row of stat tiles whose numbers count up on mount. Orchestrated reveal;
 * reduced-motion lands on the final frame.
 */
export default function ProfileHeader({ user }) {
  const reduced = useReducedMotion()

  const container = {
    hidden: {},
    show: { transition: { staggerChildren: reduced ? 0 : 0.08, delayChildren: reduced ? 0 : 0.05 } },
  }
  const item = {
    hidden: reduced ? { opacity: 0 } : { opacity: 0, y: 14 },
    show: { opacity: 1, y: 0, transition: { duration: 0.45, ease: EASE.warm } },
  }

  const hasRating = user.seller_rating != null
  const stats = [
    { key: 'sales', value: user.books_sold ?? 0, label: 'Sales' },
    { key: 'bought', value: user.books_bought ?? 0, label: 'Bought' },
  ]

  return (
    <m.header
      variants={container}
      initial="hidden"
      animate="show"
      className="glass-soft relative overflow-hidden rounded-2xl p-6 sm:p-8"
    >
      {/* warm atmosphere glows */}
      <span
        aria-hidden
        className="pointer-events-none absolute -right-20 -top-24 h-60 w-60 rounded-full bg-light_bronze-500/25 blur-3xl"
      />
      <span
        aria-hidden
        className="pointer-events-none absolute -bottom-24 -left-16 h-52 w-52 rounded-full bg-tea_green-400/20 blur-3xl"
      />

      <div className="relative flex flex-col items-center gap-6 text-center sm:flex-row sm:items-center sm:justify-between sm:text-left">
        {/* identity */}
        <div className="flex flex-col items-center gap-4 sm:flex-row sm:gap-5">
          <m.div variants={item} className="relative shrink-0">
            <span
              aria-hidden
              className="absolute -inset-1.5 rounded-full bg-gradient-to-tr from-light_bronze-400/50 via-papaya_whip-300/40 to-tea_green-400/40 blur-[3px]"
            />
            <Avatar
              src={user.avatar_url}
              name={user.full_name}
              size={88}
              className="relative ring-2 ring-white/70 shadow-warm"
            />
            {user.is_verified && (
              <m.span
                initial={reduced ? { opacity: 0 } : { scale: 0, rotate: -30 }}
                animate={{ scale: 1, rotate: 0, opacity: 1 }}
                transition={{ ...SPRING_SNAPPY, delay: reduced ? 0 : 0.5 }}
                className="absolute -bottom-1 -right-1 flex h-7 w-7 items-center justify-center rounded-full border-2 border-card bg-primary text-primary-foreground shadow-warm"
                title="Verified seller"
              >
                <BadgeCheck className="h-4 w-4" strokeWidth={2.5} />
              </m.span>
            )}
          </m.div>

          <m.div variants={item} className="min-w-0">
            <h1 className="font-display text-2xl font-semibold leading-tight tracking-tight sm:text-3xl">
              {user.full_name}
            </h1>
            <div className="mt-2 flex flex-wrap items-center justify-center gap-x-4 gap-y-1.5 text-sm text-muted-foreground sm:justify-start">
              {user.city && (
                <span className="inline-flex items-center gap-1.5">
                  <MapPin className="h-4 w-4 text-light_bronze-300" /> {user.city}
                </span>
              )}
              {user.created_at && (
                <span className="inline-flex items-center gap-1.5">
                  <CalendarDays className="h-4 w-4 text-light_bronze-300" /> Joined {formatDate(user.created_at)}
                </span>
              )}
            </div>
          </m.div>
        </div>

        {/* stat tiles */}
        <m.div variants={item} className="flex w-full items-stretch gap-3 sm:w-auto">
          {stats.map((s) => (
            <StatTile key={s.key} label={s.label} reduced={reduced}>
              <CountUp value={s.value} reduced={reduced} />
            </StatTile>
          ))}
          {hasRating && (
            <StatTile label="Rating" reduced={reduced} accent>
              <span className="inline-flex items-center gap-1">
                <Star className="h-4 w-4 fill-current text-light_bronze-400" strokeWidth={0} />
                <span className="tabular-nums">{user.seller_rating}</span>
              </span>
            </StatTile>
          )}
        </m.div>
      </div>
    </m.header>
  )
}

function StatTile({ label, children, reduced, accent }) {
  return (
    <m.div
      whileHover={reduced ? undefined : { y: -3 }}
      transition={SPRING}
      className={[
        'flex flex-1 flex-col items-center justify-center rounded-xl border px-4 py-3 text-center shadow-warm backdrop-blur-sm sm:min-w-[92px] sm:flex-none',
        accent
          ? 'border-light_bronze-700 bg-papaya_whip-800/70'
          : 'border-white/50 bg-card/70',
      ].join(' ')}
    >
      <div className="font-display text-2xl font-semibold leading-none text-foreground sm:text-[1.7rem]">
        {children}
      </div>
      <div className="mt-1.5 text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
        {label}
      </div>
    </m.div>
  )
}

/** Eased count-up from 0 → value on mount (instant under reduced motion). */
function CountUp({ value, reduced, duration = 950 }) {
  const [display, setDisplay] = useState(reduced ? value : 0)
  const rafRef = useRef(null)

  useEffect(() => {
    if (reduced || value === 0) {
      setDisplay(value)
      return
    }
    let start = null
    const tick = (t) => {
      if (start === null) start = t
      const p = Math.min(1, (t - start) / duration)
      const eased = 1 - Math.pow(1 - p, 3) // easeOutCubic
      setDisplay(Math.round(value * eased))
      if (p < 1) rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafRef.current)
  }, [value, reduced, duration])

  return <span className="tabular-nums">{display}</span>
}

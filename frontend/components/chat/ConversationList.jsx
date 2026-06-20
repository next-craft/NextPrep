'use client'
import Link from 'next/link'
import { AnimatePresence } from 'framer-motion'
import { BookOpen, MessageCircle, ChevronRight } from 'lucide-react'
import { cn, formatPrice, formatRelativeTime, listingStatus } from '@/lib/utils'
import { EmptyState } from '@/components/shared/states'
import StatusPill from '@/components/shared/status-pill'
import { m } from '@/components/shared/motion'
import { EASE, SPRING } from '@/lib/motion'

// Accent rail colours mirror the "living status" palette (status-pill.jsx) so a
// messages row scans the same way a Selling/Transactions row does. Unread wins
// the rail — it's the single most actionable signal in the list.
const STATUS_ACCENT = { active: '#5b8a3c', paused: '#b07d1e', sold: '#b3452f' }
const NEUTRAL_ACCENT = '#c7b29a'

/** Renders enriched conversations (listing summary + last message + unread). */
export default function ConversationList({
  conversations = [],
  meId,
  emptyTitle = 'No conversations yet',
  emptyDescription,
}) {
  if (!conversations.length) {
    return <EmptyState icon={MessageCircle} title={emptyTitle} description={emptyDescription} />
  }

  return (
    <div className="space-y-3">
      <AnimatePresence initial mode="popLayout">
        {conversations.map((c, idx) => {
        const removed = !c.listing_id || !c.listing
        const status = removed ? null : listingStatus(c.listing)
        const isBuyer = meId && c.buyer_id === meId
        const lastBody = c.lastMessage
          ? `${c.lastMessage.is_mine ? 'You: ' : ''}${c.lastMessage.body}`
          : 'No messages yet'
        const time = formatRelativeTime(c.lastMessage?.created_at || c.created_at)

        const unread = c.unreadCount > 0
        const price = c.listing?.asking_price
        const accent = unread ? '#b3452f' : status ? STATUS_ACCENT[status] : NEUTRAL_ACCENT

        return (
          <m.div
            key={c.id}
            layout
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0, transition: { delay: idx * 0.04, duration: 0.3, ease: EASE.warm } }}
            exit={{ opacity: 0, scale: 0.96, transition: { duration: 0.2 } }}
            whileHover={{ y: -2, transition: SPRING }}
            className={cn(
              'card group relative flex items-center gap-4 overflow-hidden p-3 pl-4 transition-colors sm:pl-5',
              unread && 'bg-papaya_whip-800/60'
            )}
          >
            {/* status / unread accent rail */}
            <span aria-hidden className="absolute inset-y-0 left-0 w-1" style={{ backgroundColor: accent }} />

            <Link href={`/chat/${c.id}`} className="flex min-w-0 flex-1 items-center gap-3.5">
              <div className="relative flex h-[60px] w-[60px] shrink-0 items-center justify-center overflow-hidden rounded-lg bg-papaya_whip-700 text-light_bronze-500 ring-1 ring-black/5">
                {c.listing?.images?.[0] ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={c.listing.images[0]}
                    alt=""
                    className={cn(
                      'h-full w-full object-cover transition-transform duration-500 group-hover:scale-105',
                      status === 'sold' && 'opacity-65 grayscale-[35%]'
                    )}
                  />
                ) : (
                  <BookOpen className="h-6 w-6" />
                )}
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-2">
                  <p className={cn('truncate leading-snug', unread ? 'font-semibold' : 'font-medium')}>
                    {removed ? 'Listing removed' : c.listing.title}
                  </p>
                  <span className="shrink-0 text-[11px] tabular-nums text-muted-foreground">{time}</span>
                </div>
                <p
                  className={cn(
                    'mt-1 flex items-center gap-1.5 truncate text-sm',
                    unread ? 'font-medium text-foreground' : 'text-muted-foreground'
                  )}
                >
                  {unread && (
                    <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-destructive" />
                  )}
                  <span className="truncate">{lastBody}</span>
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  {status && <StatusPill status={status} />}
                  {!removed && typeof price === 'number' && (
                    <span className="font-display text-sm font-semibold tracking-tight text-foreground/85">
                      {formatPrice(price)}
                    </span>
                  )}
                </div>
              </div>
            </Link>

            <div className="flex shrink-0 flex-col items-end justify-center gap-2 self-stretch">
              {unread && (
                <m.span
                  key={c.unreadCount}
                  initial={{ scale: 0.5, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={SPRING}
                  className="relative inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-destructive px-1.5 text-xs font-semibold text-destructive-foreground"
                >
                  <span className="absolute inset-0 animate-ping rounded-full bg-destructive opacity-60" />
                  <span className="relative">{c.unreadCount}</span>
                </m.span>
              )}
              {isBuyer && status === 'active' ? (
                <Link href={`/listings/${c.listing_id}`} className="btn-primary h-8 px-3 text-xs">
                  Buy Now
                </Link>
              ) : (
                <ChevronRight className="h-4 w-4 text-muted-foreground/50 transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-muted-foreground" />
              )}
            </div>
          </m.div>
        )
      })}
      </AnimatePresence>
    </div>
  )
}

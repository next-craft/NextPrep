'use client'
import Link from 'next/link'
import { BookOpen, MessageCircle } from 'lucide-react'
import { cn, formatRelativeTime, listingStatus } from '@/lib/utils'
import { EmptyState } from '@/components/shared/states'

const STATUS = {
  active: { label: 'Available', cls: 'border-[#bcd0a3] bg-[#e9f0dd] text-[#3f6733]' },
  paused: { label: 'Paused', cls: 'border-[#ecd6a0] bg-[#fbf1d6] text-[#8a5e12]' },
  sold: { label: 'Sold', cls: 'border-[#e4b3a6] bg-[#f7e6e0] text-[#8f3322]' },
}

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
      {conversations.map((c) => {
        const removed = !c.listing_id || !c.listing
        const status = removed ? null : listingStatus(c.listing)
        const isBuyer = meId && c.buyer_id === meId
        const lastBody = c.lastMessage
          ? `${c.lastMessage.is_mine ? 'You: ' : ''}${c.lastMessage.body}`
          : 'No messages yet'
        const time = formatRelativeTime(c.lastMessage?.created_at || c.created_at)

        return (
          <div key={c.id} className="card flex items-center gap-3 p-3">
            <Link href={`/chat/${c.id}`} className="flex min-w-0 flex-1 items-center gap-3">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-md bg-papaya_whip-700 text-light_bronze-500">
                {c.listing?.images?.[0] ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={c.listing.images[0]} alt="" className="h-full w-full object-cover" />
                ) : (
                  <BookOpen className="h-6 w-6" />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <p className="truncate font-medium">{removed ? 'Listing removed' : c.listing.title}</p>
                  <span className="shrink-0 text-xs text-muted-foreground">{time}</span>
                </div>
                <p
                  className={cn(
                    'mt-0.5 truncate text-sm',
                    c.unreadCount > 0 ? 'font-medium text-foreground' : 'text-muted-foreground'
                  )}
                >
                  {lastBody}
                </p>
              </div>
            </Link>

            <div className="flex shrink-0 flex-col items-end gap-1.5">
              {c.unreadCount > 0 && (
                <span className="inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-destructive px-1.5 text-xs font-semibold text-destructive-foreground">
                  {c.unreadCount}
                </span>
              )}
              {status && <span className={cn('badge', STATUS[status].cls)}>{STATUS[status].label}</span>}
              {isBuyer && status === 'active' && (
                <Link href={`/listings/${c.listing_id}`} className="btn-primary h-8 px-3 text-xs">
                  Buy Now
                </Link>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

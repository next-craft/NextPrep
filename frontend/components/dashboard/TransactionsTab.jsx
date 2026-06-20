'use client'
import { useState } from 'react'
import { Receipt, Star, ArrowDownLeft, ArrowUpRight, BadgeCheck } from 'lucide-react'
import { useMyTransactions } from '@/lib/queries'
import RateSeller from '@/components/shared/rate-seller'
import { VerifiedTag } from '@/components/shared/status-pill'
import Disclosure from '@/components/shared/disclosure'
import { EmptyState } from '@/components/shared/states'
import { Stagger, StaggerItem } from '@/components/shared/motion'
import { cn, formatDate } from '@/lib/utils'

// Role visuals — buyer rows lean green (acquired), seller rows lean bronze (sold).
const ROLE_UI = {
  buyer: {
    Icon: ArrowDownLeft,
    accent: '#5b8a3c',
    medallion: 'bg-[#eaf1de] text-[#3f6733] ring-[#cad8b0]',
  },
  seller: {
    Icon: ArrowUpRight,
    accent: '#a06a1f',
    medallion: 'bg-[#f3e9da] text-[#7a531c] ring-[#e7d4bf]',
  },
}

export default function TransactionsTab() {
  const { data: txns = [], isLoading } = useMyTransactions()
  const [rating, setRating] = useState(null) // transaction id currently being rated

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading your transactions…</p>
  }

  if (!txns.length) {
    return (
      <EmptyState
        icon={Receipt}
        title="No transactions yet"
        description="Your verified purchases and sales appear here once a passkey is confirmed at a meetup."
      />
    )
  }

  const buying = txns.filter((t) => t.role === 'buyer')
  const selling = txns.filter((t) => t.role === 'seller')

  const renderGroup = (rows, emptyText) => {
    if (!rows.length) {
      return <p className="px-1 py-2 text-sm text-muted-foreground">{emptyText}</p>
    }
    return (
      <Stagger gap={0.05} className="space-y-3">
        {rows.map((t) => {
          const ui = ROLE_UI[t.role] ?? ROLE_UI.buyer
          const { Icon } = ui
          const counterpart =
            t.role === 'buyer'
              ? t.seller_name
                ? `Purchased from ${t.seller_name}`
                : 'Verified purchase'
              : 'You sold this at a meetup'
          return (
            <StaggerItem key={t.id} className="card group relative overflow-hidden p-4 pl-5">
              {/* role accent rail */}
              <span
                aria-hidden
                className="absolute inset-y-0 left-0 w-1"
                style={{ backgroundColor: ui.accent }}
              />
              <div className="flex items-center gap-4">
                {/* directional medallion — a stamped record of the exchange */}
                <div
                  className={cn(
                    'flex h-11 w-11 shrink-0 items-center justify-center rounded-full ring-1 ring-inset',
                    ui.medallion
                  )}
                >
                  <Icon className="h-5 w-5" strokeWidth={2.5} />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium leading-snug">
                    {t.listing_title || 'Listing removed'}
                  </p>
                  <p className="mt-0.5 truncate text-sm text-muted-foreground">{counterpart}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <VerifiedTag role={t.role} />
                    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                      <span className="h-1 w-1 rounded-full bg-muted-foreground/50" />
                      {formatDate(t.created_at)}
                    </span>
                  </div>
                </div>
                {t.can_rate && rating !== t.id && (
                  <button
                    type="button"
                    onClick={() => setRating(t.id)}
                    className="btn-secondary h-9 shrink-0 self-start px-3.5 text-xs sm:self-center"
                  >
                    <Star className="h-4 w-4" /> Rate seller
                  </button>
                )}
                {!t.can_rate && t.role === 'buyer' && (
                  <span
                    className="hidden shrink-0 items-center gap-1.5 self-center text-xs font-medium text-[#3f6733] sm:inline-flex"
                    title="You've rated this seller"
                  >
                    <BadgeCheck className="h-4 w-4" /> Rated
                  </span>
                )}
              </div>
              {rating === t.id && (
                <div className="mt-4 border-t border-dashed border-border pt-4">
                  <RateSeller
                    transactionId={t.id}
                    sellerName={t.seller_name}
                    onRated={() => setRating(null)}
                  />
                </div>
              )}
            </StaggerItem>
          )
        })}
      </Stagger>
    )
  }

  return (
    <div className="space-y-5">
      <Disclosure title="Buying" count={buying.length}>
        {renderGroup(buying, "Books you've bought will appear here.")}
      </Disclosure>
      <Disclosure title="Selling" count={selling.length}>
        {renderGroup(selling, "Books you've sold will appear here.")}
      </Disclosure>
    </div>
  )
}

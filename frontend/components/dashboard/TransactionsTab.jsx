'use client'
import { useState } from 'react'
import { Receipt, Star } from 'lucide-react'
import { useMyTransactions } from '@/lib/queries'
import RateSeller from '@/components/shared/rate-seller'
import { VerifiedTag } from '@/components/shared/status-pill'
import Disclosure from '@/components/shared/disclosure'
import { EmptyState } from '@/components/shared/states'
import { Stagger, StaggerItem } from '@/components/shared/motion'
import { formatDate } from '@/lib/utils'

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
        {rows.map((t) => (
          <StaggerItem key={t.id} className="card p-4">
            <div className="flex items-center gap-4">
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{t.listing_title || 'Listing removed'}</p>
                <div className="mt-1.5 flex flex-wrap items-center gap-2">
                  <VerifiedTag role={t.role} />
                  <span className="text-xs text-muted-foreground">{formatDate(t.created_at)}</span>
                </div>
              </div>
              {t.can_rate && rating !== t.id && (
                <button
                  type="button"
                  onClick={() => setRating(t.id)}
                  className="btn-secondary shrink-0"
                >
                  <Star className="h-4 w-4" /> Rate seller
                </button>
              )}
            </div>
            {rating === t.id && (
              <div className="mt-4 border-t border-border pt-4">
                <RateSeller
                  transactionId={t.id}
                  sellerName={t.seller_name}
                  onRated={() => setRating(null)}
                />
              </div>
            )}
          </StaggerItem>
        ))}
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

'use client'
import { useState } from 'react'
import { Receipt, Star } from 'lucide-react'
import { useMyTransactions } from '@/lib/queries'
import RateSeller from '@/components/shared/rate-seller'
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

  return (
    <Stagger gap={0.05} className="space-y-3">
      {txns.map((t) => (
        <StaggerItem key={t.id} className="card p-4">
          <div className="flex items-center gap-4">
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">{t.listing_title || 'Listing removed'}</p>
              <p className="mt-0.5 text-xs capitalize text-muted-foreground">
                {t.role === 'buyer' ? 'Bought' : 'Sold'} · {formatDate(t.created_at)}
              </p>
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

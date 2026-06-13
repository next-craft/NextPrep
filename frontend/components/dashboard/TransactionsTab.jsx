'use client'
import Link from 'next/link'
import { Receipt, ArrowRight } from 'lucide-react'
import { useMyTransactions } from '@/lib/queries'
import { TransactionStatusBadge } from '@/components/shared/badges'
import { EmptyState } from '@/components/shared/states'
import { Stagger, StaggerItem } from '@/components/shared/motion'
import { formatPrice, formatDate } from '@/lib/utils'

export default function TransactionsTab() {
  const { data: txns = [], isLoading } = useMyTransactions()

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading your transactions…</p>
  }

  if (!txns.length) {
    return (
      <EmptyState
        icon={Receipt}
        title="No transactions yet"
        description="Your purchases and sales will appear here once a payment goes through."
      />
    )
  }

  return (
    <Stagger gap={0.05} className="space-y-3">
      {txns.map((t) => (
        <StaggerItem key={t.id} className="card flex items-center gap-4 p-4">
          <div className="min-w-0 flex-1">
            <p className="truncate font-medium">{t.listing_title || 'Listing removed'}</p>
            <p className="mt-0.5 text-xs capitalize text-muted-foreground">
              {t.role} · {formatDate(t.created_at)}
            </p>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1.5">
            <span className="font-semibold">{formatPrice(t.amount_rupees)}</span>
            <div className="flex items-center gap-2">
              <TransactionStatusBadge status={t.status} />
              {t.status === 'initiated' && (
                <Link
                  href={`/transactions/${t.id}/status`}
                  className="inline-flex items-center gap-0.5 text-xs font-medium text-primary hover:text-light_bronze-200"
                >
                  Resume <ArrowRight className="h-3 w-3" />
                </Link>
              )}
            </div>
          </div>
        </StaggerItem>
      ))}
    </Stagger>
  )
}

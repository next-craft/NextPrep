'use client'
import Link from 'next/link'
import { MessageCircle } from 'lucide-react'
import { useEnrichedConversations } from '@/lib/queries'
import ConversationList from '@/components/chat/ConversationList'
import Disclosure from '@/components/shared/disclosure'
import { RowSkeleton } from '@/components/shared/skeletons'
import { EmptyState, ErrorState } from '@/components/shared/states'

export default function BuyingTab({ meId }) {
  const { data, isLoading, isError } = useEnrichedConversations({
    enabled: true,
    refetchInterval: 15_000,
  })

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[0, 1, 2].map((i) => (
          <RowSkeleton key={i} />
        ))}
      </div>
    )
  }

  if (isError) {
    return <ErrorState title="Couldn't load your conversations" description="Please try again in a moment." />
  }

  const conversations = data || []

  if (!conversations.length) {
    return (
      <EmptyState
        icon={MessageCircle}
        title="No messages yet"
        description="Conversations with buyers and sellers will appear here."
        action={
          <Link href="/listings" className="btn-primary">
            Browse listings
          </Link>
        }
      />
    )
  }

  // Split by role so buying chats (you messaged a seller) and selling chats
  // (a buyer messaged you about your listing) live under separate dropdowns.
  const buying = conversations.filter((c) => c.buyer_id === meId)
  const selling = conversations.filter((c) => c.seller_id === meId)

  return (
    <div className="space-y-5">
      <Disclosure title="Buying" count={buying.length}>
        <ConversationList
          conversations={buying}
          meId={meId}
          emptyTitle="No buying conversations"
          emptyDescription="Chats with sellers you've messaged will appear here."
        />
      </Disclosure>
      <Disclosure title="Selling" count={selling.length}>
        <ConversationList
          conversations={selling}
          meId={meId}
          emptyTitle="No selling conversations"
          emptyDescription="Chats from buyers about your listings will appear here."
        />
      </Disclosure>
    </div>
  )
}

'use client'
import Link from 'next/link'
import { MessageCircle } from 'lucide-react'
import { useEnrichedConversations } from '@/lib/queries'
import ConversationList from '@/components/chat/ConversationList'
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

  // All conversations — both where you're the buyer and where a buyer has messaged
  // you about your listing (seller role). ConversationList renders each with the
  // right context (e.g. the "Buy Now" shortcut only on buyer-side active listings).
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

  return <ConversationList conversations={conversations} meId={meId} />
}

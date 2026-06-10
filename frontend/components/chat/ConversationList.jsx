'use client'
import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import api from '@/lib/api'

export default function ConversationList() {
  const { data: conversations = [], isLoading } = useQuery({
    queryKey: ['conversations'],
    queryFn: () => api.get('/conversations').then(r => r.data),
  })

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading chats...</p>
  if (!conversations.length) return <p className="text-sm text-muted-foreground">No conversations yet.</p>

  return (
    <ul className="space-y-2">
      {conversations.map((c) => (
        <li key={c.id}>
          <Link
            href={`/chat/${c.id}`}
            className="block border rounded p-3 hover:bg-muted transition-colors text-sm"
          >
            <span className="text-xs text-muted-foreground">Listing {c.listing_id ?? 'deleted'}</span>
          </Link>
        </li>
      ))}
    </ul>
  )
}

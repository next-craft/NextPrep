'use client'
import ConversationList from '@/components/chat/ConversationList'

export default function DashboardPage() {
  return (
    <div className="max-w-2xl mx-auto p-6">
      <h1 className="text-xl font-bold mb-4">My Conversations</h1>
      <ConversationList />
    </div>
  )
}

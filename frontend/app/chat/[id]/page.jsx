'use client'
import { useEffect, useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'

export default function ChatPage({ params }) {
  const conversationId = params.id
  const queryClient = useQueryClient()
  const [body, setBody] = useState('')
  const bottomRef = useRef(null)

  const { data: messages = [] } = useQuery({
    queryKey: ['messages', conversationId],
    queryFn: () => api.get(`/conversations/${conversationId}/messages`).then(r => r.data),
    refetchInterval: 4000,
  })

  const send = useMutation({
    mutationFn: () =>
      api.post(`/conversations/${conversationId}/messages`, { body }),
    onSuccess: () => {
      setBody('')
      queryClient.invalidateQueries({ queryKey: ['messages', conversationId] })
    },
  })

  const unreadCount = messages.filter(m => !m.is_read && !m.is_mine).length

  useEffect(() => {
    if (unreadCount === 0) return
    api.patch(`/conversations/${conversationId}/messages/read`).catch(() => {})
  }, [conversationId, unreadCount])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="flex flex-col h-screen max-w-2xl mx-auto">
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((m) => (
          <div
            key={m.id}
            className={`rounded p-2 text-sm max-w-[75%] ${m.is_mine ? 'ml-auto bg-primary text-primary-foreground' : 'bg-muted'}`}
          >
            {m.body}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="border-t p-3 flex gap-2">
        <input
          className="flex-1 border rounded px-3 py-2 text-sm"
          placeholder="Type a message..."
          value={body}
          onChange={e => setBody(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey && body.trim()) {
              e.preventDefault()
              send.mutate()
            }
          }}
          maxLength={2000}
        />
        <button
          onClick={() => send.mutate()}
          disabled={!body.trim() || send.isPending}
          className="px-4 py-2 rounded bg-primary text-primary-foreground text-sm disabled:opacity-50"
        >
          Send
        </button>
      </div>

      {send.isError && (
        <p className="text-red-500 text-xs px-3 pb-2">
          {send.error?.response?.data?.detail ?? 'Failed to send message.'}
        </p>
      )}
    </div>
  )
}

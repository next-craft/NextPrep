'use client'
import { use, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence } from 'framer-motion'
import { ArrowLeft, Send, Loader2 } from 'lucide-react'
import api from '@/lib/api'
import { useMe } from '@/lib/queries'
import { cn, formatPrice, formatRelativeTime, listingStatus } from '@/lib/utils'
import Avatar from '@/components/shared/avatar'
import BuyNowButton from '@/components/listings/BuyNowButton'
import { m, useReducedMotion } from '@/components/shared/motion'
import { EASE, SPRING } from '@/lib/motion'

const RATE_LIMIT_COPY = "You've sent too many messages. Please wait before sending more."

export default function ChatPage({ params }) {
  const { id: conversationId } = use(params)
  const queryClient = useQueryClient()
  const { data: me } = useMe()
  const reduced = useReducedMotion()
  const [body, setBody] = useState('')
  // The thread is its own scroll container (the composer stays put, WhatsApp-style).
  const threadRef = useRef(null)
  // Whether the user is parked at the bottom — only then do new messages auto-scroll,
  // so we never yank them away while they're reading older messages.
  const atBottomRef = useRef(true)

  const handleThreadScroll = () => {
    const el = threadRef.current
    if (!el) return
    atBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80
  }

  // No GET /conversations/{id}; derive meta (listing_id, buyer/seller) from the list.
  // TODO(backend): a single-conversation endpoint would avoid this.
  const { data: conversation } = useQuery({
    queryKey: ['conversation', conversationId],
    queryFn: async () => {
      const { data } = await api.get('/conversations')
      return data.find((c) => c.id === conversationId) || null
    },
    staleTime: 30_000,
  })

  const listingId = conversation?.listing_id
  // Messages don't include the listing summary — fetch it separately.
  const { data: listing } = useQuery({
    queryKey: ['listing', listingId],
    queryFn: async () => (await api.get(`/listings/${listingId}`)).data,
    enabled: !!listingId,
    staleTime: 30_000,
  })

  // The other participant in this chat (the seller if you're the buyer, else the buyer).
  const otherUserId =
    conversation && me?.id
      ? conversation.buyer_id === me.id
        ? conversation.seller_id
        : conversation.buyer_id
      : null
  // API: GET /users/{id} — public profile, for the counterpart's name + avatar.
  const { data: otherUser } = useQuery({
    queryKey: ['user', otherUserId],
    queryFn: async () => (await api.get(`/users/${otherUserId}`)).data,
    enabled: !!otherUserId,
    staleTime: 60_000,
  })
  const otherFirstName = otherUser?.full_name?.trim().split(/\s+/)[0]

  // API: GET /conversations/{id}/messages — poll every 4s
  const { data: messages = [] } = useQuery({
    queryKey: ['messages', conversationId],
    queryFn: () => api.get(`/conversations/${conversationId}/messages`).then((r) => r.data),
    refetchInterval: 4000,
  })

  const send = useMutation({
    // API: POST /conversations/{id}/messages
    mutationFn: () => api.post(`/conversations/${conversationId}/messages`, { body: body.trim() }),
    onSuccess: () => {
      setBody('')
      queryClient.invalidateQueries({ queryKey: ['messages', conversationId] })
    },
  })

  const unreadCount = messages.filter((m) => !m.is_read && !m.is_mine).length
  useEffect(() => {
    if (unreadCount === 0) return
    // API: PATCH /conversations/{id}/messages/read
    api.patch(`/conversations/${conversationId}/messages/read`).catch(() => {})
  }, [conversationId, unreadCount])

  // Auto-scroll the thread (not the page) to the newest message — but only when the
  // user is already at the bottom. Scrolls the inner container, so the composer below
  // never moves.
  useEffect(() => {
    const el = threadRef.current
    if (el && atBottomRef.current) el.scrollTop = el.scrollHeight
  }, [messages])

  const isBuyer = conversation && me?.id && conversation.buyer_id === me.id
  const status = listing ? listingStatus(listing) : null
  const available = status === 'active'
  const closed = status === 'sold' // listing sold -> conversation is closed

  const sendError = send.isError
    ? send.error?.response?.status === 429
      ? RATE_LIMIT_COPY
      : send.error?.response?.data?.detail || 'Failed to send message.'
    : null

  return (
    <div className="mx-auto flex h-[calc(100dvh-4rem)] max-w-2xl flex-col overflow-hidden">
      {/* Pinned listing summary — fixed; only the thread between header and composer scrolls */}
      <div className="shrink-0 border-b border-border bg-cornsilk/90 backdrop-blur">
        <m.div
          initial={reduced ? { opacity: 0 } : { opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: EASE.warm }}
          className="flex items-center gap-3 px-4 py-3"
        >
          <Link href="/dashboard?tab=buying" className="btn-ghost h-9 w-9 px-0" aria-label="Back">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <Avatar src={otherUser?.avatar_url} name={otherUser?.full_name} size={42} />
          <div className="min-w-0 flex-1">
            <p className="truncate font-medium leading-tight">
              {otherFirstName || (conversation === null ? 'Conversation' : 'Loading…')}
            </p>
            <Link
              href={listingId ? `/listings/${listingId}` : '#'}
              className="block truncate text-xs text-muted-foreground transition-colors hover:text-foreground"
            >
              {listing ? listing.title : conversation === null ? 'Listing removed' : 'Loading…'}
              {listing && (
                <>
                  {` · ${formatPrice(listing.asking_price)}`}
                  {status === 'sold' && ' · Sold'}
                  {status === 'paused' && ' · Unavailable'}
                </>
              )}
            </Link>
          </div>
          {isBuyer && available && (
            <div className="shrink-0">
              <BuyNowButton listingId={listingId} className="h-10 px-4" />
            </div>
          )}
        </m.div>
      </div>

      {/* Thread — the only scroll container */}
      <div
        ref={threadRef}
        onScroll={handleThreadScroll}
        className="flex-1 space-y-2 overflow-y-auto px-4 py-5"
      >
        {messages.length === 0 && (
          <p className="py-10 text-center text-sm text-muted-foreground">
            No messages yet. Say hello and arrange a meetup. Never share contact details or your
            passkey here.
          </p>
        )}
        {/* initial={false}: existing history appears instantly; only newly
            arrived/sent messages animate in (keeps 4s-poll additions smooth). */}
        <AnimatePresence initial={false}>
          {messages.map((msg) => (
            <m.div
              key={msg.id}
              layout
              initial={reduced ? { opacity: 0 } : { opacity: 0, y: 8, scale: 0.96, x: msg.is_mine ? 16 : -16 }}
              animate={{ opacity: 1, y: 0, scale: 1, x: 0 }}
              transition={SPRING}
              className={cn('flex flex-col', msg.is_mine ? 'items-end' : 'items-start')}
            >
              <div
                className={cn(
                  'max-w-[80%] whitespace-pre-wrap rounded-2xl px-3.5 py-2 text-sm leading-relaxed',
                  msg.is_mine
                    ? 'rounded-br-sm bg-primary text-primary-foreground'
                    : 'rounded-bl-sm border border-border bg-card text-foreground'
                )}
              >
                {msg.body}
              </div>
              <span className="mt-0.5 px-1 text-[11px] text-muted-foreground">
                {formatRelativeTime(msg.created_at)}
                {msg.is_mine && (
                  <AnimatePresence mode="wait" initial={false}>
                    <m.span
                      key={msg.is_read ? 'read' : 'sent'}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 0.2 }}
                    >
                      {msg.is_read ? ' · Read' : ' · Sent'}
                    </m.span>
                  </AnimatePresence>
                )}
              </span>
            </m.div>
          ))}
        </AnimatePresence>
      </div>

      {/* Composer — fixed below the thread, lifted a little off the bottom edge */}
      <div className="mb-4 shrink-0 border-t border-border bg-cornsilk/90 px-4 py-3 backdrop-blur">
        <AnimatePresence>
          {sendError && (
            <m.p
              key={sendError}
              initial={{ opacity: 0, height: 0 }}
              animate={reduced ? { opacity: 1, height: 'auto' } : { opacity: 1, height: 'auto', x: [0, -5, 5, -4, 4, 0] }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.4, ease: EASE.warm }}
              className="mb-2 overflow-hidden text-xs font-medium text-destructive"
            >
              {sendError}
            </m.p>
          )}
        </AnimatePresence>
        {closed ? (
          <p className="py-1.5 text-center text-sm text-muted-foreground">
            This listing has been sold — this conversation is now closed.
          </p>
        ) : (
          <>
            <div className="flex items-end gap-2">
              <textarea
                className="textarea max-h-32 min-h-[2.75rem] flex-1 resize-none py-2.5"
                placeholder="Type a message…"
                rows={1}
                value={body}
                maxLength={2000}
                onChange={(e) => setBody(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    if (body.trim() && !send.isPending) send.mutate()
                  }
                }}
              />
              <m.button
                type="button"
                onClick={() => send.mutate()}
                disabled={!body.trim() || send.isPending}
                whileTap={{ scale: 0.9 }}
                transition={SPRING}
                className="btn-primary h-11 w-11 shrink-0 px-0"
                aria-label="Send message"
              >
                {send.isPending ? <Loader2 className="h-5 w-5 animate-spin" /> : <Send className="h-5 w-5" />}
              </m.button>
            </div>
            {body.length > 1800 && (
              <p className="mt-1 text-right text-[11px] text-muted-foreground">{body.length}/2000</p>
            )}
          </>
        )}
      </div>
    </div>
  )
}

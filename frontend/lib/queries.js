import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

/**
 * Current authenticated user profile.
 * Gate with `enabled` so it never fires (and triggers the 401→/login redirect)
 * on public pages where the visitor is logged out.
 */
// API: GET /users/me
export function useMe(options = {}) {
  return useQuery({
    queryKey: ['me'],
    queryFn: async () => (await api.get('/users/me')).data,
    staleTime: 60_000,
    retry: false,
    ...options,
  })
}

/**
 * Conversations enriched with the data the dashboard / nav / chat list need but
 * that the bare `GET /conversations` response does not include.
 *
 * The backend returns only { id, listing_id, buyer_id, seller_id, created_at },
 * so we compose the listing summary + last message + unread count client-side.
 *
 * TODO(backend): a single enriched conversations endpoint would remove this N+1
 * (listing title/thumbnail/status, last message, unread count per conversation).
 */
export async function fetchEnrichedConversations() {
  // API: GET /conversations
  const { data: conversations } = await api.get('/conversations')

  return Promise.all(
    conversations.map(async (c) => {
      let listing = null
      if (c.listing_id) {
        try {
          // API: GET /listings/{id}  (public; "Listing removed" when this 404s/returns null)
          listing = (await api.get(`/listings/${c.listing_id}`)).data
        } catch {
          listing = null
        }
      }

      let messages = []
      try {
        // API: GET /conversations/{id}/messages
        messages = (await api.get(`/conversations/${c.id}/messages`)).data
      } catch {
        messages = []
      }

      const lastMessage = messages.length ? messages[messages.length - 1] : null
      // MessageOut.is_mine is computed by the backend per requester, so unread =
      // incoming (not mine) + not yet read.
      const unreadCount = messages.filter((m) => !m.is_mine && !m.is_read).length

      return { ...c, listing, lastMessage, unreadCount, messageCount: messages.length }
    })
  )
}

export function useEnrichedConversations(options = {}) {
  return useQuery({
    queryKey: ['conversations-enriched'],
    queryFn: fetchEnrichedConversations,
    staleTime: 20_000,
    ...options,
  })
}

/** The signed-in seller's own listings (active/paused/sold). */
// API: GET /listings/mine
export function useMyListings(options = {}) {
  return useQuery({
    queryKey: ['my-listings'],
    queryFn: async () => (await api.get('/listings/mine')).data,
    staleTime: 20_000,
    ...options,
  })
}

/** The signed-in user's transactions as buyer and seller. */
// API: GET /transactions
export function useMyTransactions(options = {}) {
  return useQuery({
    queryKey: ['my-transactions'],
    queryFn: async () => (await api.get('/transactions')).data,
    staleTime: 20_000,
    ...options,
  })
}

'use client'
import { useRouter } from 'next/navigation'
import { useMutation } from '@tanstack/react-query'
import api from '@/lib/api'

export default function MessageSellerButton({ listingId }) {
  const router = useRouter()

  const open = useMutation({
    mutationFn: () => api.post('/conversations', { listing_id: listingId }),
    onSuccess: (res) => router.push(`/chat/${res.data.id}`),
  })

  return (
    <button
      onClick={() => open.mutate()}
      disabled={open.isPending}
      className="border rounded px-4 py-2 text-sm disabled:opacity-50"
    >
      {open.isPending ? 'Opening chat...' : 'Message Seller'}
    </button>
  )
}

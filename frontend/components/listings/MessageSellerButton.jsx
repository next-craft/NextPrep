'use client'
import { useRouter } from 'next/navigation'
import { useMutation } from '@tanstack/react-query'
import { MessageCircle, Loader2 } from 'lucide-react'
import api from '@/lib/api'
import { cn } from '@/lib/utils'
import { toast } from '@/components/ui/sonner'

export default function MessageSellerButton({ listingId, className }) {
  const router = useRouter()

  const open = useMutation({
    // API: POST /conversations — get-or-create for this listing
    mutationFn: () => api.post('/conversations', { listing_id: listingId }),
    onSuccess: (res) => router.push(`/chat/${res.data.id}`),
    onError: (err) => toast.error(err.response?.data?.detail || 'Could not start the chat.'),
  })

  return (
    <button
      type="button"
      onClick={() => open.mutate()}
      disabled={open.isPending}
      className={cn('btn-secondary', className)}
    >
      {open.isPending ? (
        <>
          <Loader2 className="h-4 w-4 animate-spin" /> Opening chat…
        </>
      ) : (
        <>
          <MessageCircle className="h-4 w-4" /> Message seller
        </>
      )}
    </button>
  )
}

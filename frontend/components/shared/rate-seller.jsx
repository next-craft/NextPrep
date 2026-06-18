'use client'
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Star, Loader2, CheckCircle2 } from 'lucide-react'
import api from '@/lib/api'
import { cn } from '@/lib/utils'

/**
 * Buyer-only rating for a verified transaction. Reused by the post-verification
 * prompt (BuyNowButton) and the dashboard Transactions tab. One rating per
 * transaction — the backend enforces it; on success we invalidate the lists so
 * the "Rate seller" affordance disappears.
 */
export default function RateSeller({ transactionId, sellerName, onRated, className }) {
  const queryClient = useQueryClient()
  const [rating, setRating] = useState(0)
  const [hover, setHover] = useState(0)
  const [review, setReview] = useState('')
  const [error, setError] = useState(null)

  const { mutate, isPending, isSuccess } = useMutation({
    // API: POST /transactions/{id}/rating
    mutationFn: () =>
      api.post(`/transactions/${transactionId}/rating`, {
        rating,
        review: review.trim() || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['my-transactions'] })
      queryClient.invalidateQueries({ queryKey: ['me'] })
      onRated?.()
    },
    onError: (err) => setError(err.response?.data?.detail || 'Could not submit your rating.'),
  })

  if (isSuccess) {
    return (
      <p className={cn('flex items-center justify-center gap-2 text-sm font-medium text-[#3f6733]', className)}>
        <CheckCircle2 className="h-4 w-4" /> Thanks for rating {sellerName || 'the seller'}!
      </p>
    )
  }

  const label = `How was your experience${sellerName ? ` with ${sellerName}` : ''}?`

  return (
    <div className={cn('space-y-3', className)}>
      <p className="text-sm font-medium text-foreground">{label}</p>
      <div className="flex gap-1" role="radiogroup" aria-label="Rating out of 5">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            onMouseEnter={() => setHover(n)}
            onMouseLeave={() => setHover(0)}
            onClick={() => {
              setRating(n)
              setError(null)
            }}
            aria-label={`${n} star${n > 1 ? 's' : ''}`}
            aria-checked={rating === n}
            role="radio"
            className="transition-transform hover:scale-110"
          >
            <Star
              className={cn(
                'h-7 w-7',
                (hover || rating) >= n
                  ? 'fill-current text-light_bronze-400'
                  : 'text-muted-foreground/40'
              )}
            />
          </button>
        ))}
      </div>
      <textarea
        value={review}
        onChange={(e) => setReview(e.target.value)}
        maxLength={1000}
        rows={3}
        placeholder="Add a short review (optional)"
        className="textarea"
      />
      {error && <p className="text-sm font-medium text-destructive">{error}</p>}
      <button
        type="button"
        onClick={() => mutate()}
        disabled={rating === 0 || isPending}
        className="btn-primary w-full"
      >
        {isPending ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" /> Submitting…
          </>
        ) : (
          'Submit rating'
        )}
      </button>
    </div>
  )
}

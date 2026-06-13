'use client'
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { ShoppingBag, Loader2, ArrowLeft } from 'lucide-react'
import api from '@/lib/api'
import SegmentedPasskeyInput from '@/components/shared/segmented-passkey-input'
import { cn } from '@/lib/utils'
import { m, useReducedMotion } from '@/components/shared/motion'
import { SPRING, EASE } from '@/lib/motion'

/**
 * "Buy Now" is a pure UI event (no backend call) that reveals the passkey
 * entry. Submitting verifies the passkey and redirects to the Razorpay link.
 * Error copy is whatever the backend returns in `detail` (exact spec wording:
 * "Incorrect passkey. N attempts remaining." / "You have been blocked…" /
 * "This listing has already been sold.").
 */
export default function BuyNowButton({ listingId, className }) {
  const reduced = useReducedMotion()
  const [open, setOpen] = useState(false)
  const [passkey, setPasskey] = useState('')
  const [error, setError] = useState(null)

  const { mutate, isPending } = useMutation({
    // API: POST /payments/verify-passkey
    mutationFn: () => api.post('/payments/verify-passkey', { listing_id: listingId, passkey }),
    onSuccess: ({ data }) => {
      window.location.href = data.payment_link_url
    },
    onError: (err) => {
      setError(err.response?.data?.detail || 'Something went wrong. Please try again.')
    },
  })

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className={cn('btn-primary', className)}>
        <ShoppingBag className="h-4 w-4" /> Buy Now
      </button>
    )
  }

  return (
    <m.div
      initial={reduced ? { opacity: 0 } : { opacity: 0, y: -6, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={SPRING}
      className="space-y-3 rounded-lg border border-border bg-card p-4 shadow-warm"
    >
      <div>
        <p className="text-sm font-medium text-foreground">Enter the 8-digit passkey</p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          The seller shares it at the meetup, once you&apos;ve inspected the material.
        </p>
      </div>
      <SegmentedPasskeyInput
        value={passkey}
        onChange={(v) => {
          setPasskey(v)
          setError(null)
        }}
        disabled={isPending}
        autoFocus
      />
      {error && (
        <m.p
          key={error}
          initial={{ opacity: 0 }}
          animate={reduced ? { opacity: 1 } : { opacity: 1, x: [0, -5, 5, -4, 4, 0] }}
          transition={{ duration: 0.4, ease: EASE.warm }}
          className="text-sm font-medium text-destructive"
        >
          {error}
        </m.p>
      )}
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => {
            setOpen(false)
            setPasskey('')
            setError(null)
          }}
          disabled={isPending}
          className="btn-ghost h-11 px-3"
          aria-label="Back"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={() => mutate()}
          disabled={passkey.length !== 8 || isPending}
          className="btn-primary flex-1"
        >
          {isPending ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" /> Verifying…
            </>
          ) : (
            'Confirm & pay'
          )}
        </button>
      </div>
    </m.div>
  )
}

'use client'
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import Link from 'next/link'
import { ShoppingBag, Loader2, ArrowLeft, CheckCircle2 } from 'lucide-react'
import api from '@/lib/api'
import SegmentedPasskeyInput from '@/components/shared/segmented-passkey-input'
import RateSeller from '@/components/shared/rate-seller'
import { cn } from '@/lib/utils'
import { m, useReducedMotion } from '@/components/shared/motion'
import { SPRING, EASE } from '@/lib/motion'

/**
 * "I've received the book" reveals the transaction-code entry. Submitting the
 * seller's 8-digit code verifies the exchange: the listing becomes SOLD and the
 * buyer is prompted to rate the seller. Error copy is whatever the backend returns
 * in `detail` ("Incorrect passkey. N attempts remaining." / "You have been
 * blocked…" / "This listing has already been sold.").
 */
export default function BuyNowButton({ listingId, className }) {
  const reduced = useReducedMotion()
  const [open, setOpen] = useState(false)
  const [passkey, setPasskey] = useState('')
  const [error, setError] = useState(null)
  const [completed, setCompleted] = useState(null) // { transaction_id, seller_name }

  const { mutate, isPending } = useMutation({
    // API: POST /transactions/verify-passkey
    mutationFn: () => api.post('/transactions/verify-passkey', { listing_id: listingId, passkey }),
    onSuccess: ({ data }) => {
      setCompleted(data)
    },
    onError: (err) => {
      setError(err.response?.data?.detail || 'Something went wrong. Please try again.')
    },
  })

  // Exchange confirmed — celebrate and prompt for a rating.
  if (completed) {
    return (
      <m.div
        initial={reduced ? { opacity: 0 } : { opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={SPRING}
        className="space-y-4 rounded-lg border border-[#bcd0a3] bg-[#e9f0dd] p-5 shadow-warm"
      >
        <div className="flex items-center gap-2 text-[#3f6733]">
          <CheckCircle2 className="h-5 w-5 shrink-0" />
          <p className="font-semibold">Exchange confirmed — this book is now yours.</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <RateSeller
            transactionId={completed.transaction_id}
            sellerName={completed.seller_name}
          />
        </div>
        <Link href="/dashboard?tab=transactions" className="btn-ghost w-full">
          Skip for now
        </Link>
      </m.div>
    )
  }

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className={cn('btn-primary', className)}>
        <ShoppingBag className="h-4 w-4" /> I&apos;ve received the book
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
        <p className="text-sm font-medium text-foreground">Enter the 8-digit code</p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          The seller shares it at the meetup, after you&apos;ve inspected the material and
          exchanged the book.
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
            'Confirm exchange'
          )}
        </button>
      </div>
    </m.div>
  )
}

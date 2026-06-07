'use client'
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import api from '@/lib/api'

export default function BuyNowButton({ listingId }) {
  const [showPasskey, setShowPasskey] = useState(false)
  const [passkey, setPasskey] = useState('')
  const [error, setError] = useState(null)

  const { mutate, isPending } = useMutation({
    mutationFn: () => api.post('/payments/verify-passkey', { listing_id: listingId, passkey }),
    onSuccess: ({ data }) => {
      window.location.href = data.payment_link_url
    },
    onError: (err) => {
      setError(err.response?.data?.detail || 'Something went wrong.')
    },
  })

  if (!showPasskey) {
    return (
      <button onClick={() => setShowPasskey(true)} className="btn-primary">
        Buy Now
      </button>
    )
  }

  return (
    <div className="mt-4 space-y-2">
      <p className="text-sm text-gray-600">Enter the 8-digit passkey the seller gives you at the meetup:</p>
      <div className="flex gap-2">
        <input
          type="text"
          inputMode="numeric"
          maxLength={8}
          value={passkey}
          onChange={e => setPasskey(e.target.value.replace(/\D/g, ''))}
          className="input font-mono tracking-widest w-36"
          placeholder="00000000"
        />
        <button
          onClick={() => mutate()}
          disabled={passkey.length !== 8 || isPending}
          className="btn-primary"
        >
          {isPending ? 'Verifying…' : 'Submit'}
        </button>
      </div>
      {error && <p className="text-red-600 text-sm">{error}</p>}
    </div>
  )
}

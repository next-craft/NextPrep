'use client'
import { useEffect, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import api from '@/lib/api'

const STORAGE_KEY = 'razorpay_onboarding_account_id'

export default function SellerOnboardPage() {
  const [accountId, setAccountId] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    setAccountId(sessionStorage.getItem(STORAGE_KEY))
  }, [])

  const start = useMutation({
    mutationFn: () => api.post('/payments/onboard').then(r => r.data),
    onSuccess: (data) => {
      if (data.razorpay_account_id) {
        sessionStorage.setItem(STORAGE_KEY, data.razorpay_account_id)
        setAccountId(data.razorpay_account_id)
      }
      if (data.onboarding_url) {
        window.location.href = data.onboarding_url
      }
    },
    onError: (err) => setError(err.response?.data?.detail || 'Something went wrong.'),
  })

  const complete = useMutation({
    mutationFn: () => api.post('/payments/onboard/complete', { razorpay_account_id: accountId }).then(r => r.data),
    onSuccess: () => {
      sessionStorage.removeItem(STORAGE_KEY)
      window.location.href = '/listings'
    },
    onError: (err) => setError(err.response?.data?.detail || 'Something went wrong.'),
  })

  return (
    <div className="max-w-md mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold">Connect your payment account</h1>
      <p className="text-sm text-gray-600">
        Sellers must complete a one-time KYC verification with Razorpay before listing items for sale.
        Payments go directly to your linked account — the platform never holds your money.
      </p>

      {!accountId && (
        <button onClick={() => start.mutate()} disabled={start.isPending} className="btn-primary">
          {start.isPending ? 'Starting…' : 'Connect Payment Account'}
        </button>
      )}

      {accountId && (
        <div className="space-y-2">
          <p className="text-sm text-gray-600">
            Already started your KYC on Razorpay? Confirm here once it's complete.
          </p>
          <button onClick={() => complete.mutate()} disabled={complete.isPending} className="btn-primary">
            {complete.isPending ? 'Checking…' : "I've completed KYC — confirm"}
          </button>
        </div>
      )}

      {error && <p className="text-red-600 text-sm">{error}</p>}
    </div>
  )
}

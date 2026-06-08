'use client'
import { useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

export default function CreateListingButton() {
  const router = useRouter()
  const { data: me } = useQuery({
    queryKey: ['me'],
    queryFn: () => api.get('/users/me').then(r => r.data),
  })

  const isReady = Boolean(me?.razorpay_account_id)

  return (
    <div>
      <button
        disabled={!isReady}
        className={isReady ? 'btn-primary' : 'btn-primary opacity-50 cursor-not-allowed'}
        onClick={() => isReady && router.push('/listings/new')}
      >
        Create Listing
      </button>
      {!isReady && (
        <p className="text-sm text-muted-foreground mt-1">
          Complete payment setup to start selling.{' '}
          <button onClick={() => router.push('/sell/onboard')} className="underline">
            Connect Payment Account
          </button>
        </p>
      )}
    </div>
  )
}

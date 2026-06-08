'use client'
import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

export default function TransactionStatusPage({ params }) {
  const { data, isLoading } = useQuery({
    queryKey: ['transaction-status', params.id],
    queryFn: () => api.get(`/transactions/${params.id}/status`).then(r => r.data),
    refetchInterval: (query) => query.state.data?.status === 'initiated' ? 2000 : false,
  })

  if (isLoading) return <p>Payment processing...</p>

  if (data?.status === 'released') {
    return (
      <div>
        <h1>Payment Successful</h1>
        <p>Your purchase is complete. Contact the seller to arrange pickup.</p>
      </div>
    )
  }

  if (data?.status === 'cancelled') {
    return (
      <div>
        <h1>Payment Cancelled</h1>
        <p>Your payment window expired. You have not been charged. Return to the listing to try again.</p>
      </div>
    )
  }

  return <p>Payment processing...</p>
}

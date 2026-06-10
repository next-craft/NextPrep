import { createServerSupabaseClient } from '@/lib/supabase/server'
import { formatPrice } from '@/lib/utils'
import BuyNowButton from '@/components/listings/BuyNowButton'
import MessageSellerButton from '@/components/listings/MessageSellerButton'
import { notFound } from 'next/navigation'

export default async function ListingDetailPage({ params }) {
  const res = await fetch(`${process.env.API_URL}/v1/listings/${params.id}`, {
    cache: 'no-store',
  })
  if (res.status === 404) notFound()
  const listing = await res.json()

  const supabase = await createServerSupabaseClient()
  const { data: { user } } = await supabase.auth.getUser()

  const isOwner = user?.id === listing.seller_id
  const isSold = listing.is_sold === true   // computed by backend; sold_at is never in response
  const isUnavailable = !listing.is_available && !isSold

  return (
    <div className="max-w-3xl mx-auto p-6">
      {isSold && (
        <div className="mb-4 rounded-md bg-red-50 px-4 py-3 text-red-700">
          This listing has been sold.
        </div>
      )}
      {isUnavailable && (
        <div className="mb-4 rounded-md bg-yellow-50 px-4 py-3 text-yellow-700">
          This listing is temporarily unavailable.
        </div>
      )}

      {listing.images?.length > 0 && (
        <div className="mb-6 overflow-x-auto flex gap-2">
          {listing.images.map((url, i) => (
            <img key={i} src={url} alt={listing.title} className="h-64 rounded-lg object-cover" />
          ))}
        </div>
      )}

      <h1 className="text-2xl font-bold">{listing.title}</h1>
      <div className="mt-2 text-3xl font-semibold text-green-700">
        {formatPrice(listing.asking_price)}
      </div>
      {listing.original_price && (
        <div className="text-sm text-gray-500 line-through">
          Original: {formatPrice(listing.original_price)}
        </div>
      )}

      <div className="mt-4 flex gap-2 flex-wrap">
        <span className="badge">{listing.listing_type}</span>
        <span className="badge">Condition {listing.condition}</span>
        <span className="badge">{listing.exam_category}</span>
        <span className="badge">{listing.city}</span>
      </div>

      {listing.subject && (
        <p className="mt-2 text-sm text-gray-600">Subject: {listing.subject}</p>
      )}

      {listing.description && (
        <p className="mt-4 whitespace-pre-wrap text-gray-700">{listing.description}</p>
      )}

      <p className="mt-4 text-xs text-gray-400">{listing.views} views</p>

      {!isOwner && user && listing.is_available && (
        <div className="mt-6 flex gap-3">
          <BuyNowButton listingId={listing.id} />
          <MessageSellerButton listingId={listing.id} />
        </div>
      )}

      {isOwner && (
        <div className="mt-6 flex gap-3">
          {/* Edit and passkey management are in the dashboard — /listings/[id]/edit is out of scope */}
          <a href={`/dashboard`} className="btn-secondary">
            Manage listing
          </a>
        </div>
      )}
    </div>
  )
}

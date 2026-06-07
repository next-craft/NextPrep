import { formatPrice } from '@/lib/utils'
import Link from 'next/link'

export default function ListingCard({ listing }) {
  return (
    <Link href={`/listings/${listing.id}`} className="block rounded-xl border hover:shadow-md transition">
      {listing.images?.[0] ? (
        <img src={listing.images[0]} alt={listing.title} className="h-48 w-full object-cover rounded-t-xl" />
      ) : (
        <div className="h-48 w-full bg-gray-100 rounded-t-xl flex items-center justify-center text-gray-400 text-sm">
          No image
        </div>
      )}
      <div className="p-4 space-y-1">
        <p className="font-semibold line-clamp-2">{listing.title}</p>
        <p className="text-lg font-bold text-green-700">{formatPrice(listing.asking_price)}</p>
        <div className="flex gap-2 flex-wrap text-xs text-gray-500">
          <span>{listing.listing_type}</span>
          <span>Cond. {listing.condition}</span>
          <span>{listing.city}</span>
        </div>
        <p className="text-xs text-gray-400">{listing.exam_category}</p>
      </div>
    </Link>
  )
}

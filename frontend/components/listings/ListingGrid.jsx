import ListingCard from './ListingCard'
import { cn } from '@/lib/utils'

/** Pure responsive grid. Empty-state handling lives in the page (it knows
 *  whether filters are active). */
export default function ListingGrid({ listings, className }) {
  return (
    <div
      className={cn(
        'grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4',
        className
      )}
    >
      {listings.map((listing) => (
        <ListingCard key={listing.id} listing={listing} />
      ))}
    </div>
  )
}

import ListingCard from './ListingCard'
import { Stagger, StaggerItem } from '@/components/shared/motion'
import { SPRING } from '@/lib/motion'
import { cn } from '@/lib/utils'

/** Pure responsive grid. Empty-state handling lives in the page (it knows
 *  whether filters are active). Cards reveal with a staggered fade-up as the
 *  grid scrolls into view (and re-reveal when the set changes on filter). */
export default function ListingGrid({ listings, className }) {
  return (
    <Stagger
      inView
      gap={0.05}
      className={cn(
        'grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4',
        className
      )}
    >
      {listings.map((listing) => (
        <StaggerItem
          key={listing.id}
          className="flex cv-card"
          whileHover={{ y: -5 }}
          transition={SPRING}
        >
          <ListingCard listing={listing} className="w-full" />
        </StaggerItem>
      ))}
    </Stagger>
  )
}

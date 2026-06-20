'use client'
import ProfileListingCard from './ProfileListingCard'
import { Stagger, StaggerItem } from '@/components/shared/motion'
import { SPRING } from '@/lib/motion'
import { cn } from '@/lib/utils'

/** Dense, compact grid for the public profile shelf. Distinct from the roomy
 *  marketplace ListingGrid: more columns, tighter gap, a snappier lift on hover.
 *  Cards reveal with a staggered fade-up as the section scrolls into view. */
export default function ProfileListingGrid({ listings, className }) {
  return (
    <Stagger
      inView
      gap={0.04}
      className={cn(
        'grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5',
        className
      )}
    >
      {listings.map((listing) => (
        <StaggerItem
          key={listing.id}
          className="flex"
          whileHover={{ y: -4 }}
          transition={SPRING}
        >
          <ProfileListingCard listing={listing} className="w-full" />
        </StaggerItem>
      ))}
    </Stagger>
  )
}

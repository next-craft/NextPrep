import Link from 'next/link'
import Image from 'next/image'
import { BookOpen } from 'lucide-react'
import {
  cn,
  listingStatus,
  isOptimizedImageHost,
  formatPrice,
  LISTING_TYPE_LABEL,
} from '@/lib/utils'
import { EXAM_CATEGORY_LABEL } from '@/constants/examCategories'

/**
 * Compact "shelf" card — used ONLY on the public profile (/users/[id]), where a
 * seller's wares should read as a dense collection rather than the roomy
 * marketplace card on /listings. Square thumbnail, price + grade overlaid on the
 * image, a small footer, and a bronze accent that wipes in on hover.
 *
 * Deliberately distinct from ListingCard (do not converge the two).
 */
export default function ProfileListingCard({ listing, className }) {
  const status = listingStatus(listing)
  const dimmed = status !== 'active'

  return (
    <Link
      href={`/listings/${listing.id}`}
      className={cn(
        'card group relative flex flex-col overflow-hidden transition-shadow duration-300 hover:shadow-warm-lg',
        className
      )}
    >
      <div className="relative aspect-square overflow-hidden bg-papaya_whip-700">
        {listing.images?.[0] ? (
          <Image
            src={listing.images[0]}
            alt={listing.title}
            fill
            unoptimized={!isOptimizedImageHost(listing.images[0])}
            sizes="(max-width: 640px) 50vw, (max-width: 1024px) 25vw, 20vw"
            className={cn(
              'object-contain transition-transform duration-500 ease-out group-hover:scale-[1.07]',
              dimmed && 'opacity-70'
            )}
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-light_bronze-500">
            <BookOpen className="h-8 w-8" />
          </div>
        )}

        {/* soft bottom scrim so the frosted price chip stays legible on any image */}
        <span
          aria-hidden
          className="pointer-events-none absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-black/25 to-transparent"
        />

        {/* lifecycle marker — top-left, only when not active */}
        {status === 'sold' && (
          <span className="absolute left-2 top-2 rounded-full border border-[#e4b3a6] bg-[#f7e6e0]/90 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[#8f3322] shadow-sm backdrop-blur-sm">
            Sold
          </span>
        )}
        {status === 'paused' && (
          <span className="absolute left-2 top-2 rounded-full border border-[#ecd6a0] bg-[#fbf1d6]/90 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[#8a5e12] shadow-sm backdrop-blur-sm">
            Paused
          </span>
        )}

        {/* condition grade — top-right white chip */}
        <span
          title={`Condition ${listing.condition}`}
          className="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-full border border-black/10 bg-white text-xs font-bold text-foreground shadow-sm"
        >
          {listing.condition}
        </span>

        {/* price — white pill, lifts gently on hover */}
        <span className="absolute bottom-2 left-2 rounded-full border border-black/10 bg-white px-2.5 py-0.5 font-display text-sm font-semibold text-foreground shadow-warm transition-transform duration-300 group-hover:-translate-y-0.5">
          {formatPrice(listing.asking_price)}
        </span>

        {/* hover accent — bronze wipe along the base of the image */}
        <span
          aria-hidden
          className="absolute inset-x-0 bottom-0 h-[3px] origin-left scale-x-0 bg-primary transition-transform duration-300 ease-out group-hover:scale-x-100"
        />
      </div>

      <div className="flex flex-1 flex-col gap-1 p-2.5">
        <h3 className="line-clamp-1 text-sm font-medium leading-snug text-foreground transition-colors group-hover:text-primary">
          {listing.title}
        </h3>
        <div className="mt-auto flex items-center gap-1.5 truncate text-[11px] text-muted-foreground">
          <span className="shrink-0">{LISTING_TYPE_LABEL[listing.listing_type] ?? listing.listing_type}</span>
          <span className="h-0.5 w-0.5 shrink-0 rounded-full bg-muted-foreground/50" />
          <span className="truncate">
            {EXAM_CATEGORY_LABEL[listing.exam_category] ?? listing.exam_category}
          </span>
        </div>
      </div>
    </Link>
  )
}

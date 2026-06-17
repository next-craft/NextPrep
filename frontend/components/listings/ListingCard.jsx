import Link from 'next/link'
import Image from 'next/image'
import { MapPin, BookOpen } from 'lucide-react'
import PriceBlock from '@/components/shared/price-block'
import { ConditionBadge, ListingTypeBadge } from '@/components/shared/badges'
import { cn, listingStatus } from '@/lib/utils'
import { EXAM_CATEGORY_LABEL } from '@/constants/examCategories'

export default function ListingCard({ listing, className }) {
  const status = listingStatus(listing)
  const dimmed = status !== 'active'

  return (
    <Link
      href={`/listings/${listing.id}`}
      className={cn(
        'card group flex flex-col overflow-hidden transition-shadow duration-300 hover:shadow-warm-lg',
        className
      )}
    >
      <div className="relative aspect-[4/3] overflow-hidden bg-papaya_whip-700">
        {listing.images?.[0] ? (
          <Image
            src={listing.images[0]}
            alt={listing.title}
            fill
            sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 25vw"
            className={cn(
              'object-cover transition-transform duration-500 ease-out group-hover:scale-105',
              dimmed && 'opacity-70'
            )}
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-light_bronze-500">
            <BookOpen className="h-10 w-10" />
          </div>
        )}
        {status === 'sold' && (
          <span className="badge absolute left-3 top-3 animate-scale-in border-[#e4b3a6] bg-[#f7e6e0] text-[#8f3322]">Sold</span>
        )}
        {status === 'paused' && (
          <span className="badge absolute left-3 top-3 animate-scale-in border-[#ecd6a0] bg-[#fbf1d6] text-[#8a5e12]">Paused</span>
        )}
      </div>

      <div className="flex flex-1 flex-col gap-2.5 p-4">
        <h3 className="line-clamp-2 font-medium leading-snug text-foreground">{listing.title}</h3>
        <PriceBlock asking={listing.asking_price} original={listing.original_price} size="sm" />

        <div className="mt-auto flex flex-wrap items-center gap-1.5 pt-1">
          <ListingTypeBadge type={listing.listing_type} />
          <ConditionBadge code={listing.condition} showLabel={false} />
        </div>

        <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
          <span className="inline-flex min-w-0 items-center gap-1">
            <MapPin className="h-3.5 w-3.5 shrink-0" />
            <span className="truncate">{listing.city}</span>
          </span>
          <span className="shrink-0 truncate text-right">
            {EXAM_CATEGORY_LABEL[listing.exam_category] ?? listing.exam_category}
          </span>
        </div>
      </div>
    </Link>
  )
}

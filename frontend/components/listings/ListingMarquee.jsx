import Link from 'next/link'
import Image from 'next/image'
import { MapPin, BookOpen } from 'lucide-react'
import { isOptimizedImageHost } from '@/lib/utils'

/* Fresh-listings marquee — one row of the latest listings that auto-scrolls
   left-to-right forever and pauses while hovered (anywhere on the row, incl.
   a card image). The track holds two identical copies and shifts by exactly
   one copy width, so the loop is seamless.

   Uses a compact card (image + title + city only — no price/badges) distinct
   from the full ListingCard used on grid pages. Pure CSS (group-hover pauses
   the animation), so this stays a server component and the cards remain
   crawlable. Reduced-motion → a normal horizontally-scrollable row. */

function MarqueeCard({ listing }) {
  const img = listing.images?.[0]
  return (
    <Link
      href={`/listings/${listing.id}`}
      className="card group flex flex-col overflow-hidden transition-shadow duration-300 hover:shadow-warm-lg"
    >
      <div className="relative aspect-[4/3] overflow-hidden bg-papaya_whip-700">
        {img ? (
          <Image
            src={img}
            alt={listing.title}
            fill
            unoptimized={!isOptimizedImageHost(img)}
            sizes="240px"
            className="object-cover transition-transform duration-500 ease-out group-hover:scale-105"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-light_bronze-500">
            <BookOpen className="h-9 w-9" />
          </div>
        )}
      </div>
      <div className="flex flex-col gap-1 p-4">
        <h3 className="line-clamp-1 font-medium leading-snug text-foreground">{listing.title}</h3>
        <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
          <MapPin className="h-3.5 w-3.5 shrink-0" />
          <span className="truncate">{listing.city}</span>
        </span>
      </div>
    </Link>
  )
}

export default function ListingMarquee({ listings }) {
  if (!listings?.length) return null

  // Duplicate the set so translateX(-50%) lands on an identical frame.
  const loop = [...listings, ...listings]

  return (
    <div className="group relative overflow-hidden [mask-image:linear-gradient(to_right,transparent,#000_5%,#000_95%,transparent)] motion-reduce:overflow-x-auto motion-reduce:[mask-image:none]">
      {/* cards drop their backdrop-blur here — it's unperceivable on fast-
          moving cards and re-blurring sliding cards is the costliest case */}
      <ul className="flex w-max transform-gpu will-change-transform animate-marquee group-hover:[animation-play-state:paused] motion-reduce:animate-none motion-reduce:will-change-auto [&_.card]:backdrop-blur-none">
        {loop.map((listing, i) => (
          <li
            key={`${listing.id}-${i}`}
            className="w-60 shrink-0 pr-4"
            aria-hidden={i >= listings.length || undefined}
          >
            <MarqueeCard listing={listing} />
          </li>
        ))}
      </ul>
    </div>
  )
}

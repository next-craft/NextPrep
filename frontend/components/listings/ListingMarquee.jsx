import ListingCard from '@/components/listings/ListingCard'

/* Fresh-listings marquee — one row of the latest listings that auto-scrolls
   left-to-right forever and pauses while hovered (anywhere on the row, incl.
   a card image). The track holds two identical copies and shifts by exactly
   one copy width, so the loop is seamless.

   Pure CSS (group-hover pauses the animation), so this stays a server
   component and the cards remain crawlable. Reduced-motion users get a normal
   horizontally-scrollable row instead of the animation. Edge fades come from a
   mask so they work over the aurora regardless of hue. */

export default function ListingMarquee({ listings }) {
  if (!listings?.length) return null

  // Duplicate the set so translateX(-50%) lands on an identical frame.
  const loop = [...listings, ...listings]

  return (
    <div className="group relative overflow-hidden [mask-image:linear-gradient(to_right,transparent,#000_5%,#000_95%,transparent)] motion-reduce:overflow-x-auto motion-reduce:[mask-image:none]">
      {/* cards drop their backdrop-blur here — it's unperceivable on fast-
          moving cards and re-blurring 24 sliding cards is the costliest case */}
      <ul className="flex w-max transform-gpu will-change-transform animate-marquee group-hover:[animation-play-state:paused] motion-reduce:animate-none motion-reduce:will-change-auto [&_.card]:backdrop-blur-none">
        {loop.map((listing, i) => (
          <li
            key={`${listing.id}-${i}`}
            className="w-72 shrink-0 pr-5"
            aria-hidden={i >= listings.length || undefined}
          >
            <ListingCard listing={listing} />
          </li>
        ))}
      </ul>
    </div>
  )
}

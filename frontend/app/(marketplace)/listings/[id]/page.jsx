import { cache } from 'react'
import { createServerSupabaseClient } from '@/lib/supabase/server'
import { notFound } from 'next/navigation'
import Link from 'next/link'
import { MapPin, Eye, BadgeCheck, ChevronRight, ShieldCheck, Settings, Clock } from 'lucide-react'
import { conditionMeta, listingStatus, formatPrice, LISTING_TYPE_LABEL, formatRelativeTime, formatDate } from '@/lib/utils'
import { EXAM_CATEGORY_LABEL } from '@/constants/examCategories'
import JsonLd from '@/components/shared/json-ld'
import PriceBlock from '@/components/shared/price-block'
import { ConditionBadge, ListingTypeBadge, ExamCategoryChip } from '@/components/shared/badges'
import Avatar from '@/components/shared/avatar'
import ListingGallery from '@/components/listings/ListingGallery'
import BuyNowButton from '@/components/listings/BuyNowButton'
import MessageSellerButton from '@/components/listings/MessageSellerButton'
import ReportListingDialog from '@/components/listings/ReportListingDialog'
import { Reveal, Stagger, StaggerItem } from '@/components/shared/motion'

export const revalidate = 0

// cache() dedupes this across generateMetadata, the OG image route, and the page
// render within a single request — without it the listing is fetched 3×.
// Forward the signed-in user's token so the API can identify the viewer: views
// are counted once per non-owner account (the owner's own opens never count).
const getListing = cache(async function getListing(id) {
  const supabase = await createServerSupabaseClient()
  const {
    data: { session },
  } = await supabase.auth.getSession()
  const headers = session?.access_token
    ? { Authorization: `Bearer ${session.access_token}` }
    : undefined

  const res = await fetch(`${process.env.API_URL}/listings/${id}`, {
    cache: 'no-store',
    headers,
  })
  if (res.status === 404) return { notFound: true }
  if (!res.ok) return { error: true }
  return { listing: await res.json() }
})

export async function generateMetadata({ params }) {
  const { id } = await params
  try {
    const { listing } = await getListing(id)
    if (listing) {
      const examLabel = EXAM_CATEGORY_LABEL[listing.exam_category] ?? listing.exam_category
      const description =
        listing.description?.slice(0, 155) ||
        `${examLabel} ${LISTING_TYPE_LABEL[listing.listing_type] ?? 'study material'} for ${formatPrice(
          listing.asking_price
        )} in ${listing.city}.`
      const canonical = `/listings/${id}`
      // Sold/paused listings are terminal — keep them out of the index to avoid
      // soft-404s and stale results, while staying reachable for direct links.
      const indexable = listingStatus(listing) === 'active'
      return {
        title: listing.title,
        description,
        alternates: { canonical },
        robots: indexable ? undefined : { index: false, follow: true },
        openGraph: {
          type: 'website',
          title: listing.title,
          description,
          url: `https://nextprep.online${canonical}`,
        },
        twitter: { card: 'summary_large_image', title: listing.title, description },
      }
    }
  } catch {
    /* fall through */
  }
  return { title: 'Listing' }
}

export default async function ListingDetailPage({ params }) {
  const { id } = await params
  const { listing, notFound: missing } = await getListing(id)
  if (missing) notFound()

  // API: GET /users/{id} — public seller profile for the seller card
  let seller = null
  if (listing?.seller_id) {
    try {
      const sr = await fetch(`${process.env.API_URL}/users/${listing.seller_id}`, {
        cache: 'no-store',
      })
      if (sr.ok) seller = await sr.json()
    } catch {
      /* seller card is optional */
    }
  }

  const supabase = await createServerSupabaseClient()
  const {
    data: { user },
  } = await supabase.auth.getUser()

  const isOwner = user?.id === listing.seller_id
  const status = listingStatus(listing)
  const isAvailable = status === 'active'

  const url = `https://nextprep.online/listings/${listing.id}`
  const productJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'Product',
    name: listing.title,
    description:
      listing.description || `${EXAM_CATEGORY_LABEL[listing.exam_category] ?? listing.exam_category} study material`,
    category: EXAM_CATEGORY_LABEL[listing.exam_category] ?? listing.exam_category,
    ...(listing.images?.length ? { image: listing.images } : {}),
    ...(listing.subject ? { material: listing.subject } : {}),
    offers: {
      '@type': 'Offer',
      url,
      priceCurrency: 'INR',
      price: listing.asking_price,
      // All items are pre-owned; condition grade A/B/C is conveyed in the listing copy.
      itemCondition: 'https://schema.org/UsedCondition',
      availability: isAvailable
        ? 'https://schema.org/InStock'
        : 'https://schema.org/SoldOut',
      areaServed: [listing.city, listing.state].filter(Boolean).join(', '),
      ...(seller
        ? {
            seller: {
              '@type': 'Person',
              name: seller.full_name,
              url: `https://nextprep.online/users/${seller.id}`,
            },
          }
        : {}),
    },
    ...(seller?.seller_rating && seller.books_sold
      ? {
          aggregateRating: {
            '@type': 'AggregateRating',
            ratingValue: seller.seller_rating,
            reviewCount: seller.books_sold,
            bestRating: 5,
          },
        }
      : {}),
  }
  const breadcrumbJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://nextprep.online' },
      { '@type': 'ListItem', position: 2, name: 'Browse', item: 'https://nextprep.online/listings' },
      { '@type': 'ListItem', position: 3, name: listing.title, item: url },
    ],
  }

  const cond = conditionMeta(listing.condition)

  return (
    <div className="container py-8 lg:py-12">
      <JsonLd data={[productJsonLd, breadcrumbJsonLd]} />
      <Link
        href="/listings"
        className="group mb-6 inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <span aria-hidden className="transition-transform duration-200 group-hover:-translate-x-1">←</span>
        Back to listings
      </Link>

      {status === 'sold' && (
        <Reveal y={-8} className="mb-6 rounded-xl border border-[#e4b3a6] bg-[#f7e6e0] px-4 py-3 text-sm font-medium text-[#8f3322]">
          This listing has been sold.
        </Reveal>
      )}
      {status === 'paused' && (
        <Reveal y={-8} className="mb-6 rounded-xl border border-[#ecd6a0] bg-[#fbf1d6] px-4 py-3 text-sm font-medium text-[#8a5e12]">
          This listing is temporarily unavailable.
        </Reveal>
      )}

      <div className="grid items-start gap-8 lg:grid-cols-[1.05fr_0.95fr] lg:gap-12">
        {/* Gallery — a matted "frame" lifts on hover; a library-style ink
            grade stamp settles onto the corner on load (CSS animation only).
            Solid fills (no backdrop-blur) so scroll/hover stay smooth. */}
        <Reveal whileHover={{ y: -3 }}>
          <div className="relative rounded-2xl border border-white/50 bg-gradient-to-br from-papaya_whip-700 to-cornsilk-700 p-3 shadow-warm-lg sm:p-4">
            <ListingGallery images={listing.images || []} title={listing.title} />

            <div
              aria-hidden
              className="pointer-events-none absolute right-4 top-4 z-10 sm:right-6 sm:top-6"
              style={{ animation: 'stamp-in 0.7s cubic-bezier(0.22,1,0.36,1) 0.4s both' }}
            >
              <div
                className="flex h-20 w-20 flex-col items-center justify-center rounded-full border-2 border-light_bronze-300/70 bg-cornsilk-600/80 text-center text-light_bronze-300 sm:h-24 sm:w-24"
                style={{ boxShadow: 'inset 0 0 0 3px rgba(150,98,46,0.22)' }}
              >
                <span className="text-[9px] font-semibold uppercase tracking-[0.2em]">Grade</span>
                <span className="font-display text-3xl font-bold leading-none sm:text-4xl">{listing.condition}</span>
                <span className="whitespace-nowrap text-[8px] font-medium uppercase tracking-[0.14em]">{cond.short}</span>
              </div>
            </div>
          </div>
        </Reveal>

        {/* Purchase rail — one cohesive glass panel. The sticky wrapper stays
            untransformed; its inner content sequences in (transforms on
            children don't break sticky). */}
        <div className="lg:sticky lg:top-24 lg:self-start">
          <div className="rounded-2xl border border-white/50 bg-card/95 p-6 shadow-warm-lg sm:p-7">
            <Stagger gap={0.07}>
              <StaggerItem className="mb-3 flex flex-wrap items-center gap-1.5">
                <ListingTypeBadge type={listing.listing_type} />
                <ExamCategoryChip value={listing.exam_category} />
              </StaggerItem>

              <StaggerItem as="h1" className="font-display text-2xl font-semibold leading-tight sm:text-[2rem]">
                {listing.title}
              </StaggerItem>

              <StaggerItem className="mt-4">
                <PriceBlock asking={listing.asking_price} original={listing.original_price} size="lg" />
              </StaggerItem>

              <StaggerItem className="mt-5 flex flex-wrap items-center gap-x-3 gap-y-2">
                <ConditionBadge code={listing.condition} />
                <Dot />
                <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
                  <MapPin className="h-4 w-4" /> {listing.state ? `${listing.city}, ${listing.state}` : listing.city}
                </span>
                <Dot />
                <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
                  <Eye className="h-4 w-4" /> {listing.views} views
                </span>
                {listing.created_at && (
                  <>
                    <Dot />
                    <span
                      className="inline-flex items-center gap-1.5 text-sm text-muted-foreground"
                      title={`Listed ${formatDate(listing.created_at)}`}
                    >
                      <Clock className="h-4 w-4" /> Listed {formatRelativeTime(listing.created_at)}
                    </span>
                  </>
                )}
              </StaggerItem>

              <StaggerItem>
                <p className="mt-3 text-sm text-muted-foreground">{cond.full}</p>
                {listing.subject && (
                  <p className="mt-1 text-sm text-muted-foreground">
                    Subject: <span className="font-medium text-foreground">{listing.subject}</span>
                  </p>
                )}
                {listing.edition && (
                  <p className="mt-1 text-sm text-muted-foreground">
                    Edition: <span className="font-medium text-foreground">{listing.edition}</span>
                  </p>
                )}
                {listing.year && (
                  <p className="mt-1 text-sm text-muted-foreground">
                    Year: <span className="font-medium text-foreground">{listing.year}</span>
                  </p>
                )}
              </StaggerItem>

              <StaggerItem className="my-6 h-px bg-gradient-to-r from-transparent via-border to-transparent" />

              {/* Seller card */}
              {seller && (
                <StaggerItem whileHover={{ y: -3 }}>
                  <Link
                    href={`/users/${seller.id}`}
                    className="group flex items-center gap-3 rounded-xl border border-border bg-papaya_whip-800/60 p-4 shadow-warm transition-colors hover:border-light_bronze-500"
                  >
                    <Avatar src={seller.avatar_url} name={seller.full_name} size={48} />
                    <div className="min-w-0 flex-1">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                        Seller
                      </p>
                      <p className="flex items-center gap-1 font-medium">
                        <span className="truncate">{seller.full_name}</span>
                        {seller.is_verified && <BadgeCheck className="h-4 w-4 shrink-0 text-primary" />}
                      </p>
                      <p className="truncate text-xs text-muted-foreground">
                        {seller.city ? `${seller.city} · ` : ''}
                        {seller.books_sold} {seller.books_sold === 1 ? 'sale' : 'sales'}
                        {seller.seller_rating ? ` · ★ ${seller.seller_rating}` : ''}
                      </p>
                    </div>
                    <ChevronRight className="h-5 w-5 shrink-0 text-muted-foreground transition-transform duration-200 group-hover:translate-x-1" />
                  </Link>
                </StaggerItem>
              )}

              {/* Actions */}
              <StaggerItem className="mt-6">
                {isOwner ? (
                  <Link href="/dashboard" className="btn-secondary w-full">
                    <Settings className="h-4 w-4" /> Manage listing
                  </Link>
                ) : isAvailable && user ? (
                  <div className="space-y-3">
                    <div className="flex flex-wrap gap-3">
                      <BuyNowButton listingId={listing.id} className="flex-1" />
                      <MessageSellerButton listingId={listing.id} className="flex-1" />
                    </div>
                    <p className="flex items-start gap-2.5 rounded-xl border border-tea_green-500/60 bg-tea_green-800/50 p-3.5 text-xs leading-relaxed text-secondary-foreground">
                      <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                      <span>
                        Meet in a public place, inspect the material, and settle payment directly with
                        the seller. Then enter the seller&apos;s code here to confirm the exchange.{' '}
                        <span className="font-semibold">Never share the code over chat.</span>
                      </span>
                    </p>
                  </div>
                ) : isAvailable && !user ? (
                  <Link href="/login" className="btn-primary w-full">
                    Continue with Google to buy or chat
                  </Link>
                ) : null}
              </StaggerItem>

              {/* Report — available to any non-owner viewer, in any listing state */}
              {!isOwner && (
                <StaggerItem className="mt-4 flex justify-end">
                  <ReportListingDialog listingId={listing.id} isLoggedIn={!!user} />
                </StaggerItem>
              )}
            </Stagger>
          </div>
        </div>
      </div>

      {/* Description — editorial column with a kicker rule */}
      {listing.description && (
        <Reveal inView className="cv-auto mt-14 max-w-3xl">
          <div className="mb-4 flex items-center gap-3">
            <h2 className="text-xs font-semibold uppercase tracking-[0.22em] text-light_bronze-300">
              Description
            </h2>
            <span className="h-px flex-1 bg-gradient-to-r from-light_bronze-500/50 to-transparent" />
          </div>
          <p className="whitespace-pre-wrap text-[0.95rem] leading-7 text-foreground/90">
            {listing.description}
          </p>
        </Reveal>
      )}
    </div>
  )
}

/** Small inline separator dot for the meta row. */
function Dot() {
  return <span aria-hidden className="h-1 w-1 shrink-0 rounded-full bg-light_bronze-500/70" />
}

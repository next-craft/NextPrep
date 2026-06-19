import { cache } from 'react'
import { createServerSupabaseClient } from '@/lib/supabase/server'
import { notFound } from 'next/navigation'
import Link from 'next/link'
import { MapPin, Eye, BadgeCheck, ChevronRight, ShieldCheck, Settings } from 'lucide-react'
import { conditionMeta, listingStatus, formatPrice, LISTING_TYPE_LABEL } from '@/lib/utils'
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
      areaServed: listing.city,
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

  return (
    <div className="container py-6 lg:py-8">
      <JsonLd data={[productJsonLd, breadcrumbJsonLd]} />
      <Link href="/listings" className="mb-5 inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground">
        ← Back to listings
      </Link>

      {status === 'sold' && (
        <Reveal y={-8} className="mb-5 rounded-lg border border-[#e4b3a6] bg-[#f7e6e0] px-4 py-3 text-sm font-medium text-[#8f3322]">
          This listing has been sold.
        </Reveal>
      )}
      {status === 'paused' && (
        <Reveal y={-8} className="mb-5 rounded-lg border border-[#ecd6a0] bg-[#fbf1d6] px-4 py-3 text-sm font-medium text-[#8a5e12]">
          This listing is temporarily unavailable.
        </Reveal>
      )}

      <div className="grid gap-8 lg:grid-cols-2">
        {/* Gallery */}
        <Reveal>
          <ListingGallery images={listing.images || []} title={listing.title} />
        </Reveal>

        {/* Summary + actions — sticky wrapper stays untransformed; its inner
            content sequences in (transforms on children don't break sticky). */}
        <div className="lg:sticky lg:top-20 lg:self-start">
          <Stagger gap={0.07}>
            <StaggerItem className="mb-3 flex flex-wrap items-center gap-1.5">
              <ListingTypeBadge type={listing.listing_type} />
              <ExamCategoryChip value={listing.exam_category} />
            </StaggerItem>

            <StaggerItem as="h1" className="font-display text-2xl font-semibold leading-tight sm:text-3xl">
              {listing.title}
            </StaggerItem>

            <StaggerItem className="mt-4">
              <PriceBlock asking={listing.asking_price} original={listing.original_price} size="lg" />
            </StaggerItem>

            <StaggerItem className="mt-5 flex flex-wrap items-center gap-2">
              <ConditionBadge code={listing.condition} />
              <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
                <MapPin className="h-4 w-4" /> {listing.city}
              </span>
              <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
                <Eye className="h-4 w-4" /> {listing.views} views
              </span>
            </StaggerItem>

            <StaggerItem>
              <p className="mt-2 text-sm text-muted-foreground">{conditionMeta(listing.condition).full}</p>
              {listing.subject && (
                <p className="mt-1 text-sm text-muted-foreground">
                  Subject: <span className="text-foreground">{listing.subject}</span>
                </p>
              )}
            </StaggerItem>

            {/* Seller card */}
            {seller && (
              <StaggerItem whileHover={{ y: -3 }}>
                <Link
                  href={`/users/${seller.id}`}
                  className="card group mt-6 flex items-center gap-3 p-4 transition-colors hover:border-light_bronze-500"
                >
                  <Avatar src={seller.avatar_url} name={seller.full_name} size={48} />
                  <div className="min-w-0 flex-1">
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
                <p className="flex items-start gap-2 rounded-lg bg-secondary/60 p-3 text-xs text-secondary-foreground">
                  <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />
                  Meet in a public place, inspect the material, and settle payment directly with the
                  seller. Then enter the seller&apos;s code here to confirm the exchange. Never share
                  the code over chat.
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

      {/* Description */}
      {listing.description && (
        <Reveal inView className="mt-10 max-w-3xl">
          <h2 className="font-display text-lg font-semibold">Description</h2>
          <p className="mt-2 whitespace-pre-wrap leading-relaxed text-foreground/90">
            {listing.description}
          </p>
        </Reveal>
      )}
    </div>
  )
}

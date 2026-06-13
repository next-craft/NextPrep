import { createServerSupabaseClient } from '@/lib/supabase/server'
import { notFound } from 'next/navigation'
import Link from 'next/link'
import { MapPin, Eye, BadgeCheck, ChevronRight, ShieldCheck, Settings } from 'lucide-react'
import { conditionMeta, listingStatus } from '@/lib/utils'
import PriceBlock from '@/components/shared/price-block'
import { ConditionBadge, ListingTypeBadge, ExamCategoryChip } from '@/components/shared/badges'
import Avatar from '@/components/shared/avatar'
import ListingGallery from '@/components/listings/ListingGallery'
import BuyNowButton from '@/components/listings/BuyNowButton'
import MessageSellerButton from '@/components/listings/MessageSellerButton'
import { Reveal, Stagger, StaggerItem } from '@/components/shared/motion'

export const revalidate = 0

async function getListing(id) {
  const res = await fetch(`${process.env.API_URL}/listings/${id}`, { cache: 'no-store' })
  if (res.status === 404) return { notFound: true }
  if (!res.ok) return { error: true }
  return { listing: await res.json() }
}

export async function generateMetadata({ params }) {
  const { id } = await params
  try {
    const { listing } = await getListing(id)
    if (listing) {
      return {
        title: listing.title,
        description: listing.description?.slice(0, 150) || `${listing.exam_category} study material`,
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

  return (
    <div className="container py-6 lg:py-8">
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
                      {seller.total_sales} {seller.total_sales === 1 ? 'sale' : 'sales'}
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
                  Meet in a public place, inspect the material, then pay. Never share or enter your
                  passkey over chat.
                </p>
              </div>
            ) : isAvailable && !user ? (
              <Link href="/login" className="btn-primary w-full">
                Continue with Google to buy or chat
              </Link>
            ) : null}
            </StaggerItem>
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

import ListingGrid from '@/components/listings/ListingGrid'
import ListingFilters from '@/components/listings/ListingFilters'
import { FILTER_KEYS } from '@/constants/filters'
import MobileFilters from '@/components/listings/MobileFilters'
import CreateListingButton from '@/components/listings/CreateListingButton'
import { EmptyState, ErrorState } from '@/components/shared/states'
import ResultCount from '@/components/listings/ResultCount'
import { Reveal } from '@/components/shared/motion'
import { Compass, SearchX } from 'lucide-react'
import JsonLd from '@/components/shared/json-ld'

const listingsJsonLd = [
  {
    '@context': 'https://schema.org',
    '@type': 'CollectionPage',
    name: 'Browse study material',
    description: 'Books, notes and coaching modules for JEE, NEET, UPSC, CA and more.',
    url: 'https://nextprep.online/listings',
    isPartOf: { '@id': 'https://nextprep.online/#website' },
  },
  {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://nextprep.online' },
      { '@type': 'ListItem', position: 2, name: 'Browse', item: 'https://nextprep.online/listings' },
    ],
  },
]

export const revalidate = 0 // always fresh — ISR not needed here
export const metadata = {
  title: 'Browse study material',
  description: 'Browse books, notes and coaching modules for JEE, NEET, UPSC, CA and more.',
  // All filter permutations (?q, ?exam_category, ?city…) are near-duplicate thin
  // pages — canonical them to the clean URL to avoid index bloat.
  alternates: { canonical: '/listings' },
  openGraph: {
    title: 'Browse study material · NextPrep',
    description: 'Browse books, notes and coaching modules for JEE, NEET, UPSC, CA and more.',
    url: 'https://nextprep.online/listings',
  },
}

export default async function ListingsPage({ searchParams }) {
  const sp = await searchParams // Next 16: searchParams is a Promise, must be awaited
  const params = new URLSearchParams()
  FILTER_KEYS.forEach((k) => {
    if (sp[k]) params.set(k, String(sp[k]))
  })
  const hasFilters = FILTER_KEYS.some((k) => sp[k])

  // API: GET /listings — public, additive AND filters (q, exam_category, etc.)
  let listings = []
  let failed = false
  try {
    const res = await fetch(`${process.env.API_URL}/listings?${params.toString()}`, {
      cache: 'no-store',
    })
    if (res.ok) listings = await res.json()
    else failed = true
  } catch {
    failed = true
  }

  return (
    <div className="container py-6 lg:py-8">
      <JsonLd data={listingsJsonLd} />
      <Reveal className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold sm:text-3xl">Browse study material</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Books, notes &amp; coaching modules — one unified stream.
          </p>
        </div>
        <div className="hidden sm:block">
          <CreateListingButton />
        </div>
      </Reveal>

      {/* mobile toolbar */}
      <div className="mt-6 flex items-center justify-between gap-3 lg:hidden">
        <MobileFilters current={sp} />
        {!failed && (
          <ResultCount count={listings.length} className="text-sm text-muted-foreground" />
        )}
      </div>

      <div className="mt-6 flex gap-8">
        <aside className="hidden w-64 shrink-0 lg:block">
          <div className="sticky top-20">
            <ListingFilters current={sp} />
          </div>
        </aside>

        <div className="min-w-0 flex-1">
          {failed ? (
            <ErrorState
              title="Couldn't load listings"
              description="We hit a snag reaching the marketplace. Please try again in a moment."
            />
          ) : listings.length === 0 ? (
            hasFilters ? (
              <EmptyState
                icon={SearchX}
                title="No listings found for your filters"
                description="Try removing a filter or broadening your search."
                action={
                  <a href="/listings" className="btn-secondary">
                    Clear filters
                  </a>
                }
              />
            ) : (
              <EmptyState
                icon={Compass}
                title="Be the first to list study material in your city"
                description="Sell your old JEE, NEET, UPSC or CA books, notes and modules to students who need them."
                action={
                  <a href="/listings/new" className="btn-primary">
                    Create a listing
                  </a>
                }
              />
            )
          ) : (
            <>
              <ResultCount
                count={listings.length}
                className="mb-4 hidden text-sm text-muted-foreground lg:block"
              />
              {/* Remount on any filter/search change so the staggered scroll-reveal
                  runs fresh — otherwise a soft (same-route) navigation leaves the
                  new cards stuck in their hidden (opacity-0) state. */}
              <ListingGrid key={params.toString()} listings={listings} />
            </>
          )}
        </div>
      </div>
    </div>
  )
}

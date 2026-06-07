import ListingGrid from '@/components/listings/ListingGrid'
import ListingFilters from '@/components/listings/ListingFilters'

export const revalidate = 0  // always fresh — ISR not needed here

export default async function ListingsPage({ searchParams }) {
  const params = new URLSearchParams()
  const keys = ['q', 'exam_category', 'subject', 'city', 'condition', 'listing_type']
  keys.forEach(k => { if (searchParams[k]) params.set(k, searchParams[k]) })

  const res = await fetch(
    `${process.env.API_URL}/v1/listings?${params.toString()}`,
    { cache: 'no-store' }
  )
  const listings = res.ok ? await res.json() : []

  return (
    <div className="flex gap-6 p-6">
      <aside className="w-64 shrink-0">
        <ListingFilters current={searchParams} />
      </aside>
      <main className="flex-1">
        <ListingGrid listings={listings} />
      </main>
    </div>
  )
}

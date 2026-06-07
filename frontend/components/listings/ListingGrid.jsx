import ListingCard from './ListingCard'

export default function ListingGrid({ listings }) {
  if (!listings.length) {
    return (
      <p className="text-gray-500 text-center py-20">
        No listings found for your filters. Try removing a filter or broadening your search.
      </p>
    )
  }
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {listings.map(l => <ListingCard key={l.id} listing={l} />)}
    </div>
  )
}

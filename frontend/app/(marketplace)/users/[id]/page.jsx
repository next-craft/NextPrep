import { notFound } from 'next/navigation'
import { MapPin, BadgeCheck, BookOpen, Star } from 'lucide-react'
import Avatar from '@/components/shared/avatar'
import ListingGrid from '@/components/listings/ListingGrid'
import { EmptyState } from '@/components/shared/states'
import { formatDate } from '@/lib/utils'

export const revalidate = 0

export async function generateMetadata({ params }) {
  const { id } = await params
  try {
    const r = await fetch(`${process.env.API_URL}/users/${id}`, { cache: 'no-store' })
    if (r.ok) {
      const u = await r.json()
      return { title: u.full_name, description: `Study material listed by ${u.full_name} on NextPrep.` }
    }
  } catch {
    /* fall through */
  }
  return { title: 'Profile' }
}

export default async function UserProfilePage({ params }) {
  const { id } = await params

  // API: GET /users/{id} — public profile
  let user = null
  try {
    const res = await fetch(`${process.env.API_URL}/users/${id}`, { cache: 'no-store' })
    if (res.status === 404 || !res.ok) notFound()
    user = await res.json()
  } catch {
    notFound()
  }

  // API: GET /listings?seller_id={id} — the seller's public (active) listings
  let listings = []
  try {
    const lr = await fetch(`${process.env.API_URL}/listings?seller_id=${id}`, { cache: 'no-store' })
    if (lr.ok) listings = await lr.json()
  } catch {
    listings = []
  }

  return (
    <div className="container py-8">
      <header className="flex flex-col items-center gap-5 text-center sm:flex-row sm:text-left">
        <Avatar src={user.avatar_url} name={user.full_name} size={84} />
        <div>
          <h1 className="flex items-center justify-center gap-2 font-display text-2xl font-semibold sm:justify-start sm:text-3xl">
            <span>{user.full_name}</span>
            {user.is_verified && <BadgeCheck className="h-6 w-6 text-primary" />}
          </h1>
          <div className="mt-2 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-sm text-muted-foreground sm:justify-start">
            {user.city && (
              <span className="inline-flex items-center gap-1">
                <MapPin className="h-4 w-4" /> {user.city}
              </span>
            )}
            <span>
              {user.total_sales} {user.total_sales === 1 ? 'sale' : 'sales'}
            </span>
            {user.seller_rating != null && (
              <span className="inline-flex items-center gap-1">
                <Star className="h-4 w-4 fill-current text-light_bronze-400" /> {user.seller_rating}
              </span>
            )}
            {user.created_at && <span>Joined {formatDate(user.created_at)}</span>}
          </div>
        </div>
      </header>

      <section className="mt-10">
        <h2 className="mb-4 font-display text-lg font-semibold">Active listings</h2>
        {listings.length ? (
          <ListingGrid listings={listings} />
        ) : (
          <EmptyState
            icon={BookOpen}
            title="No active listings"
            description={`${user.full_name} has nothing listed right now.`}
          />
        )}
      </section>
    </div>
  )
}

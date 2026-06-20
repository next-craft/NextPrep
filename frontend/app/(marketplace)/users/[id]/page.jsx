import { cache } from 'react'
import { notFound } from 'next/navigation'
import { MapPin, BadgeCheck, BookOpen, Star } from 'lucide-react'
import Avatar from '@/components/shared/avatar'
import ProfileListingGrid from '@/components/listings/ProfileListingGrid'
import { EmptyState } from '@/components/shared/states'
import { Reveal, Stagger, StaggerItem } from '@/components/shared/motion'
import { formatDate } from '@/lib/utils'
import JsonLd from '@/components/shared/json-ld'

export const revalidate = 0

// Deduped across generateMetadata and the page render within one request.
const getUser = cache(async function getUser(id) {
  const r = await fetch(`${process.env.API_URL}/users/${id}`, { cache: 'no-store' })
  if (!r.ok) return null
  return r.json()
})

export async function generateMetadata({ params }) {
  const { id } = await params
  try {
    const u = await getUser(id)
    if (u) {
      const description = `Study material listed by ${u.full_name}${
        u.city ? ` in ${u.city}` : ''
      } on NextPrep — ${u.books_sold} ${u.books_sold === 1 ? 'sale' : 'sales'}.`
      return {
        title: u.full_name,
        description,
        alternates: { canonical: `/users/${id}` },
        openGraph: {
          type: 'profile',
          title: `${u.full_name} · NextPrep`,
          description,
          url: `https://nextprep.online/users/${id}`,
        },
      }
    }
  } catch {
    /* fall through */
  }
  return { title: 'Profile' }
}

export default async function UserProfilePage({ params }) {
  const { id } = await params

  // API: GET /users/{id} — public profile (deduped with generateMetadata via cache())
  const user = await getUser(id)
  if (!user) notFound()

  // API: GET /listings?seller_id={id} — the seller's public (active) listings
  let listings = []
  try {
    const lr = await fetch(`${process.env.API_URL}/listings?seller_id=${id}`, { cache: 'no-store' })
    if (lr.ok) listings = await lr.json()
  } catch {
    listings = []
  }

  const profileJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'ProfilePage',
    mainEntity: {
      '@type': 'Person',
      name: user.full_name,
      url: `https://nextprep.online/users/${id}`,
      ...(user.avatar_url ? { image: user.avatar_url } : {}),
      ...(user.city ? { homeLocation: { '@type': 'Place', name: user.city } } : {}),
      ...(user.seller_rating && user.books_sold
        ? {
            aggregateRating: {
              '@type': 'AggregateRating',
              ratingValue: user.seller_rating,
              reviewCount: user.books_sold,
              bestRating: 5,
            },
          }
        : {}),
    },
  }
  const breadcrumbJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://nextprep.online' },
      { '@type': 'ListItem', position: 2, name: 'Browse', item: 'https://nextprep.online/listings' },
      { '@type': 'ListItem', position: 3, name: user.full_name, item: `https://nextprep.online/users/${id}` },
    ],
  }

  return (
    <div className="container py-8">
      <JsonLd data={[profileJsonLd, breadcrumbJsonLd]} />
      <Stagger as="header" gap={0.1} className="flex flex-col items-center gap-5 text-center sm:flex-row sm:text-left">
        <StaggerItem>
          <Avatar src={user.avatar_url} name={user.full_name} size={84} />
        </StaggerItem>
        <StaggerItem>
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
              {user.books_sold} {user.books_sold === 1 ? 'sale' : 'sales'}
            </span>
            <span>
              {user.books_bought} bought
            </span>
            {user.seller_rating != null && (
              <span className="inline-flex items-center gap-1">
                <Star className="h-4 w-4 fill-current text-light_bronze-400" /> {user.seller_rating}
                {user.books_sold > 0 && (
                  <span className="text-muted-foreground"> · {user.books_sold} verified</span>
                )}
              </span>
            )}
            {user.created_at && <span>Joined {formatDate(user.created_at)}</span>}
          </div>
        </StaggerItem>
      </Stagger>

      <section className="mt-10">
        <Reveal inView as="h2" className="mb-4 font-display text-lg font-semibold">
          Active listings
        </Reveal>
        {listings.length ? (
          <ProfileListingGrid listings={listings} />
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

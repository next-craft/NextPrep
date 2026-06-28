import { cache } from 'react'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { BookOpen, GraduationCap } from 'lucide-react'
import ProfileHeader from '@/components/shared/profile-header'
import ProfileListingGrid from '@/components/listings/ProfileListingGrid'
import { EmptyState } from '@/components/shared/states'
import { Reveal } from '@/components/shared/motion'
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
      <ProfileHeader user={user} />

      {/* Campus: canonical → links to the college community page; free text → unlinked muted chip. */}
      {user.college ? (
        <div className="mt-4">
          <Link
            href={`/colleges/${user.college.slug}`}
            className="inline-flex items-center gap-1.5 rounded-full border border-light_bronze-700 bg-papaya_whip-800 px-3 py-1 text-sm font-medium text-light_bronze-200 transition-colors hover:border-light_bronze-500"
          >
            <GraduationCap className="h-4 w-4" /> {user.college.name}
          </Link>
        </div>
      ) : user.college_other ? (
        <div className="mt-4">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted px-3 py-1 text-sm text-muted-foreground">
            <GraduationCap className="h-4 w-4" /> {user.college_other}
          </span>
        </div>
      ) : null}

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

import { cache } from 'react'
import { notFound } from 'next/navigation'
import Link from 'next/link'
import { BookOpen, GraduationCap, MapPin } from 'lucide-react'
import ListingGrid from '@/components/listings/ListingGrid'
import { EmptyState } from '@/components/shared/states'
import { Reveal } from '@/components/shared/motion'
import JsonLd from '@/components/shared/json-ld'

export const revalidate = 0

// Deduped across generateMetadata and the page render within one request.
// API: GET /v1/colleges/{slug} → { college: CollegeOut, listings: [ListingOut] }
const getCollege = cache(async function getCollege(slug) {
  const r = await fetch(`${process.env.API_URL}/colleges/${encodeURIComponent(slug)}`, { cache: 'no-store' })
  if (!r.ok) return null
  return r.json()
})

export async function generateMetadata({ params }) {
  const { slug } = await params
  try {
    const data = await getCollege(slug)
    if (data?.college) {
      const { college } = data
      const where = [college.city, college.state].filter(Boolean).join(', ')
      const description = `Study material from students at ${college.name}${
        where ? ` (${where})` : ''
      } on NextPrep — books, notes and coaching modules.`
      return {
        title: college.name,
        description,
        alternates: { canonical: `/colleges/${slug}` },
        openGraph: {
          title: `${college.name} · NextPrep`,
          description,
          url: `https://nextprep.online/colleges/${slug}`,
        },
      }
    }
  } catch {
    /* fall through */
  }
  return { title: 'College' }
}

export default async function CollegePage({ params }) {
  const { slug } = await params

  const data = await getCollege(slug)
  if (!data?.college) notFound()

  const { college, listings = [] } = data
  const where = [college.city, college.state].filter(Boolean).join(', ')

  const collegeJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'CollectionPage',
    name: `${college.name} — study material`,
    url: `https://nextprep.online/colleges/${slug}`,
    ...(where ? { about: { '@type': 'Place', name: where } } : {}),
    isPartOf: { '@id': 'https://nextprep.online/#website' },
  }
  const breadcrumbJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://nextprep.online' },
      { '@type': 'ListItem', position: 2, name: 'Colleges', item: 'https://nextprep.online/colleges' },
      { '@type': 'ListItem', position: 3, name: college.name, item: `https://nextprep.online/colleges/${slug}` },
    ],
  }

  return (
    <div className="container py-8 lg:py-12">
      <JsonLd data={[collegeJsonLd, breadcrumbJsonLd]} />
      <Link
        href="/colleges"
        className="group mb-6 inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <span aria-hidden className="transition-transform duration-200 group-hover:-translate-x-1">←</span>
        All colleges
      </Link>

      <Reveal className="flex items-start gap-4">
        <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
          <GraduationCap className="h-7 w-7" />
        </span>
        <div className="min-w-0">
          <h1 className="font-display text-2xl font-semibold sm:text-3xl">{college.name}</h1>
          {where && (
            <p className="mt-1 inline-flex items-center gap-1.5 text-sm text-muted-foreground">
              <MapPin className="h-4 w-4 shrink-0" /> {where}
            </p>
          )}
        </div>
      </Reveal>

      <section className="mt-10">
        <Reveal inView as="h2" className="mb-4 font-display text-lg font-semibold">
          Active listings
        </Reveal>
        {listings.length ? (
          <ListingGrid listings={listings} />
        ) : (
          <EmptyState
            icon={BookOpen}
            title="No active listings"
            description={`Nothing is listed at ${college.name} right now.`}
            action={
              <Link href="/listings" className="btn-secondary">
                Browse all listings
              </Link>
            }
          />
        )}
      </section>
    </div>
  )
}

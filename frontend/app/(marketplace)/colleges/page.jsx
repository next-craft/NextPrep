import Link from 'next/link'
import { GraduationCap, MapPin, ChevronRight } from 'lucide-react'
import { EmptyState, ErrorState } from '@/components/shared/states'
import { Reveal, Stagger, StaggerItem } from '@/components/shared/motion'
import { SPRING } from '@/lib/motion'
import JsonLd from '@/components/shared/json-ld'

export const revalidate = 0 // always fresh

export const metadata = {
  title: 'College communities',
  description: 'Browse study material by college campus — find books, notes and modules from students at your college.',
  alternates: { canonical: '/colleges' },
  openGraph: {
    title: 'College communities · NextPrep',
    description: 'Browse study material by college campus on NextPrep.',
    url: 'https://nextprep.online/colleges',
  },
}

const collegesJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'BreadcrumbList',
  itemListElement: [
    { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://nextprep.online' },
    { '@type': 'ListItem', position: 2, name: 'Colleges', item: 'https://nextprep.online/colleges' },
  ],
}

export default async function CollegesPage() {
  // API: GET /v1/colleges?has_listings=1 — only campuses with >=1 active listing.
  // Each links to its /colleges/[slug] community page (read-only listing stream).
  let colleges = []
  let failed = false
  try {
    const res = await fetch(`${process.env.API_URL}/colleges?has_listings=1`, { cache: 'no-store' })
    if (res.ok) colleges = await res.json()
    else failed = true
  } catch {
    failed = true
  }

  return (
    <div className="container py-8 lg:py-12">
      <JsonLd data={collegesJsonLd} />
      <Reveal>
        <h1 className="font-display text-2xl font-semibold sm:text-3xl">College communities</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Find study material from students at your campus. Pick a college to see its listings
          and arrange an easier in-person meetup.
        </p>
      </Reveal>

      <div className="mt-8">
        {failed ? (
          <ErrorState
            title="Couldn't load colleges"
            description="We hit a snag reaching the marketplace. Please try again in a moment."
          />
        ) : colleges.length === 0 ? (
          <EmptyState
            icon={GraduationCap}
            title="No college communities yet"
            description="Once students list material under their campus, it'll show up here."
            action={
              <Link href="/listings" className="btn-secondary">
                Browse all listings
              </Link>
            }
          />
        ) : (
          <Stagger
            inView
            gap={0.04}
            className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3"
          >
            {colleges.map((c) => (
              <StaggerItem key={c.id} className="flex" whileHover={{ y: -4 }} transition={SPRING}>
                <Link
                  href={`/colleges/${c.slug}`}
                  className="card group flex w-full items-center gap-3 p-4 transition-shadow duration-300 hover:shadow-warm-lg"
                >
                  <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
                    <GraduationCap className="h-5 w-5" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium text-foreground">{c.name}</span>
                    {(c.city || c.state) && (
                      <span className="mt-0.5 inline-flex items-center gap-1 text-xs text-muted-foreground">
                        <MapPin className="h-3 w-3 shrink-0" />
                        <span className="truncate">{[c.city, c.state].filter(Boolean).join(', ')}</span>
                      </span>
                    )}
                  </span>
                  <ChevronRight className="h-5 w-5 shrink-0 text-muted-foreground transition-transform duration-200 group-hover:translate-x-1" />
                </Link>
              </StaggerItem>
            ))}
          </Stagger>
        )}
      </div>
    </div>
  )
}

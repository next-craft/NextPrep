import Link from 'next/link'
import { createServerSupabaseClient } from '@/lib/supabase/server'
import {
  Search,
  MessageCircle,
  MapPin,
  KeyRound,
  IndianRupee,
  ShieldCheck,
  Users,
  ArrowRight,
} from 'lucide-react'
import ListingGrid from '@/components/listings/ListingGrid'
import { ExamCategoryChip } from '@/components/shared/badges'
import { POPULAR_EXAM_CATEGORIES } from '@/constants/examCategories'

export const revalidate = 0

const STEPS = [
  { icon: Search, title: 'Browse', body: 'Find books, notes & modules for your exam.' },
  { icon: MessageCircle, title: 'Chat', body: 'Message the seller and agree to meet.' },
  { icon: MapPin, title: 'Meet', body: 'Inspect the material in person, no surprises.' },
  { icon: KeyRound, title: 'Passkey', body: 'The seller shares an 8-digit code when you’re happy.' },
  { icon: IndianRupee, title: 'Pay', body: 'Pay securely in-app; the seller is paid instantly.' },
]

const SPINES = [
  { label: 'HC Verma · Physics', cls: 'bg-light_bronze-400 text-light_bronze-100 rotate-[-6deg]' },
  { label: 'NCERT · Class 12', cls: 'bg-tea_green-500 text-tea_green-100 rotate-[3deg]' },
  { label: 'Allen · NEET Bio', cls: 'bg-papaya_whip-400 text-light_bronze-100 rotate-[-2deg]' },
]

export default async function Home() {
  const supabase = await createServerSupabaseClient()
  const {
    data: { user },
  } = await supabase.auth.getUser()

  // API: GET /listings — recent listings strip
  let recent = []
  try {
    const res = await fetch(`${process.env.API_URL}/listings`, { cache: 'no-store' })
    if (res.ok) recent = (await res.json()).slice(0, 8)
  } catch {
    recent = []
  }

  return (
    <div>
      {/* ── Hero ───────────────────────────────────────────────────────── */}
      <section className="relative overflow-hidden">
        <div className="container grid items-center gap-10 py-14 lg:grid-cols-2 lg:py-20">
          <div className="animate-fade-in-up">
            <span className="chip mb-5 cursor-default">
              <Users className="h-4 w-4" /> Student-to-student · India
            </span>
            <h1 className="font-display text-4xl font-semibold leading-[1.1] sm:text-5xl">
              Buy &amp; sell JEE, NEET, UPSC &amp; CA books — from students, for students.
            </h1>
            <p className="mt-5 max-w-xl text-lg leading-relaxed text-muted-foreground">
              India’s peer-to-peer marketplace for exam study material. Meet locally, inspect before
              you pay, and pass it on. No shipping, no middlemen.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              {user ? (
                <>
                  <Link href="/listings" className="btn-primary px-6 text-base">
                    Browse listings <ArrowRight className="h-4 w-4" />
                  </Link>
                  <Link href="/listings/new" className="btn-secondary px-6 text-base">
                    Sell material
                  </Link>
                </>
              ) : (
                <>
                  <Link href="/login" className="btn-primary px-6 text-base">
                    Continue with Google
                  </Link>
                  <Link href="/listings" className="btn-secondary px-6 text-base">
                    Browse listings
                  </Link>
                </>
              )}
            </div>
          </div>

          {/* decorative book stack */}
          <div className="relative hidden h-72 lg:block">
            <div className="absolute left-1/2 top-1/2 h-64 w-64 -translate-x-1/2 -translate-y-1/2 rounded-full bg-tea_green-700/50 blur-2xl" />
            <div className="relative mx-auto flex h-full max-w-sm items-center justify-center gap-4">
              {SPINES.map((s, i) => (
                <div
                  key={i}
                  className={`flex h-52 w-32 flex-col justify-end rounded-lg border border-light_bronze-700 p-4 shadow-warm-lg ${s.cls}`}
                  style={{ marginTop: i === 1 ? '-1.5rem' : '0' }}
                >
                  <span className="font-display text-sm font-semibold leading-tight">{s.label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Trust strip ────────────────────────────────────────────────── */}
      <section className="border-y border-border bg-papaya_whip-800">
        <div className="container grid gap-6 py-6 sm:grid-cols-3">
          {[
            { icon: MapPin, t: 'In-person meetup', d: 'Meet locally — no shipping, no courier.' },
            { icon: KeyRound, t: 'Passkey-protected', d: 'Pay only after you inspect the material.' },
            { icon: ShieldCheck, t: 'Real students', d: 'Google sign-in. No anonymous resellers.' },
          ].map((x) => (
            <div key={x.t} className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
                <x.icon className="h-5 w-5" />
              </div>
              <div>
                <p className="font-medium">{x.t}</p>
                <p className="text-sm text-muted-foreground">{x.d}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── How it works ───────────────────────────────────────────────── */}
      <section className="container py-14">
        <h2 className="text-center font-display text-2xl font-semibold sm:text-3xl">How it works</h2>
        <p className="mx-auto mt-2 max-w-md text-center text-muted-foreground">
          From finding the right book to paying for it — five simple steps.
        </p>
        <ol className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {STEPS.map((s, i) => (
            <li key={s.title} className="card flex flex-col gap-3 p-5">
              <div className="flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
                  <s.icon className="h-5 w-5" />
                </div>
                <span className="font-display text-2xl font-semibold text-light_bronze-600">
                  {i + 1}
                </span>
              </div>
              <p className="font-medium">{s.title}</p>
              <p className="text-sm text-muted-foreground">{s.body}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* ── Recent listings ────────────────────────────────────────────── */}
      {recent.length > 0 && (
        <section className="container pb-14">
          <div className="mb-5 flex items-end justify-between">
            <h2 className="font-display text-2xl font-semibold">Fresh on NextPrep</h2>
            <Link
              href="/listings"
              className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:text-light_bronze-200"
            >
              Browse all <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
          <ListingGrid listings={recent} />
        </section>
      )}

      {/* ── Browse by exam ─────────────────────────────────────────────── */}
      <section className="border-t border-border bg-papaya_whip-800">
        <div className="container py-14">
          <h2 className="font-display text-2xl font-semibold">Browse by exam</h2>
          <div className="mt-5 flex flex-wrap gap-2.5">
            {POPULAR_EXAM_CATEGORIES.map((value) => (
              <ExamCategoryChip key={value} value={value} asLink />
            ))}
          </div>
        </div>
      </section>

      {/* ── Sell CTA ───────────────────────────────────────────────────── */}
      <section className="container py-16">
        <div className="card flex flex-col items-center gap-4 bg-tea_green-800 p-10 text-center">
          <h2 className="font-display text-2xl font-semibold sm:text-3xl">
            Got books gathering dust?
          </h2>
          <p className="max-w-md text-muted-foreground">
            Turn last year’s prep material into cash and help a junior. Listing takes a minute.
          </p>
          <Link href={user ? '/listings/new' : '/login'} className="btn-primary px-6 text-base">
            Start selling
          </Link>
        </div>
      </section>
    </div>
  )
}

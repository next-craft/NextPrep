import Link from 'next/link'
import { BookOpen, ShieldCheck, MapPin } from 'lucide-react'

export default function Footer() {
  return (
    <footer className="relative mt-16 cv-auto">
      {/* whisper-faint hairline only — no panel; the footer floats over the
          aurora like the hero, matching the transparent navbar */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/40 to-transparent"
      />
      <div className="container py-10">
        <div className="flex flex-col gap-8 sm:flex-row sm:justify-between">
          <div className="max-w-xs">
            <Link href="/" className="font-display text-lg font-semibold tracking-tight">
              Next<span className="text-primary">Prep</span>
            </Link>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              India&apos;s peer-to-peer marketplace for exam study material. From students, for
              students.
            </p>
          </div>

          <nav className="grid grid-cols-2 gap-x-12 gap-y-2 text-sm">
            <Link href="/listings" className="link-underline text-muted-foreground hover:text-foreground">
              Browse listings
            </Link>
            <Link href="/listings/new" className="link-underline text-muted-foreground hover:text-foreground">
              Sell material
            </Link>
            <Link href="/listings?listing_type=BOOK" className="link-underline text-muted-foreground hover:text-foreground">
              Books
            </Link>
            <Link href="/listings?listing_type=NOTES" className="link-underline text-muted-foreground hover:text-foreground">
              Notes
            </Link>
            <Link href="/contact" className="link-underline text-muted-foreground hover:text-foreground">
              Contact us
            </Link>
            <Link href="/privacy" className="link-underline text-muted-foreground hover:text-foreground">
              Privacy Policy
            </Link>
            <Link href="/terms" className="link-underline text-muted-foreground hover:text-foreground">
              Terms of Service
            </Link>
          </nav>
        </div>

        <div className="mt-8 flex flex-col gap-3 border-t border-white/30 pt-6 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <p>© {new Date().getFullYear()} NextPrep. Built for Indian students.</p>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <span className="inline-flex items-center gap-1.5">
              <MapPin className="h-3.5 w-3.5" /> In-person meetup only
            </span>
            <span className="inline-flex items-center gap-1.5">
              <ShieldCheck className="h-3.5 w-3.5" /> Passkey-verified exchanges
            </span>
            <span className="inline-flex items-center gap-1.5">
              <BookOpen className="h-3.5 w-3.5" /> No piracy
            </span>
          </div>
        </div>
      </div>
    </footer>
  )
}

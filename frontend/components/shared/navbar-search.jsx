'use client'
import { Suspense, useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Search } from 'lucide-react'

// Shared so the live input and its prerender fallback are pixel-identical (no CLS).
const FORM_CLASSES =
  'ml-3 hidden flex-1 items-center gap-2 rounded-xl border border-light_bronze-600 bg-card/90 px-3.5 py-2 text-sm shadow-warm backdrop-blur-md transition-all hover:border-light_bronze-400 hover:bg-card hover:shadow-warm-lg focus-within:border-light_bronze-400 focus-within:bg-card focus-within:shadow-warm-lg sm:flex sm:max-w-md'
const INPUT_CLASSES = 'w-full bg-transparent text-foreground placeholder:text-muted-foreground focus:outline-none'
const PLACEHOLDER = 'Search books, notes & modules…'

function SearchInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const active = searchParams.get('q') || ''
  const [query, setQuery] = useState(active)

  // Mirror the box to the active search: keeps repeat searches clean (no stale
  // leftover text), and stays correct across back/forward and leaving /listings.
  useEffect(() => {
    setQuery(active)
  }, [active])

  const onSubmit = (e) => {
    e.preventDefault()
    const q = query.trim()
    router.push(q ? `/listings?q=${encodeURIComponent(q)}` : '/listings')
  }

  return (
    <form onSubmit={onSubmit} role="search" className={FORM_CLASSES}>
      <Search className="h-4 w-4 shrink-0 text-primary" />
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={PLACEHOLDER}
        aria-label="Search books, notes and modules"
        className={INPUT_CLASSES}
      />
    </form>
  )
}

/** Static, identical-looking placeholder rendered during prerender (useSearchParams
 *  forces a client boundary). Swapped for the interactive input on hydration. */
function SearchFallback() {
  return (
    <form role="search" className={FORM_CLASSES} aria-hidden>
      <Search className="h-4 w-4 shrink-0 text-primary" />
      <input type="search" placeholder={PLACEHOLDER} tabIndex={-1} readOnly className={INPUT_CLASSES} />
    </form>
  )
}

export default function NavbarSearch() {
  return (
    <Suspense fallback={<SearchFallback />}>
      <SearchInner />
    </Suspense>
  )
}

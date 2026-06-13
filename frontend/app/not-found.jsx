import Link from 'next/link'
import { Compass } from 'lucide-react'

export default function NotFound() {
  return (
    <div className="container flex min-h-[calc(100vh-4rem)] flex-col items-center justify-center py-16 text-center">
      <p className="font-display text-7xl font-semibold text-light_bronze-500">404</p>
      <h1 className="mt-4 font-display text-2xl font-semibold">Page not found</h1>
      <p className="mt-2 max-w-sm text-muted-foreground">
        The page you&apos;re looking for doesn&apos;t exist or may have been removed.
      </p>
      <Link href="/listings" className="btn-primary mt-6">
        <Compass className="h-4 w-4" /> Browse listings
      </Link>
    </div>
  )
}

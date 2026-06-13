'use client'
import Link from 'next/link'
import { TriangleAlert, RotateCw } from 'lucide-react'

export default function Error({ error, reset }) {
  return (
    <div className="container flex min-h-[calc(100vh-4rem)] flex-col items-center justify-center py-16 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-[#f7e6e0] text-[#8f3322]">
        <TriangleAlert className="h-8 w-8" />
      </div>
      <h1 className="mt-5 font-display text-2xl font-semibold">Something went wrong</h1>
      <p className="mt-2 max-w-sm text-muted-foreground">
        An unexpected error occurred. You can try again or head back to the marketplace.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-3">
        <button onClick={() => reset()} className="btn-primary">
          <RotateCw className="h-4 w-4" /> Try again
        </button>
        <Link href="/listings" className="btn-secondary">
          Browse listings
        </Link>
      </div>
    </div>
  )
}

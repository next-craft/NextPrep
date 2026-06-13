'use client'
import { useState } from 'react'
import Link from 'next/link'
import { Copy, Check, KeyRound, TriangleAlert } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * High-emphasis "shown once" passkey moment.
 * Reused by create-listing (heading "Your listing is live!") and
 * regenerate-passkey (heading "New passkey generated").
 */
export default function PasskeyDisplay({
  passkey,
  listingId,
  heading = 'Your listing is live!',
  className,
}) {
  const [copied, setCopied] = useState(false)
  const grouped = `${String(passkey).slice(0, 4)} ${String(passkey).slice(4)}`

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(String(passkey))
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      /* clipboard unavailable — passkey is still visible to copy manually */
    }
  }

  return (
    <div className={cn('card mx-auto w-full max-w-md animate-scale-in p-8 text-center', className)}>
      <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
        <KeyRound className="h-6 w-6" />
      </div>
      <h2 className="font-display text-2xl font-semibold">{heading}</h2>
      <p className="mt-1 text-sm text-muted-foreground">Your passkey is</p>

      <div className="my-5 select-all rounded-lg border border-border bg-cornsilk px-4 py-5 font-mono text-4xl font-semibold tracking-[0.25em] text-foreground">
        {grouped}
      </div>

      <button type="button" onClick={copy} className="btn-secondary w-full">
        {copied ? (
          <>
            <Check className="h-4 w-4" /> Copied
          </>
        ) : (
          <>
            <Copy className="h-4 w-4" /> Copy passkey
          </>
        )}
      </button>

      <div className="mt-5 rounded-lg bg-papaya_whip-700 p-4 text-left text-sm text-light_bronze-200">
        <p className="flex items-center gap-2 font-semibold text-light_bronze-100">
          <TriangleAlert className="h-4 w-4 shrink-0" /> You won&apos;t be able to see this code again.
        </p>
        <p className="mt-1.5 leading-relaxed">
          Copy or memorise it now. Give it to the buyer only when they&apos;re ready to pay at the
          meetup — the order is <strong className="text-light_bronze-100">meet → inspect → share
          passkey → pay</strong>. Don&apos;t share it over chat; buyers enter it in the app.
        </p>
      </div>

      {listingId && (
        <Link href={`/listings/${listingId}`} className="btn-primary mt-5 w-full">
          Go to my listing
        </Link>
      )}
    </div>
  )
}

'use client'
import { useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import Link from 'next/link'
import { Copy, Check, KeyRound, TriangleAlert } from 'lucide-react'
import { cn } from '@/lib/utils'
import { m, useReducedMotion } from '@/components/shared/motion'
import { SPRING, SPRING_SOFT, EASE } from '@/lib/motion'

/**
 * High-emphasis "shown once" passkey moment.
 * Reused by create-listing (heading "Your listing is live!") and
 * regenerate-passkey (heading "New passkey generated"). Celebratory but calm:
 * the card springs in, the monospace digits count in one by one, and the copy
 * button flips to an animated check on success.
 */
export default function PasskeyDisplay({
  passkey,
  listingId,
  heading = 'Your listing is live!',
  className,
}) {
  const reduced = useReducedMotion()
  const [copied, setCopied] = useState(false)
  const code = String(passkey)
  const grouped = `${code.slice(0, 4)} ${code.slice(4)}`
  const chars = grouped.split('')

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      /* clipboard unavailable — passkey is still visible to copy manually */
    }
  }

  return (
    <m.div
      initial={reduced ? { opacity: 0 } : { opacity: 0, scale: 0.94, y: 8 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={SPRING_SOFT}
      className={cn('card mx-auto w-full max-w-md p-8 text-center', className)}
    >
      <m.div
        initial={reduced ? { opacity: 0 } : { opacity: 0, scale: 0.6 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ ...SPRING, delay: 0.15 }}
        className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-secondary text-secondary-foreground"
      >
        <KeyRound className="h-6 w-6" />
      </m.div>
      <h2 className="font-display text-2xl font-semibold">{heading}</h2>
      <p className="mt-1 text-sm text-muted-foreground">Your passkey is</p>

      <div className="my-5 flex select-all justify-center gap-0.5 rounded-lg border border-border bg-cornsilk px-4 py-5 font-mono text-4xl font-semibold tracking-[0.25em] text-foreground">
        {chars.map((ch, i) =>
          ch === ' ' ? (
            <span key={i} className="w-3" />
          ) : (
            <m.span
              key={i}
              initial={reduced ? { opacity: 0 } : { opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, ease: EASE.warm, delay: 0.3 + i * 0.05 }}
            >
              {ch}
            </m.span>
          )
        )}
      </div>

      <button type="button" onClick={copy} className="btn-secondary w-full overflow-hidden">
        <AnimatePresence mode="wait" initial={false}>
          {copied ? (
            <m.span
              key="copied"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.18, ease: EASE.warm }}
              className="inline-flex items-center gap-2"
            >
              <m.span initial={{ scale: 0.5 }} animate={{ scale: 1 }} transition={SPRING}>
                <Check className="h-4 w-4" />
              </m.span>
              Copied
            </m.span>
          ) : (
            <m.span
              key="copy"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.18, ease: EASE.warm }}
              className="inline-flex items-center gap-2"
            >
              <Copy className="h-4 w-4" /> Copy passkey
            </m.span>
          )}
        </AnimatePresence>
      </button>

      <div className="mt-5 rounded-lg bg-papaya_whip-700 p-4 text-left text-sm text-light_bronze-200">
        <p className="flex items-center gap-2 font-semibold text-light_bronze-100">
          <TriangleAlert className="h-4 w-4 shrink-0" /> You won&apos;t be able to see this code again.
        </p>
        <p className="mt-1.5 leading-relaxed">
          Copy or memorise it now. Give it to the buyer only after they&apos;ve inspected the
          material and you&apos;ve handed over the book — the order is{' '}
          <strong className="text-light_bronze-100">meet → inspect → exchange → share code</strong>.
          Don&apos;t share it over chat; the buyer enters it in the app to confirm the exchange.
        </p>
      </div>

      {listingId && (
        <Link href={`/listings/${listingId}`} className="btn-primary mt-5 w-full">
          Go to my listing
        </Link>
      )}
    </m.div>
  )
}

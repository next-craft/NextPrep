import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/** Merge conditional class names, de-duping conflicting Tailwind utilities. */
export function cn(...inputs) {
  return twMerge(clsx(inputs))
}

/** Format whole rupees as INR. Prices are always whole rupees — no paise. */
export function formatPrice(rupees) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(rupees)
}

/** Percentage saved vs original price, or null when there's no discount. */
export function discountPercent(asking, original) {
  if (!original || original <= asking) return null
  return Math.round(((original - asking) / original) * 100)
}

/** Short + full labels for the A/B/C condition grades. */
export const CONDITION_META = {
  A: { short: 'Like New', full: 'A — Like new (no markings, no wear)' },
  B: { short: 'Good', full: 'B — Good (light use, minimal highlighting)' },
  C: { short: 'Acceptable', full: 'C — Acceptable (heavy use, fully readable)' },
}
export function conditionMeta(code) {
  return CONDITION_META[code] ?? { short: code, full: code }
}

/** Display label for a listing type. */
export const LISTING_TYPE_LABEL = {
  BOOK: 'Book',
  NOTES: 'Notes',
  MODULE: 'Module',
  BUNDLE: 'Bundle',
}

/** Derive the lifecycle status of a listing from its flags. */
export function listingStatus(listing) {
  if (listing?.is_sold) return 'sold'
  if (!listing?.is_available) return 'paused'
  return 'active'
}

/** "just now" / "5m ago" / "3h ago" / "2d ago" / dated. */
export function formatRelativeTime(iso) {
  if (!iso) return ''
  const diffMs = Date.now() - new Date(iso).getTime()
  const sec = Math.round(diffMs / 1000)
  if (sec < 45) return 'just now'
  const min = Math.round(sec / 60)
  if (min < 60) return `${min}m ago`
  const hr = Math.round(min / 60)
  if (hr < 24) return `${hr}h ago`
  const day = Math.round(hr / 24)
  if (day < 7) return `${day}d ago`
  return formatDate(iso)
}

/** "12 Jun 2026" */
export function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

/** Initials for an avatar fallback. */
export function initials(name) {
  if (!name) return '?'
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join('')
}

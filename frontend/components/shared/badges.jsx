import Link from 'next/link'
import { BookOpen, PenLine, Layers, Package } from 'lucide-react'
import { cn, conditionMeta, LISTING_TYPE_LABEL } from '@/lib/utils'
import { EXAM_CATEGORIES } from '@/constants/examCategories'

const examLabel = Object.fromEntries(EXAM_CATEGORIES.map((c) => [c.value, c.label]))

// Warm, semantic status tints (static so opacity/hover behave predictably).
const STATUS_TINT = {
  success: 'border-[#bcd0a3] bg-[#e9f0dd] text-[#3f6733]',
  warning: 'border-[#ecd6a0] bg-[#fbf1d6] text-[#8a5e12]',
  danger: 'border-[#e4b3a6] bg-[#f7e6e0] text-[#8f3322]',
  neutral: 'border-border bg-muted text-muted-foreground',
}

const CONDITION_TINT = {
  A: 'border-tea_green-400 bg-tea_green-700 text-tea_green-100',
  B: 'border-beige-400 bg-beige-700 text-beige-100',
  C: 'border-papaya_whip-300 bg-papaya_whip-700 text-light_bronze-200',
}

export function ConditionBadge({ code, showLabel = true, className }) {
  const meta = conditionMeta(code)
  return (
    <span className={cn('badge', CONDITION_TINT[code] ?? '', className)} title={meta.full}>
      <span className="font-semibold">{code}</span>
      {showLabel && <span>· {meta.short}</span>}
    </span>
  )
}

const TYPE_ICON = { BOOK: BookOpen, NOTES: PenLine, MODULE: Layers, BUNDLE: Package }

export function ListingTypeBadge({ type, className }) {
  const Icon = TYPE_ICON[type] ?? BookOpen
  return (
    <span className={cn('badge border-light_bronze-700 bg-papaya_whip-800 text-light_bronze-200', className)}>
      <Icon className="h-3.5 w-3.5" />
      {LISTING_TYPE_LABEL[type] ?? type}
    </span>
  )
}

export function ExamCategoryChip({ value, asLink = false, className }) {
  const label = examLabel[value] ?? value
  if (asLink) {
    return (
      <Link href={`/listings?exam_category=${value}`} className={cn('chip', className)}>
        {label}
      </Link>
    )
  }
  return <span className={cn('badge border-tea_green-500 bg-tea_green-800 text-tea_green-100', className)}>{label}</span>
}

const LISTING_STATUS = {
  active: { label: 'Active', tint: 'success' },
  paused: { label: 'Paused', tint: 'warning' },
  sold: { label: 'Sold', tint: 'danger' },
}

export function ListingStatusBadge({ status, className }) {
  const meta = LISTING_STATUS[status] ?? LISTING_STATUS.active
  return <span className={cn('badge', STATUS_TINT[meta.tint], className)}>{meta.label}</span>
}

const TX_STATUS = {
  initiated: { label: 'Initiated', tint: 'warning' },
  released: { label: 'Released', tint: 'success' },
  cancelled: { label: 'Cancelled', tint: 'neutral' },
}

export function TransactionStatusBadge({ status, className }) {
  const meta = TX_STATUS[status] ?? TX_STATUS.initiated
  return <span className={cn('badge', STATUS_TINT[meta.tint], className)}>{meta.label}</span>
}

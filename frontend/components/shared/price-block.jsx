import { cn, formatPrice, discountPercent } from '@/lib/utils'

const SIZE = {
  sm: 'text-lg',
  md: 'text-2xl',
  lg: 'text-4xl',
}
const STRIKE = {
  sm: 'text-xs',
  md: 'text-sm',
  lg: 'text-base',
}

/** Asking price + struck-through original + computed "X% off" savings mark.
 *  Set `showCompare={false}` to show the asking price only — the struck-through
 *  original and savings mark are omitted. On `size="sm"` (dense cards) the
 *  savings mark is a compact pill; larger sizes use the full badge. */
export default function PriceBlock({ asking, original, size = 'lg', showCompare = true, className }) {
  const off = showCompare ? discountPercent(asking, original) : null
  const hasOriginal = showCompare && original != null && original > asking
  return (
    <div className={cn('flex flex-wrap items-baseline gap-x-2.5 gap-y-1', className)}>
      <span className={cn('font-display font-semibold text-foreground', SIZE[size])}>
        {formatPrice(asking)}
      </span>
      {hasOriginal && (
        <span className={cn('text-muted-foreground line-through', STRIKE[size])}>
          {formatPrice(original)}
        </span>
      )}
      {off != null &&
        (size === 'sm' ? (
          <span className="rounded-md bg-[#e9f0dd] px-1.5 py-0.5 text-[11px] font-semibold leading-none text-[#3f6733]">
            {off}% off
          </span>
        ) : (
          <span className="badge border-[#bcd0a3] bg-[#e9f0dd] text-[#3f6733]">{off}% off</span>
        ))}
    </div>
  )
}

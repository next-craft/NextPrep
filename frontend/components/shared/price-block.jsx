import { cn, formatPrice, discountPercent } from '@/lib/utils'

const SIZE = {
  sm: 'text-lg',
  md: 'text-2xl',
  lg: 'text-4xl',
}

/** Asking price + struck-through original + computed "X% off" tag. */
export default function PriceBlock({ asking, original, size = 'lg', className }) {
  const off = discountPercent(asking, original)
  return (
    <div className={cn('flex flex-wrap items-baseline gap-x-3 gap-y-1', className)}>
      <span className={cn('font-display font-semibold text-foreground', SIZE[size])}>
        {formatPrice(asking)}
      </span>
      {original != null && original > asking && (
        <span className="text-sm text-muted-foreground line-through">{formatPrice(original)}</span>
      )}
      {off != null && (
        <span className="badge border-[#bcd0a3] bg-[#e9f0dd] text-[#3f6733]">{off}% off</span>
      )}
    </div>
  )
}

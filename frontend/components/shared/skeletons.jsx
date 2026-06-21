import { cn } from '@/lib/utils'

export function Skeleton({ className }) {
  return <div className={cn('skeleton', className)} />
}

export function ListingCardSkeleton() {
  return (
    <div className="card overflow-hidden">
      <div className="skeleton aspect-[6/5] rounded-none" />
      <div className="space-y-2.5 p-3">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-6 w-1/3" />
        <div className="flex gap-2">
          <Skeleton className="h-5 w-16" />
          <Skeleton className="h-5 w-20" />
        </div>
      </div>
    </div>
  )
}

export function ListingGridSkeleton({ count = 8, className }) {
  return (
    <div className={cn('grid grid-cols-2 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-3', className)}>
      {Array.from({ length: count }).map((_, i) => (
        <ListingCardSkeleton key={i} />
      ))}
    </div>
  )
}

export function ListingDetailSkeleton() {
  return (
    <div className="grid items-start gap-8 lg:grid-cols-[1.05fr_0.95fr] lg:gap-12">
      <div className="rounded-2xl border border-white/50 bg-papaya_whip-700 p-3 shadow-warm sm:p-4">
        <Skeleton className="aspect-[4/3] w-full" />
      </div>
      <div className="space-y-4 rounded-2xl border border-white/50 bg-card/95 p-6 shadow-warm-lg sm:p-7">
        <div className="flex gap-2">
          <Skeleton className="h-6 w-16" />
          <Skeleton className="h-6 w-20" />
        </div>
        <Skeleton className="h-8 w-3/4" />
        <Skeleton className="h-10 w-1/3" />
        <div className="flex gap-2">
          <Skeleton className="h-5 w-20" />
          <Skeleton className="h-5 w-24" />
          <Skeleton className="h-5 w-20" />
        </div>
        <Skeleton className="h-px w-full" />
        <Skeleton className="h-16 w-full rounded-xl" />
        <Skeleton className="h-12 w-full" />
      </div>
    </div>
  )
}

export function RowSkeleton() {
  return (
    <div className="card flex items-center gap-4 p-4">
      <Skeleton className="h-16 w-16 shrink-0 rounded-md" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-4 w-1/4" />
      </div>
    </div>
  )
}

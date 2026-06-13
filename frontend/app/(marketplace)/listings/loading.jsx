import { Skeleton, ListingGridSkeleton } from '@/components/shared/skeletons'

export default function Loading() {
  return (
    <div className="container py-6 lg:py-8">
      <Skeleton className="h-9 w-64" />
      <div className="mt-6 flex gap-8">
        <aside className="hidden w-64 shrink-0 lg:block">
          <Skeleton className="h-96 w-full" />
        </aside>
        <div className="min-w-0 flex-1">
          <ListingGridSkeleton />
        </div>
      </div>
    </div>
  )
}

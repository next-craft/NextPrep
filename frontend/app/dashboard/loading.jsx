import { Skeleton, RowSkeleton } from '@/components/shared/skeletons'

export default function Loading() {
  return (
    <div className="container py-8">
      <Skeleton className="h-9 w-48" />
      <Skeleton className="mt-6 h-11 w-72" />
      <div className="mt-6 space-y-3">
        {[0, 1, 2, 3].map((i) => (
          <RowSkeleton key={i} />
        ))}
      </div>
    </div>
  )
}

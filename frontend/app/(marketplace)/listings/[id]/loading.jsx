import { ListingDetailSkeleton } from '@/components/shared/skeletons'

export default function Loading() {
  return (
    <div className="container py-6 lg:py-8">
      <ListingDetailSkeleton />
    </div>
  )
}

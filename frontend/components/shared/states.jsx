import { TriangleAlert } from 'lucide-react'
import { cn } from '@/lib/utils'

/** Friendly, warm empty state. Pass a lucide icon, copy, and optional action node. */
export function EmptyState({ icon: Icon, title, description, action, className }) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center rounded-lg border border-dashed border-light_bronze-700 bg-card/60 px-6 py-16 text-center',
        className
      )}
    >
      {Icon && (
        <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
          <Icon className="h-7 w-7" />
        </div>
      )}
      <h3 className="font-display text-lg font-semibold">{title}</h3>
      {description && <p className="mt-1.5 max-w-sm text-sm text-muted-foreground">{description}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  )
}

export function ErrorState({ title = 'Something went wrong', description, action, className }) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center rounded-lg border border-[#e4b3a6] bg-[#f7e6e0] px-6 py-12 text-center',
        className
      )}
    >
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-[#f2d6cd] text-[#8f3322]">
        <TriangleAlert className="h-6 w-6" />
      </div>
      <h3 className="font-display text-lg font-semibold text-[#7a2c1d]">{title}</h3>
      {description && <p className="mt-1.5 max-w-sm text-sm text-[#8f3322]">{description}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  )
}

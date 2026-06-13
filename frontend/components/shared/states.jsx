import { TriangleAlert } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Stagger, StaggerItem } from '@/components/shared/motion'

/** Friendly, warm empty state. Pass a lucide icon, copy, and optional action node. */
export function EmptyState({ icon: Icon, title, description, action, className }) {
  return (
    <Stagger
      gap={0.07}
      className={cn(
        'flex flex-col items-center justify-center rounded-lg border border-dashed border-light_bronze-700 bg-card/60 px-6 py-16 text-center',
        className
      )}
    >
      {Icon && (
        <StaggerItem className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
          <Icon className="h-7 w-7" />
        </StaggerItem>
      )}
      <StaggerItem as="h3" className="font-display text-lg font-semibold">
        {title}
      </StaggerItem>
      {description && (
        <StaggerItem as="p" className="mt-1.5 max-w-sm text-sm text-muted-foreground">
          {description}
        </StaggerItem>
      )}
      {action && <StaggerItem className="mt-6">{action}</StaggerItem>}
    </Stagger>
  )
}

export function ErrorState({ title = 'Something went wrong', description, action, className }) {
  return (
    <Stagger
      gap={0.07}
      className={cn(
        'flex flex-col items-center justify-center rounded-lg border border-[#e4b3a6] bg-[#f7e6e0] px-6 py-12 text-center',
        className
      )}
    >
      <StaggerItem className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-[#f2d6cd] text-[#8f3322]">
        <TriangleAlert className="h-6 w-6" />
      </StaggerItem>
      <StaggerItem as="h3" className="font-display text-lg font-semibold text-[#7a2c1d]">
        {title}
      </StaggerItem>
      {description && (
        <StaggerItem as="p" className="mt-1.5 max-w-sm text-sm text-[#8f3322]">
          {description}
        </StaggerItem>
      )}
      {action && <StaggerItem className="mt-6">{action}</StaggerItem>}
    </Stagger>
  )
}

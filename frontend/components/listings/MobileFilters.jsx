'use client'
import { useState } from 'react'
import { SlidersHorizontal } from 'lucide-react'
import {
  Sheet,
  SheetTrigger,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import ListingFilters from './ListingFilters'
import { FILTER_KEYS } from '@/constants/filters'

export default function MobileFilters({ current = {} }) {
  const [open, setOpen] = useState(false)
  const activeCount = FILTER_KEYS.filter((k) => current[k]).length

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger className="btn-secondary h-10 px-4">
        <SlidersHorizontal className="h-4 w-4" /> Filters
        {activeCount > 0 && (
          <span className="ml-1 rounded-full bg-primary px-1.5 text-xs font-semibold text-primary-foreground">
            {activeCount}
          </span>
        )}
      </SheetTrigger>
      <SheetContent side="left">
        <SheetHeader>
          <SheetTitle>Filters</SheetTitle>
        </SheetHeader>
        <ListingFilters current={current} showHeader={false} onNavigate={() => setOpen(false)} />
      </SheetContent>
    </Sheet>
  )
}

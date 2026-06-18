'use client'
import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { AnimatePresence } from 'framer-motion'
import { m, useReducedMotion } from '@/components/shared/motion'
import { EASE } from '@/lib/motion'
import { cn } from '@/lib/utils'

/**
 * Collapsible section with a header that toggles its body open/closed.
 * Used to split the dashboard Messages / Transactions tabs into Buying vs Selling.
 */
export default function Disclosure({ title, count, defaultOpen = true, children, className }) {
  const reduced = useReducedMotion()
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div className={cn('space-y-3', className)}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center justify-between rounded-lg border border-border bg-papaya_whip-800 px-4 py-2.5 text-left transition-colors hover:bg-papaya_whip-700"
      >
        <span className="font-medium">
          {title}
          {typeof count === 'number' && (
            <span className="ml-2 text-sm text-muted-foreground">({count})</span>
          )}
        </span>
        <ChevronDown className={cn('h-4 w-4 shrink-0 transition-transform duration-200', open && 'rotate-180')} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <m.div
            initial={reduced ? { opacity: 0 } : { height: 0, opacity: 0 }}
            animate={reduced ? { opacity: 1 } : { height: 'auto', opacity: 1 }}
            exit={reduced ? { opacity: 0 } : { height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: EASE.warm }}
            className="overflow-hidden"
          >
            <div className="pt-1">{children}</div>
          </m.div>
        )}
      </AnimatePresence>
    </div>
  )
}

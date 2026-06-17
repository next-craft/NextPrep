'use client'
import { useState } from 'react'
import Image from 'next/image'
import { AnimatePresence } from 'framer-motion'
import { BookOpen } from 'lucide-react'
import { cn } from '@/lib/utils'
import { m } from '@/components/shared/motion'
import { DURATION, EASE } from '@/lib/motion'

/** Image gallery for the listing detail page (≤5 images). Main image
 *  crossfades between selections; the active thumbnail carries a shared
 *  animated ring that slides between thumbs. */
export default function ListingGallery({ images = [], title }) {
  const [active, setActive] = useState(0)

  if (!images.length) {
    return (
      <div className="flex aspect-[4/3] w-full items-center justify-center rounded-lg border border-border bg-papaya_whip-700 text-light_bronze-500">
        <BookOpen className="h-16 w-16" />
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="relative aspect-[4/3] overflow-hidden rounded-lg border border-border bg-papaya_whip-700">
        <AnimatePresence initial={false} mode="popLayout">
          <m.div
            key={active}
            initial={{ opacity: 0, scale: 1.03 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: DURATION.base, ease: EASE.warm }}
            className="absolute inset-0 bg-papaya_whip-700"
          >
            <Image
              src={images[active]}
              alt={title}
              fill
              // Main image is the LCP element on the listing page — load eagerly.
              priority={active === 0}
              sizes="(max-width: 1024px) 100vw, 50vw"
              className="object-contain"
            />
          </m.div>
        </AnimatePresence>
      </div>
      {images.length > 1 && (
        <div className="flex gap-2 overflow-x-auto pb-1">
          {images.map((url, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setActive(i)}
              className={cn(
                'relative h-16 w-16 shrink-0 overflow-hidden rounded-md transition-opacity',
                i === active ? 'opacity-100' : 'opacity-60 hover:opacity-100'
              )}
              aria-label={`View image ${i + 1}`}
            >
              <Image
                src={url}
                alt={`${title} — image ${i + 1}`}
                fill
                sizes="64px"
                className="object-cover"
              />
              {i === active && (
                <m.span
                  layoutId="gallery-thumb-ring"
                  className="pointer-events-none absolute inset-0 rounded-md ring-2 ring-primary ring-offset-1 ring-offset-card"
                  transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

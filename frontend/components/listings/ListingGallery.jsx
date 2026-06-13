'use client'
import { useState } from 'react'
import { BookOpen } from 'lucide-react'
import { cn } from '@/lib/utils'

/** Image gallery for the listing detail page (≤5 images). */
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
      <div className="overflow-hidden rounded-lg border border-border bg-papaya_whip-700">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={images[active]}
          alt={title}
          className="aspect-[4/3] w-full bg-papaya_whip-700 object-contain"
        />
      </div>
      {images.length > 1 && (
        <div className="flex gap-2 overflow-x-auto pb-1">
          {images.map((url, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setActive(i)}
              className={cn(
                'h-16 w-16 shrink-0 overflow-hidden rounded-md border-2 transition-all',
                i === active
                  ? 'border-primary'
                  : 'border-border opacity-60 hover:opacity-100'
              )}
              aria-label={`View image ${i + 1}`}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={url} alt="" className="h-full w-full object-cover" />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

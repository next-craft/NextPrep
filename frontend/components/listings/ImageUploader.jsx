'use client'
import { useEffect, useRef, useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import { ImagePlus, X, ChevronLeft, ChevronRight, Link2 } from 'lucide-react'
import { m } from '@/components/shared/motion'
import { SPRING } from '@/lib/motion'

// Direct browser→Cloudinary upload (never through FastAPI). Env-gated: when the
// cloud name + unsigned preset aren't set, fall back to pasting image URLs so the
// form still works end-to-end in development.
const CLOUD = process.env.NEXT_PUBLIC_CLOUDINARY_CLOUD_NAME
const PRESET = process.env.NEXT_PUBLIC_CLOUDINARY_UPLOAD_PRESET
const CLOUDINARY_ENABLED = Boolean(CLOUD && PRESET)
const WIDGET_SRC = 'https://upload-widget.cloudinary.com/global/all.js'

export default function ImageUploader({ value = [], onChange, max = 5 }) {
  const [scriptReady, setScriptReady] = useState(false)
  const [urlInput, setUrlInput] = useState('')
  const valueRef = useRef(value)
  valueRef.current = value
  const widgetRef = useRef(null)

  useEffect(() => {
    if (!CLOUDINARY_ENABLED) return
    if (window.cloudinary) {
      setScriptReady(true)
      return
    }
    const existing = document.querySelector(`script[src="${WIDGET_SRC}"]`)
    if (existing) {
      existing.addEventListener('load', () => setScriptReady(true))
      return
    }
    const s = document.createElement('script')
    s.src = WIDGET_SRC
    s.async = true
    s.onload = () => setScriptReady(true)
    document.body.appendChild(s)
  }, [])

  const remaining = max - value.length

  const openWidget = () => {
    if (!window.cloudinary) return
    if (!widgetRef.current) {
      widgetRef.current = window.cloudinary.createUploadWidget(
        {
          cloudName: CLOUD,
          uploadPreset: PRESET,
          sources: ['local', 'camera', 'url'],
          multiple: true,
          maxFiles: max,
          clientAllowedFormats: ['image'],
          maxImageFileSize: 5_000_000,
        },
        (error, result) => {
          if (!error && result?.event === 'success') {
            const url = result.info.secure_url
            const cur = valueRef.current
            if (cur.length < max && !cur.includes(url)) onChange([...cur, url])
          }
        }
      )
    }
    widgetRef.current.open()
  }

  const addUrl = () => {
    const u = urlInput.trim()
    if (!u || !/^https?:\/\//i.test(u)) return
    if (value.length >= max || value.includes(u)) return
    onChange([...value, u])
    setUrlInput('')
  }

  const removeAt = (i) => onChange(value.filter((_, idx) => idx !== i))
  const move = (i, dir) => {
    const j = i + dir
    if (j < 0 || j >= value.length) return
    const next = value.slice()
    ;[next[i], next[j]] = [next[j], next[i]]
    onChange(next)
  }

  return (
    <div className="space-y-3">
      {value.length > 0 && (
        <div className="grid grid-cols-3 gap-3 sm:grid-cols-5">
          <AnimatePresence initial={false} mode="popLayout">
            {value.map((url, i) => (
              <m.div
                key={url}
                layout
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
                transition={SPRING}
                className="group relative aspect-square overflow-hidden rounded-md border border-border bg-papaya_whip-700"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={url} alt="" className="h-full w-full object-cover" />
                <AnimatePresence>
                  {i === 0 && (
                    <m.span
                      initial={{ opacity: 0, scale: 0.7 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.7 }}
                      transition={SPRING}
                      className="badge absolute left-1 top-1 bg-card/90 px-1.5 text-[10px]"
                    >
                      Cover
                    </m.span>
                  )}
                </AnimatePresence>
                <button
                  type="button"
                  onClick={() => removeAt(i)}
                  className="absolute right-1 top-1 rounded-full bg-light_bronze-100/70 p-1 text-cornsilk opacity-0 transition-opacity group-hover:opacity-100"
                  aria-label="Remove image"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
                <div className="absolute inset-x-1 bottom-1 flex justify-between opacity-0 transition-opacity group-hover:opacity-100">
                  <button
                    type="button"
                    onClick={() => move(i, -1)}
                    disabled={i === 0}
                    className="rounded bg-light_bronze-100/70 p-0.5 text-cornsilk disabled:opacity-30"
                    aria-label="Move left"
                  >
                    <ChevronLeft className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => move(i, 1)}
                    disabled={i === value.length - 1}
                    className="rounded bg-light_bronze-100/70 p-0.5 text-cornsilk disabled:opacity-30"
                    aria-label="Move right"
                  >
                    <ChevronRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </m.div>
            ))}
          </AnimatePresence>
        </div>
      )}

      {remaining > 0 &&
        (CLOUDINARY_ENABLED ? (
          <button
            type="button"
            onClick={openWidget}
            disabled={!scriptReady}
            className="btn-secondary w-full"
          >
            <ImagePlus className="h-4 w-4" />
            {scriptReady ? `Add images (${remaining} left)` : 'Loading uploader…'}
          </button>
        ) : (
          <div className="space-y-1.5">
            <div className="flex gap-2">
              <input
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    addUrl()
                  }
                }}
                placeholder="Paste image URL (https://…)"
                className="input"
              />
              <button type="button" onClick={addUrl} className="btn-secondary shrink-0">
                <Link2 className="h-4 w-4" /> Add
              </button>
            </div>
            {/* TODO(backend): set NEXT_PUBLIC_CLOUDINARY_CLOUD_NAME + NEXT_PUBLIC_CLOUDINARY_UPLOAD_PRESET to enable direct upload. */}
            <p className="text-xs text-muted-foreground">
              Cloudinary isn&apos;t configured yet — paste image URLs for now.
            </p>
          </div>
        ))}

      <p className="text-xs text-muted-foreground">
        {value.length}/{max} images. The first image is the cover.
      </p>
    </div>
  )
}

'use client'
import { useEffect, useRef, useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import {
  UploadCloud,
  ImagePlus,
  X,
  ChevronLeft,
  ChevronRight,
  Link2,
  Loader2,
  AlertCircle,
  Camera,
  Plus,
} from 'lucide-react'
import { m } from '@/components/shared/motion'
import { EASE, SPRING } from '@/lib/motion'
import { cn } from '@/lib/utils'

// Direct browser→Cloudinary unsigned upload (never through FastAPI). Env-gated:
// when the cloud name + unsigned preset aren't set, fall back to pasting image
// URLs so the form still works end-to-end in development.
const CLOUD = process.env.NEXT_PUBLIC_CLOUDINARY_CLOUD_NAME
const PRESET = process.env.NEXT_PUBLIC_CLOUDINARY_UPLOAD_PRESET
const CLOUDINARY_ENABLED = Boolean(CLOUD && PRESET)
const UPLOAD_URL = `https://api.cloudinary.com/v1_1/${CLOUD}/upload`
const MAX_BYTES = 5_000_000

const TABS = [
  { key: 'device', label: 'Device', icon: UploadCloud },
  { key: 'camera', label: 'Camera', icon: Camera },
  { key: 'link', label: 'Web link', icon: Link2 },
]

export default function ImageUploader({ value = [], onChange, max = 5 }) {
  const [tab, setTab] = useState('device')
  const [urlInput, setUrlInput] = useState('')
  const [uploads, setUploads] = useState([]) // { id, preview, progress, error }
  const [dragOver, setDragOver] = useState(false)
  const [notice, setNotice] = useState(null)
  const [camReady, setCamReady] = useState(false)
  const [camError, setCamError] = useState(null)
  const valueRef = useRef(value)
  valueRef.current = value
  const inputRef = useRef(null)
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const streamRef = useRef(null)
  const idRef = useRef(0)

  // How many more can be queued (committed + in-flight).
  const remaining = max - value.length - uploads.length

  // ── Live camera (getUserMedia) ──────────────────────────────────────────
  const cameraActive = CLOUDINARY_ENABLED && tab === 'camera' && remaining > 0

  useEffect(() => {
    if (!cameraActive) return undefined
    let cancelled = false
    setCamError(null)
    setCamReady(false)

    if (!navigator.mediaDevices?.getUserMedia) {
      setCamError('This browser can’t access the camera. Use Device upload instead.')
      return undefined
    }

    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: 'environment' }, audio: false })
      .then((stream) => {
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop())
          return
        }
        streamRef.current = stream
        if (videoRef.current) videoRef.current.srcObject = stream
        setCamReady(true)
      })
      .catch(() => {
        if (!cancelled) setCamError('Couldn’t access the camera — check permissions, or use Device upload.')
      })

    return () => {
      cancelled = true
      streamRef.current?.getTracks().forEach((t) => t.stop())
      streamRef.current = null
      setCamReady(false)
    }
  }, [cameraActive])

  function capturePhoto() {
    const v = videoRef.current
    const c = canvasRef.current
    if (!v || !c || !v.videoWidth) return
    c.width = v.videoWidth
    c.height = v.videoHeight
    c.getContext('2d').drawImage(v, 0, 0)
    c.toBlob(
      (blob) => {
        if (blob && valueRef.current.length + uploads.length < max) {
          uploadOne(new File([blob], `camera-${idRef.current + 1}.jpg`, { type: 'image/jpeg' }))
        }
      },
      'image/jpeg',
      0.9
    )
  }

  const setUpload = (id, patch) =>
    setUploads((list) => list.map((u) => (u.id === id ? { ...u, ...patch } : u)))
  const dropUpload = (id) => setUploads((list) => list.filter((u) => u.id !== id))

  function uploadOne(file) {
    const id = ++idRef.current
    const preview = URL.createObjectURL(file)
    setUploads((list) => [...list, { id, preview, progress: 0, error: false }])

    const form = new FormData()
    form.append('file', file)
    form.append('upload_preset', PRESET)

    const xhr = new XMLHttpRequest()
    xhr.open('POST', UPLOAD_URL)
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) setUpload(id, { progress: e.loaded / e.total })
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const { secure_url } = JSON.parse(xhr.responseText)
          const cur = valueRef.current
          if (secure_url && cur.length < max && !cur.includes(secure_url)) {
            onChange([...cur, secure_url])
          }
          URL.revokeObjectURL(preview)
          dropUpload(id)
          return
        } catch {
          /* fall through to error */
        }
      }
      setUpload(id, { error: true })
    }
    xhr.onerror = () => setUpload(id, { error: true })
    xhr.send(form)
  }

  function handleFiles(fileList) {
    setNotice(null)
    const files = Array.from(fileList || [])
    let slots = max - valueRef.current.length - uploads.length
    let rejected = false
    for (const file of files) {
      if (slots <= 0) {
        setNotice(`You can add up to ${max} images.`)
        break
      }
      if (!file.type.startsWith('image/')) {
        rejected = true
        continue
      }
      if (file.size > MAX_BYTES) {
        rejected = true
        continue
      }
      uploadOne(file)
      slots--
    }
    if (rejected) setNotice('Some files were skipped — images only, up to 5 MB each.')
  }

  const onDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    if (remaining > 0) handleFiles(e.dataTransfer.files)
  }

  const retry = (u) => {
    // Re-pick is simplest: drop the failed tile; user re-adds. Free the preview.
    URL.revokeObjectURL(u.preview)
    dropUpload(u.id)
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

  const hasTiles = value.length > 0 || uploads.length > 0

  return (
    <div className="space-y-3">
      {hasTiles && (
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
                <img src={url} alt="" referrerPolicy="no-referrer" className="h-full w-full object-cover" />
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

            {/* In-flight uploads — local preview + bronze progress bar */}
            {uploads.map((u) => (
              <m.div
                key={`up-${u.id}`}
                layout
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
                transition={SPRING}
                className="relative aspect-square overflow-hidden rounded-md border border-border bg-papaya_whip-700"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={u.preview} alt="" className="h-full w-full object-cover opacity-50" />
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-1 bg-light_bronze-100/25 text-cornsilk">
                  {u.error ? (
                    <>
                      <AlertCircle className="h-5 w-5" />
                      <button
                        type="button"
                        onClick={() => retry(u)}
                        className="rounded bg-cornsilk/90 px-2 py-0.5 text-[10px] font-semibold text-destructive"
                      >
                        Dismiss
                      </button>
                    </>
                  ) : (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  )}
                </div>
                {!u.error && (
                  <div className="absolute inset-x-0 bottom-0 h-1 bg-light_bronze-100/30">
                    <m.div
                      className="h-full bg-primary"
                      initial={{ width: 0 }}
                      animate={{ width: `${Math.round(u.progress * 100)}%` }}
                      transition={{ ease: 'easeOut', duration: 0.2 }}
                    />
                  </div>
                )}
              </m.div>
            ))}
          </AnimatePresence>
        </div>
      )}

      {remaining > 0 &&
        (CLOUDINARY_ENABLED ? (
          <div className="overflow-hidden rounded-lg border border-border bg-card shadow-warm">
            {/* Tabs — Device / Camera / Web link */}
            <div className="flex border-b border-border">
              {TABS.map((t) => {
                const active = tab === t.key
                return (
                  <button
                    key={t.key}
                    type="button"
                    onClick={() => setTab(t.key)}
                    className={cn(
                      'relative flex flex-1 items-center justify-center gap-1.5 px-3 py-2.5 text-sm font-medium transition-colors',
                      active ? 'text-primary' : 'text-muted-foreground hover:text-foreground'
                    )}
                  >
                    <t.icon className="h-4 w-4" /> {t.label}
                    {active && (
                      <m.span
                        layoutId="uploader-tab"
                        className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-primary"
                        transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                      />
                    )}
                  </button>
                )
              })}
            </div>

            <div className="p-3">
              <AnimatePresence mode="wait" initial={false}>
                <m.div
                  key={tab}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={{ duration: 0.18, ease: EASE.warm }}
                >
                  {tab === 'device' && (
                    <div
                      onDragOver={(e) => {
                        e.preventDefault()
                        setDragOver(true)
                      }}
                      onDragLeave={() => setDragOver(false)}
                      onDrop={onDrop}
                      onClick={() => inputRef.current?.click()}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          inputRef.current?.click()
                        }
                      }}
                      className={cn(
                        'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-10 text-center transition-colors',
                        dragOver
                          ? 'border-primary bg-accent/70'
                          : 'border-light_bronze-700 bg-card/50 hover:border-light_bronze-500 hover:bg-card'
                      )}
                    >
                      <m.div
                        animate={dragOver ? { y: -3, scale: 1.05 } : { y: 0, scale: 1 }}
                        transition={SPRING}
                        className="flex h-12 w-12 items-center justify-center rounded-full bg-secondary text-primary"
                      >
                        <UploadCloud className="h-6 w-6" />
                      </m.div>
                      <p className="text-sm font-medium text-foreground">
                        {dragOver ? 'Drop to upload' : 'Drag & drop images here'}
                      </p>
                      <p className="text-xs text-muted-foreground">or</p>
                      <span className="btn-primary pointer-events-none h-9 px-4 text-sm">
                        <ImagePlus className="h-4 w-4" /> Browse files
                      </span>
                      <p className="text-xs text-muted-foreground">
                        JPG or PNG · up to 5 MB · {remaining} {remaining === 1 ? 'slot' : 'slots'} left
                      </p>
                      <input
                        ref={inputRef}
                        type="file"
                        accept="image/*"
                        multiple
                        className="hidden"
                        onChange={(e) => {
                          handleFiles(e.target.files)
                          e.target.value = '' // allow re-selecting the same file
                        }}
                      />
                    </div>
                  )}

                  {tab === 'camera' && (
                    <div className="space-y-2">
                      {camError ? (
                        <div className="flex items-start gap-2 rounded-lg border border-[#e4b3a6] bg-[#f7e6e0] px-4 py-3 text-sm font-medium text-[#8f3322]">
                          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                          {camError}
                        </div>
                      ) : (
                        <>
                          <div className="relative aspect-video overflow-hidden rounded-lg border border-border bg-light_bronze-100">
                            <video
                              ref={videoRef}
                              autoPlay
                              playsInline
                              muted
                              className="h-full w-full object-cover"
                            />
                            {!camReady && (
                              <div className="absolute inset-0 flex items-center justify-center text-cornsilk">
                                <Loader2 className="h-6 w-6 animate-spin" />
                              </div>
                            )}
                          </div>
                          <button
                            type="button"
                            onClick={capturePhoto}
                            disabled={!camReady}
                            className="btn-primary w-full"
                          >
                            <Camera className="h-4 w-4" /> Capture photo
                          </button>
                          <p className="text-center text-xs text-muted-foreground">
                            {remaining} {remaining === 1 ? 'slot' : 'slots'} left · captures upload automatically
                          </p>
                        </>
                      )}
                      <canvas ref={canvasRef} className="hidden" />
                    </div>
                  )}

                  {tab === 'link' && (
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
                        <button type="button" onClick={addUrl} className="btn-primary shrink-0">
                          <Plus className="h-4 w-4" /> Add
                        </button>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Paste a direct link to an image (JPG or PNG).
                      </p>
                    </div>
                  )}
                </m.div>
              </AnimatePresence>
            </div>

            {notice && (
              <p className="border-t border-border px-3 py-2 text-xs font-medium text-destructive">
                {notice}
              </p>
            )}
          </div>
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

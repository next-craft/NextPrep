'use client'
import { useEffect, useRef, useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import {
  UploadCloud,
  ImagePlus,
  Link2,
  Loader2,
  AlertCircle,
  Camera,
  Plus,
  RotateCcw,
} from 'lucide-react'
import { m } from '@/components/shared/motion'
import { EASE, SPRING } from '@/lib/motion'
import { cn } from '@/lib/utils'

// Single-image sibling of ImageUploader (listings). Direct browser→Cloudinary
// unsigned upload — never through FastAPI. Env-gated: without the cloud name +
// unsigned preset, fall back to pasting a URL so the form still works in dev.
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

/**
 * Avatar picker with the same Device / Camera / Web-link options as the listing
 * image uploader, scoped to a single photo. `value` is the committed image URL,
 * `onChange(url)` replaces it ('' resets to the account default — the Google photo).
 */
export default function AvatarUploader({ value, onChange }) {
  const [tab, setTab] = useState('device')
  const [urlInput, setUrlInput] = useState('')
  const [upload, setUpload] = useState(null) // { preview, progress, error }
  const [dragOver, setDragOver] = useState(false)
  const [notice, setNotice] = useState(null)
  const [camReady, setCamReady] = useState(false)
  const [camError, setCamError] = useState(null)
  const inputRef = useRef(null)
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const streamRef = useRef(null)

  // ── Live camera (getUserMedia) — front-facing for a selfie ───────────────
  const cameraActive = CLOUDINARY_ENABLED && tab === 'camera'

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
      .getUserMedia({ video: { facingMode: 'user' }, audio: false })
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
    c.toBlob((blob) => blob && uploadOne(new File([blob], 'avatar.jpg', { type: 'image/jpeg' })), 'image/jpeg', 0.9)
  }

  function uploadOne(file) {
    const preview = URL.createObjectURL(file)
    setNotice(null)
    setUpload({ preview, progress: 0, error: false })

    const form = new FormData()
    form.append('file', file)
    form.append('upload_preset', PRESET)

    const xhr = new XMLHttpRequest()
    xhr.open('POST', UPLOAD_URL)
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) setUpload((u) => u && { ...u, progress: e.loaded / e.total })
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const { secure_url } = JSON.parse(xhr.responseText)
          if (secure_url) {
            onChange(secure_url)
            URL.revokeObjectURL(preview)
            setUpload(null)
            return
          }
        } catch {
          /* fall through to error */
        }
      }
      setUpload((u) => u && { ...u, error: true })
    }
    xhr.onerror = () => setUpload((u) => u && { ...u, error: true })
    xhr.send(form)
  }

  function handleFile(fileList) {
    setNotice(null)
    const file = Array.from(fileList || [])[0]
    if (!file) return
    if (!file.type.startsWith('image/')) {
      setNotice('Please choose an image file (JPG or PNG).')
      return
    }
    if (file.size > MAX_BYTES) {
      setNotice('Image must be under 5 MB.')
      return
    }
    uploadOne(file)
  }

  const onDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    handleFile(e.dataTransfer.files)
  }

  const dismissUpload = () => {
    if (upload) URL.revokeObjectURL(upload.preview)
    setUpload(null)
  }

  const addUrl = () => {
    const u = urlInput.trim()
    if (!u || !/^https?:\/\//i.test(u)) return
    onChange(u)
    setUrlInput('')
  }

  // ── In-flight status strip (spinner / progress / error) ──────────────────
  const statusStrip = (
    <AnimatePresence>
      {upload && (
        <m.div
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.18, ease: EASE.warm }}
          className="flex items-center gap-3 rounded-lg border border-border bg-card/70 p-2.5"
        >
          <span className="relative h-12 w-12 shrink-0 overflow-hidden rounded-full border border-border bg-papaya_whip-700">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={upload.preview} alt="" className="h-full w-full object-cover opacity-60" />
            <span className="absolute inset-0 flex items-center justify-center text-light_bronze-200">
              {upload.error ? <AlertCircle className="h-5 w-5 text-destructive" /> : <Loader2 className="h-5 w-5 animate-spin" />}
            </span>
          </span>
          <div className="min-w-0 flex-1">
            {upload.error ? (
              <p className="text-sm font-medium text-destructive">Upload failed.</p>
            ) : (
              <>
                <p className="text-sm font-medium text-foreground">Uploading photo…</p>
                <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-light_bronze-800">
                  <m.div
                    className="h-full bg-primary"
                    initial={{ width: 0 }}
                    animate={{ width: `${Math.round(upload.progress * 100)}%` }}
                    transition={{ ease: 'easeOut', duration: 0.2 }}
                  />
                </div>
              </>
            )}
          </div>
          <button
            type="button"
            onClick={dismissUpload}
            className="shrink-0 rounded-md px-2 py-1 text-xs font-semibold text-muted-foreground hover:text-foreground"
          >
            {upload.error ? 'Dismiss' : 'Cancel'}
          </button>
        </m.div>
      )}
    </AnimatePresence>
  )

  // ── URL-only fallback (Cloudinary not configured) ────────────────────────
  if (!CLOUDINARY_ENABLED) {
    return (
      <div className="space-y-1.5">
        <div className="flex gap-2">
          <input
            value={value || ''}
            onChange={(e) => onChange(e.target.value)}
            placeholder="Paste image URL (https://…)"
            className="input"
          />
          {value && (
            <button type="button" onClick={() => onChange('')} className="btn-ghost shrink-0" title="Reset to Google photo">
              <RotateCcw className="h-4 w-4" />
            </button>
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          Defaults to your Google photo. Paste a URL to override.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {statusStrip}

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
                    layoutId="avatar-uploader-tab"
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
                    'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-8 text-center transition-colors',
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
                    {dragOver ? 'Drop to upload' : 'Drag & drop a photo here'}
                  </p>
                  <p className="text-xs text-muted-foreground">or</p>
                  <span className="btn-primary pointer-events-none h-9 px-4 text-sm">
                    <ImagePlus className="h-4 w-4" /> Browse files
                  </span>
                  <p className="text-xs text-muted-foreground">JPG or PNG · up to 5 MB</p>
                  <input
                    ref={inputRef}
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(e) => {
                      handleFile(e.target.files)
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
                      <div className="relative mx-auto aspect-square w-44 overflow-hidden rounded-full border border-border bg-light_bronze-100">
                        <video
                          ref={videoRef}
                          autoPlay
                          playsInline
                          muted
                          className="h-full w-full -scale-x-100 object-cover"
                        />
                        {!camReady && (
                          <div className="absolute inset-0 flex items-center justify-center text-cornsilk">
                            <Loader2 className="h-6 w-6 animate-spin" />
                          </div>
                        )}
                      </div>
                      <button type="button" onClick={capturePhoto} disabled={!camReady} className="btn-primary w-full">
                        <Camera className="h-4 w-4" /> Capture photo
                      </button>
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
                  <p className="text-xs text-muted-foreground">Paste a direct link to an image (JPG or PNG).</p>
                </div>
              )}
            </m.div>
          </AnimatePresence>
        </div>

        {notice && (
          <p className="border-t border-border px-3 py-2 text-xs font-medium text-destructive">{notice}</p>
        )}
      </div>

      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">Defaults to your Google photo.</p>
        {value && (
          <button
            type="button"
            onClick={() => onChange('')}
            className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
          >
            <RotateCcw className="h-3.5 w-3.5" /> Reset to default
          </button>
        )}
      </div>
    </div>
  )
}

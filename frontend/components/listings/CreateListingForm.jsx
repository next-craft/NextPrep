'use client'
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import api from '@/lib/api'
import { EXAM_CATEGORIES } from '@/constants/examCategories'
import { LISTING_TYPES } from '@/constants/listingTypes'
import { CONDITIONS } from '@/constants/conditions'
import { CITIES } from '@/constants/cities'
import { SUBJECTS } from '@/constants/subjects'
import ImageUploader from '@/components/listings/ImageUploader'
import PasskeyReveal from '@/components/listings/PasskeyReveal'
import { Reveal, Stagger, StaggerItem } from '@/components/shared/motion'

export default function CreateListingForm() {
  const [passkey, setPasskey] = useState(null)
  const [listingId, setListingId] = useState(null)
  const [images, setImages] = useState([])

  const { mutate, isPending, error } = useMutation({
    // API: POST /listings — returns { listing, passkey } (passkey shown once)
    mutationFn: (data) => api.post('/listings', data),
    onSuccess: ({ data }) => {
      setPasskey(data.passkey)
      setListingId(data.listing.id)
    },
  })

  if (passkey) {
    return (
      <div className="container py-10">
        <PasskeyReveal passkey={passkey} listingId={listingId} />
      </div>
    )
  }

  function handleSubmit(e) {
    e.preventDefault()
    if (images.length === 0) return // at least one image required
    const fd = new FormData(e.target)
    const asking_price = parseInt(fd.get('asking_price'), 10)
    const original_price = fd.get('original_price') ? parseInt(fd.get('original_price'), 10) : undefined
    mutate({
      title: fd.get('title'),
      description: fd.get('description') || undefined,
      exam_category: fd.get('exam_category'),
      subject: fd.get('subject') || undefined,
      listing_type: fd.get('listing_type'),
      condition: fd.get('condition'),
      asking_price,
      original_price,
      city: fd.get('city'),
      images,
    })
  }

  return (
    <div className="container py-8">
      <div className="mx-auto max-w-2xl">
        <Reveal>
          <h1 className="font-display text-2xl font-semibold sm:text-3xl">Create a listing</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            List physical study material you own. No pirated scans, photocopied books, or unauthorized
            reproductions.
          </p>
        </Reveal>

        {error && (
          <div className="mt-4 animate-shake rounded-lg border border-[#e4b3a6] bg-[#f7e6e0] px-4 py-3 text-sm font-medium text-[#8f3322]">
            {error.response?.data?.detail || 'Something went wrong. Please check the form and try again.'}
          </div>
        )}

        <Stagger as="form" onSubmit={handleSubmit} gap={0.05} className="mt-6 space-y-5">
          <StaggerItem>
            <label htmlFor="title" className="label">Title *</label>
            <input
              id="title"
              name="title"
              required
              maxLength={120}
              className="input"
              placeholder="e.g. HC Verma Concepts of Physics Vol 1 & 2"
            />
          </StaggerItem>

          <StaggerItem>
            <label htmlFor="description" className="label">Description</label>
            <textarea
              id="description"
              name="description"
              maxLength={1000}
              rows={4}
              className="textarea"
              placeholder="Edition, what's included, any markings or wear…"
            />
          </StaggerItem>

          <StaggerItem>
            <label className="label">Images *</label>
            <ImageUploader value={images} onChange={setImages} max={5} />
            <p className="mt-1 text-xs text-muted-foreground">At least one image is required.</p>
          </StaggerItem>

          <StaggerItem className="grid gap-5 sm:grid-cols-2">
            <div>
              <label htmlFor="exam_category" className="label">Exam category *</label>
              <select id="exam_category" name="exam_category" required defaultValue="" className="input">
                <option value="" disabled>Select category…</option>
                {EXAM_CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="subject" className="label">Subject</label>
              <input
                id="subject"
                name="subject"
                list="subject-options-form"
                className="input"
                placeholder="e.g. Physics"
              />
              <datalist id="subject-options-form">
                {SUBJECTS.map((s) => (
                  <option key={s} value={s} />
                ))}
              </datalist>
            </div>

            <div>
              <label htmlFor="listing_type" className="label">Material type *</label>
              <select id="listing_type" name="listing_type" required defaultValue="" className="input">
                <option value="" disabled>Select type…</option>
                {LISTING_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="condition" className="label">Condition *</label>
              <select id="condition" name="condition" required defaultValue="" className="input">
                <option value="" disabled>Select condition…</option>
                {CONDITIONS.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="asking_price" className="label">Asking price (₹) *</label>
              <input id="asking_price" name="asking_price" type="number" min={1} required className="input" placeholder="450" />
            </div>

            <div>
              <label htmlFor="original_price" className="label">Original price (₹)</label>
              <input id="original_price" name="original_price" type="number" min={1} className="input" placeholder="750" />
            </div>

            <div className="sm:col-span-2">
              <label htmlFor="city" className="label">City *</label>
              <select id="city" name="city" required defaultValue="" className="input">
                <option value="" disabled>Select city…</option>
                {CITIES.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>
          </StaggerItem>

          <StaggerItem>
            <button type="submit" disabled={isPending || images.length === 0} className="btn-primary w-full">
              {isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> Creating…
                </>
              ) : (
                'Create listing'
              )}
            </button>
          </StaggerItem>
        </Stagger>
      </div>
    </div>
  )
}

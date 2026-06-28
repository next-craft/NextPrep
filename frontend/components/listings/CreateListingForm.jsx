'use client'
import { useEffect, useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import api from '@/lib/api'
import { useMe } from '@/lib/queries'
import { EXAM_CATEGORIES } from '@/constants/examCategories'
import { LISTING_TYPES } from '@/constants/listingTypes'
import { CONDITIONS } from '@/constants/conditions'
import { STATES } from '@/constants/states'
import { DISTRICTS_BY_STATE } from '@/constants/districts'
import { SUBJECTS } from '@/constants/subjects'
import { YEARS } from '@/constants/years'
import ImageUploader from '@/components/listings/ImageUploader'
import CollegeCombobox from '@/components/listings/CollegeCombobox'
import PasskeyReveal from '@/components/listings/PasskeyReveal'
import { Reveal, Stagger, StaggerItem } from '@/components/shared/motion'

const EMPTY_COLLEGE = { college_id: null, college_other: null, college: null }

export default function CreateListingForm() {
  const [passkey, setPasskey] = useState(null)
  const [listingId, setListingId] = useState(null)
  const [images, setImages] = useState([])
  const [state, setState] = useState('') // drives the dependent City/District options
  const [college, setCollege] = useState(EMPTY_COLLEGE)

  // Autofill the campus from the signed-in user's profile, but keep it editable /
  // clearable — a listing can carry a different campus than the profile. Only
  // seed while the field is still untouched (empty).
  const { data: me } = useMe()
  const seeded = useRef(false)
  useEffect(() => {
    // Seed exactly once, on the first `me` resolution — never on later refetches.
    // A campus the user deliberately clears returns the field to its empty shape,
    // so a re-run would silently re-apply the cleared campus.
    if (!me || seeded.current) return
    seeded.current = true
    if (me.college) setCollege({ college_id: me.college.id ?? null, college_other: null, college: me.college })
    else if (me.college_other) setCollege({ college_id: null, college_other: me.college_other, college: null })
  }, [me])

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
    const year = fd.get('year') ? parseInt(fd.get('year'), 10) : undefined
    mutate({
      title: fd.get('title'),
      description: fd.get('description') || undefined,
      exam_category: fd.get('exam_category'),
      subject: fd.get('subject') || undefined,
      listing_type: fd.get('listing_type'),
      condition: fd.get('condition'),
      asking_price,
      original_price,
      year,
      edition: fd.get('edition') || undefined,
      state: fd.get('state'),
      city: fd.get('city'),
      // At most one of these is set (the combobox enforces it); send only what's chosen.
      college_id: college.college_id || undefined,
      college_other: college.college_other || undefined,
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
              <select id="exam_category" name="exam_category" required defaultValue="" className="select">
                <option value="" disabled>Select category…</option>
                {EXAM_CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="subject" className="label">Subject</label>
              <select id="subject" name="subject" defaultValue="" className="select">
                <option value="">Select subject…</option>
                {SUBJECTS.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="listing_type" className="label">Material type *</label>
              <select id="listing_type" name="listing_type" required defaultValue="" className="select">
                <option value="" disabled>Select type…</option>
                {LISTING_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="condition" className="label">Condition *</label>
              <select id="condition" name="condition" required defaultValue="" className="select">
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

            <div>
              <label htmlFor="year" className="label">Year</label>
              <select id="year" name="year" defaultValue="" className="select">
                <option value="">Select year…</option>
                {YEARS.map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="edition" className="label">Edition</label>
              <input id="edition" name="edition" maxLength={50} className="input" placeholder="e.g. 7th edition" />
            </div>

            <div>
              <label htmlFor="state" className="label">State *</label>
              <select
                id="state"
                name="state"
                required
                value={state}
                onChange={(e) => setState(e.target.value)}
                className="select"
              >
                <option value="" disabled>Select state…</option>
                {STATES.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="city" className="label">City / District *</label>
              {/* keyed by state so the selection resets when the state changes */}
              <select id="city" name="city" key={state} required defaultValue="" disabled={!state} className="select">
                <option value="" disabled>{state ? 'Select district…' : 'Select a state first'}</option>
                {(DISTRICTS_BY_STATE[state] || []).map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </div>

            <div className="sm:col-span-2">
              <label className="label">College</label>
              <CollegeCombobox value={college} onChange={setCollege} />
              <p className="mt-1 text-xs text-muted-foreground">
                Optional — auto-filled from your profile. Buyers can find listings from their own campus.
              </p>
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

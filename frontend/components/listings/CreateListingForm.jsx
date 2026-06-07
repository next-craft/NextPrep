'use client'
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import api from '@/lib/api'
import { EXAM_CATEGORIES } from '@/constants/examCategories'
import { LISTING_TYPES } from '@/constants/listingTypes'
import { CONDITIONS } from '@/constants/conditions'
import PasskeyReveal from '@/components/listings/PasskeyReveal'

export default function CreateListingForm() {
  const router = useRouter()
  const [passkey, setPasskey] = useState(null)
  const [listingId, setListingId] = useState(null)

  const { mutate, isPending, error } = useMutation({
    mutationFn: (data) => api.post('/listings', data),
    onSuccess: ({ data }) => {
      setPasskey(data.passkey)
      setListingId(data.listing.id)
    },
  })

  if (passkey) return <PasskeyReveal passkey={passkey} listingId={listingId} />

  function handleSubmit(e) {
    e.preventDefault()
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
    })
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-lg mx-auto p-6 space-y-4">
      <h1 className="text-2xl font-bold">Create Listing</h1>

      {error && (
        <div className="text-red-600 text-sm">
          {error.response?.data?.detail || 'Something went wrong.'}
        </div>
      )}

      <div>
        <label className="label">Title *</label>
        <input name="title" required maxLength={120} className="input" />
      </div>

      <div>
        <label className="label">Description</label>
        <textarea name="description" maxLength={1000} className="input" rows={4} />
      </div>

      <div>
        <label className="label">Exam Category *</label>
        <select name="exam_category" required className="input">
          {EXAM_CATEGORIES.map(c => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </select>
      </div>

      <div>
        <label className="label">Subject</label>
        <input name="subject" className="input" placeholder="e.g. Physics, Organic Chemistry" />
      </div>

      <div>
        <label className="label">Listing Type *</label>
        <select name="listing_type" required className="input">
          {LISTING_TYPES.map(t => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
      </div>

      <div>
        <label className="label">Condition *</label>
        <select name="condition" required className="input">
          {CONDITIONS.map(c => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="label">Asking Price (₹) *</label>
          <input name="asking_price" type="number" min={1} required className="input" />
        </div>
        <div>
          <label className="label">Original Price (₹)</label>
          <input name="original_price" type="number" min={1} className="input" />
        </div>
      </div>

      <div>
        <label className="label">City *</label>
        <input name="city" required className="input" placeholder="e.g. Delhi, Mumbai" />
      </div>

      <button type="submit" disabled={isPending} className="btn-primary w-full">
        {isPending ? 'Creating…' : 'Create Listing'}
      </button>
    </form>
  )
}

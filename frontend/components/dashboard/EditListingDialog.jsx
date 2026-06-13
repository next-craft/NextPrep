'use client'
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Loader2, Lock } from 'lucide-react'
import api from '@/lib/api'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { toast } from '@/components/ui/sonner'
import { CONDITIONS } from '@/constants/conditions'
import { CITIES } from '@/constants/cities'
import { SUBJECTS } from '@/constants/subjects'
import { LISTING_TYPE_LABEL } from '@/lib/utils'
import { EXAM_CATEGORY_LABEL } from '@/constants/examCategories'
import ImageUploader from '@/components/listings/ImageUploader'

/** Edit a listing's mutable fields. listing_type + exam_category are locked
 *  (the PATCH schema doesn't accept them — anti bait-and-switch). */
export default function EditListingDialog({ listing, open, onOpenChange, onSaved }) {
  const [form, setForm] = useState({
    title: listing.title || '',
    description: listing.description || '',
    subject: listing.subject || '',
    asking_price: listing.asking_price ?? '',
    original_price: listing.original_price ?? '',
    condition: listing.condition || 'A',
    city: listing.city || '',
  })
  const [images, setImages] = useState(listing.images || [])
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const { mutate, isPending } = useMutation({
    mutationFn: async (payload) => {
      // API: PATCH /listings/{id} — owner only
      await api.patch(`/listings/${listing.id}`, payload)
      return payload
    },
    onSuccess: (payload) => {
      onSaved?.({ ...listing, ...payload })
      toast.success('Listing updated')
      onOpenChange(false)
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Could not update the listing.'),
  })

  const submit = (e) => {
    e.preventDefault()
    mutate({
      title: form.title,
      description: form.description || null,
      subject: form.subject || null,
      asking_price: form.asking_price ? parseInt(form.asking_price, 10) : undefined,
      original_price: form.original_price ? parseInt(form.original_price, 10) : null,
      condition: form.condition,
      city: form.city,
      images,
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit listing</DialogTitle>
          <DialogDescription>
            Material type and exam category can&apos;t be changed after posting.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={submit} className="space-y-4">
          <div className="flex animate-fade-in flex-wrap items-center gap-1.5 rounded-md bg-muted/50 px-2.5 py-1.5">
            <span className="badge">{LISTING_TYPE_LABEL[listing.listing_type] ?? listing.listing_type}</span>
            <span className="badge">{EXAM_CATEGORY_LABEL[listing.exam_category] ?? listing.exam_category}</span>
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <Lock className="h-3 w-3" /> locked
            </span>
          </div>

          <div>
            <label htmlFor="e-title" className="label">Title</label>
            <input id="e-title" className="input" value={form.title} onChange={set('title')} maxLength={120} required />
          </div>

          <div>
            <label htmlFor="e-desc" className="label">Description</label>
            <textarea id="e-desc" className="textarea" value={form.description} onChange={set('description')} maxLength={1000} rows={3} />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="e-price" className="label">Asking price (₹)</label>
              <input id="e-price" className="input" type="number" min={1} value={form.asking_price} onChange={set('asking_price')} required />
            </div>
            <div>
              <label htmlFor="e-orig" className="label">Original price (₹)</label>
              <input id="e-orig" className="input" type="number" min={1} value={form.original_price} onChange={set('original_price')} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="e-cond" className="label">Condition</label>
              <select id="e-cond" className="input" value={form.condition} onChange={set('condition')}>
                {CONDITIONS.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="e-city" className="label">City</label>
              <select id="e-city" className="input" value={form.city} onChange={set('city')}>
                {CITIES.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label htmlFor="e-subject" className="label">Subject</label>
            <input id="e-subject" className="input" list="subject-edit" value={form.subject} onChange={set('subject')} />
            <datalist id="subject-edit">
              {SUBJECTS.map((s) => (
                <option key={s} value={s} />
              ))}
            </datalist>
          </div>

          <div>
            <label className="label">Images</label>
            <ImageUploader value={images} onChange={setImages} max={5} />
          </div>

          <DialogFooter>
            <button type="button" onClick={() => onOpenChange(false)} className="btn-ghost">
              Cancel
            </button>
            <button type="submit" disabled={isPending} className="btn-primary">
              {isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> Saving…
                </>
              ) : (
                'Save changes'
              )}
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

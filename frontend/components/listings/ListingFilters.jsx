'use client'
import { useRouter } from 'next/navigation'
import { EXAM_CATEGORIES } from '@/constants/examCategories'
import { LISTING_TYPES } from '@/constants/listingTypes'
import { CONDITIONS } from '@/constants/conditions'

export default function ListingFilters({ current }) {
  const router = useRouter()

  function handleChange(key, value) {
    const params = new URLSearchParams(current)
    if (value) params.set(key, value)
    else params.delete(key)
    router.push(`/listings?${params.toString()}`)
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="label text-xs">Search</label>
        <input
          className="input text-sm"
          defaultValue={current.q || ''}
          placeholder="Title or description"
          onBlur={e => handleChange('q', e.target.value)}
        />
      </div>
      <div>
        <label className="label text-xs">Exam category</label>
        <select className="input text-sm" defaultValue={current.exam_category || ''} onChange={e => handleChange('exam_category', e.target.value)}>
          <option value="">All</option>
          {EXAM_CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
      </div>
      <div>
        <label className="label text-xs">Type</label>
        <select className="input text-sm" defaultValue={current.listing_type || ''} onChange={e => handleChange('listing_type', e.target.value)}>
          <option value="">All</option>
          {LISTING_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
      </div>
      <div>
        <label className="label text-xs">Condition</label>
        <select className="input text-sm" defaultValue={current.condition || ''} onChange={e => handleChange('condition', e.target.value)}>
          <option value="">All</option>
          {CONDITIONS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
      </div>
    </div>
  )
}

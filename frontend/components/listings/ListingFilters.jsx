'use client'
import { useRouter } from 'next/navigation'
import { Search, X } from 'lucide-react'
import { EXAM_CATEGORIES } from '@/constants/examCategories'
import { LISTING_TYPES } from '@/constants/listingTypes'
import { CONDITIONS } from '@/constants/conditions'
import { CITIES } from '@/constants/cities'
import { SUBJECTS } from '@/constants/subjects'
import { FILTER_KEYS } from '@/constants/filters'

export default function ListingFilters({ current = {}, onNavigate, showHeader = true }) {
  const router = useRouter()
  const activeCount = FILTER_KEYS.filter((k) => current[k]).length

  function apply(next) {
    const params = new URLSearchParams()
    FILTER_KEYS.forEach((k) => {
      if (next[k]) params.set(k, next[k])
    })
    const qs = params.toString()
    router.push(qs ? `/listings?${qs}` : '/listings')
    onNavigate?.()
  }

  const handleChange = (key, value) => apply({ ...current, [key]: value || undefined })
  const clearAll = () => {
    router.push('/listings')
    onNavigate?.()
  }

  // Commit a free-text field only when its value actually changed.
  const commitText = (key) => (e) => {
    if ((e.target.value || '') !== (current[key] || '')) handleChange(key, e.target.value)
  }
  const commitOnEnter = (key) => (e) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleChange(key, e.currentTarget.value)
    }
  }

  return (
    <div className="space-y-5">
      {showHeader && (
        <div className="flex items-center justify-between">
          <h2 className="font-display text-base font-semibold">Filters</h2>
          {activeCount > 0 && (
            <button
              type="button"
              onClick={clearAll}
              className="inline-flex items-center gap-1 text-xs font-medium text-primary transition-colors hover:text-light_bronze-200"
            >
              <X className="h-3.5 w-3.5" /> Clear all
            </button>
          )}
        </div>
      )}

      <div>
        <label htmlFor="f-q" className="label">Search</label>
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            id="f-q"
            className="input pl-9"
            defaultValue={current.q || ''}
            placeholder="Title or description"
            onKeyDown={commitOnEnter('q')}
            onBlur={commitText('q')}
          />
        </div>
      </div>

      <div>
        <label htmlFor="f-exam" className="label">Exam category</label>
        <select
          id="f-exam"
          className="input"
          value={current.exam_category || ''}
          onChange={(e) => handleChange('exam_category', e.target.value)}
        >
          <option value="">All categories</option>
          {EXAM_CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="f-type" className="label">Material type</label>
        <select
          id="f-type"
          className="input"
          value={current.listing_type || ''}
          onChange={(e) => handleChange('listing_type', e.target.value)}
        >
          <option value="">All types</option>
          {LISTING_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="f-condition" className="label">Condition</label>
        <select
          id="f-condition"
          className="input"
          value={current.condition || ''}
          onChange={(e) => handleChange('condition', e.target.value)}
        >
          <option value="">Any condition</option>
          {CONDITIONS.map((c) => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="f-city" className="label">City</label>
        <select
          id="f-city"
          className="input"
          value={current.city || ''}
          onChange={(e) => handleChange('city', e.target.value)}
        >
          <option value="">All cities</option>
          {CITIES.map((c) => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="f-subject" className="label">Subject</label>
        <input
          id="f-subject"
          list="subject-options"
          className="input"
          defaultValue={current.subject || ''}
          placeholder="Any subject"
          onKeyDown={commitOnEnter('subject')}
          onBlur={commitText('subject')}
        />
        <datalist id="subject-options">
          {SUBJECTS.map((s) => (
            <option key={s} value={s} />
          ))}
        </datalist>
      </div>
    </div>
  )
}

'use client'
import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown, PlusCircle, X } from 'lucide-react'

/**
 * Reusable college typeahead. Colleges live in the DB (not a static constant),
 * so this queries the API as the user types rather than importing a list.
 *
 * Controlled. `value` is `{ college_id, college_other, college }` where
 * `college` is the embedded `{ slug, name }` brief (for showing the selected
 * label without a refetch). `onChange` receives the same shape on every change:
 *   - picking a canonical option → { college_id, college: {slug, name}, college_other: null }
 *   - typing a free-text campus   → { college_other, college_id: null, college: null }
 *   - clearing                    → { college_id: null, college_other: null, college: null }
 *
 * The "My college isn't listed → add it" row switches the control to a free-text
 * input bound to `college_other` and clears any `college_id`. App invariant: at
 * most one of (college_id, college_other) is ever set.
 */
export default function CollegeCombobox({
  value = {},
  onChange,
  id = 'college',
  placeholder = 'Search your college',
  disabled = false,
  allowOther = true,
}) {
  const { college_id, college_other, college } = value

  // "other" mode shows the free-text input. Seed it from an existing
  // college_other value so an already-saved free-text campus opens editable.
  const [otherMode, setOtherMode] = useState(Boolean(college_other))
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [debounced, setDebounced] = useState('')
  const wrapRef = useRef(null)

  // Debounce the typeahead query (250ms) so we don't hit the API every keystroke.
  useEffect(() => {
    const t = setTimeout(() => setDebounced(text.trim()), 250)
    return () => clearTimeout(t)
  }, [text])

  // Keep "other" mode in sync if the controlled value flips externally (e.g.
  // the form resets or autofill arrives after mount).
  useEffect(() => {
    if (college_other) setOtherMode(true)
    else if (!college_id && !college) setOtherMode(false)
  }, [college_other, college_id, college])

  // Close the dropdown on outside click.
  useEffect(() => {
    if (!open) return
    function onDocClick(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [open])

  // API: GET /v1/colleges?q= — only fires while the dropdown is open in select mode.
  const { data: options = [], isFetching } = useQuery({
    queryKey: ['colleges', debounced],
    queryFn: async () => {
      const url = new URL(`${process.env.NEXT_PUBLIC_API_URL}/colleges`)
      if (debounced) url.searchParams.set('q', debounced)
      const res = await fetch(url)
      if (!res.ok) throw new Error('Failed to load colleges')
      return res.json()
    },
    enabled: open && !otherMode,
    staleTime: 60_000,
  })

  const selectedName = college?.name || ''

  function pick(option) {
    onChange?.({ college_id: option.id, college: { slug: option.slug, name: option.name }, college_other: null })
    setOpen(false)
    setText('')
  }

  function clearSelection() {
    onChange?.({ college_id: null, college: null, college_other: null })
    setText('')
  }

  function enterOtherMode() {
    setOtherMode(true)
    setOpen(false)
    // Clear any canonical selection — invariant: only one source at a time.
    onChange?.({ college_id: null, college: null, college_other: college_other || '' })
  }

  function exitOtherMode() {
    setOtherMode(false)
    onChange?.({ college_id: null, college: null, college_other: null })
  }

  function handleOtherChange(e) {
    onChange?.({ college_id: null, college: null, college_other: e.target.value })
  }

  // ── Free-text ("my college isn't listed") mode ──────────────────────────
  if (otherMode) {
    return (
      <div ref={wrapRef}>
        <input
          id={id}
          className="input"
          value={college_other || ''}
          placeholder="Type your college name"
          disabled={disabled}
          onChange={handleOtherChange}
          maxLength={120}
        />
        <div className="mt-1.5 flex items-center justify-between gap-2">
          <p className="text-xs text-muted-foreground">
            We&apos;ll review and add it — it won&apos;t appear in filters until then.
          </p>
          <button
            type="button"
            onClick={exitOtherMode}
            className="shrink-0 text-xs font-medium text-primary transition-colors hover:text-light_bronze-200"
          >
            Pick from list
          </button>
        </div>
      </div>
    )
  }

  // ── Canonical select mode ────────────────────────────────────────────────
  return (
    <div ref={wrapRef} className="relative">
      {(college_id || college) && selectedName ? (
        // A college is selected — show its name as a filled "trigger" with a clear button.
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={disabled}
            // Clicking the filled trigger reverts to the search input (clearing the
            // canonical pick) so the user can pick a different campus.
            onClick={() => {
              clearSelection()
              setOpen(true)
            }}
            className="select flex items-center justify-between text-left"
          >
            <span className="truncate">{selectedName}</span>
          </button>
          <button
            type="button"
            onClick={clearSelection}
            aria-label="Clear college"
            className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-md border border-input text-muted-foreground transition-colors hover:border-light_bronze-500 hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      ) : (
        <div className="relative">
          <input
            id={id}
            className="input pr-10"
            value={text}
            placeholder={placeholder}
            disabled={disabled}
            onChange={(e) => {
              setText(e.target.value)
              setOpen(true)
            }}
            onFocus={() => setOpen(true)}
            autoComplete="off"
          />
          <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-light_bronze-300" />
        </div>
      )}

      {open && !college_id && (
        <ul className="absolute z-20 mt-1.5 max-h-64 w-full overflow-auto rounded-md border border-input bg-card py-1 shadow-warm-lg">
          {isFetching && (
            <li className="px-3.5 py-2 text-sm text-muted-foreground">Searching…</li>
          )}
          {!isFetching && options.length === 0 && (
            <li className="px-3.5 py-2 text-sm text-muted-foreground">
              {debounced ? 'No colleges match.' : 'Type to search colleges.'}
            </li>
          )}
          {options.map((opt) => (
            <li key={opt.id}>
              <button
                type="button"
                onClick={() => pick(opt)}
                className="flex w-full items-center justify-between gap-2 px-3.5 py-2 text-left text-sm transition-colors hover:bg-secondary"
              >
                <span className="min-w-0">
                  <span className="block truncate text-foreground">{opt.name}</span>
                  {(opt.city || opt.state) && (
                    <span className="block truncate text-xs text-muted-foreground">
                      {[opt.city, opt.state].filter(Boolean).join(', ')}
                    </span>
                  )}
                </span>
              </button>
            </li>
          ))}

          {/* Persistent "not listed" escape hatch — hidden in filter mode (free text is never a filter). */}
          {allowOther && (
            <li className="mt-1 border-t border-border">
              <button
                type="button"
                onClick={enterOtherMode}
                className="flex w-full items-center gap-2 px-3.5 py-2 text-left text-sm font-medium text-primary transition-colors hover:bg-secondary"
              >
                <PlusCircle className="h-4 w-4 shrink-0" />
                My college isn&apos;t listed — add it
              </button>
            </li>
          )}
        </ul>
      )}
    </div>
  )
}

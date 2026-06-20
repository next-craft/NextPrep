'use client'
import { useState } from 'react'
import Link from 'next/link'
import { AnimatePresence } from 'framer-motion'
import {
  MoreVertical,
  Pencil,
  Pause,
  Play,
  KeyRound,
  Trash2,
  Plus,
  Store,
  BookOpen,
} from 'lucide-react'
import { m } from '@/components/shared/motion'
import { EASE, SPRING } from '@/lib/motion'
import api from '@/lib/api'
import { cn, formatPrice, listingStatus } from '@/lib/utils'
import { ConditionBadge, ListingTypeBadge } from '@/components/shared/badges'
import StatusPill from '@/components/shared/status-pill'
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from '@/components/ui/dropdown-menu'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { EmptyState } from '@/components/shared/states'
import { toast } from '@/components/ui/sonner'
import PasskeyDisplay from '@/components/shared/passkey-display'
import EditListingDialog from './EditListingDialog'
import { useQueryClient } from '@tanstack/react-query'
import { useMyListings } from '@/lib/queries'

// Section accent colours mirror the "living status" palette in status-pill.jsx
// so a seller can scan their inventory by colour alone.
const GROUPS = [
  { key: 'active', label: 'Active', accent: '#5b8a3c', tint: 'bg-[#eaf1de] text-[#3f6733] ring-[#cad8b0]' },
  { key: 'paused', label: 'Paused', accent: '#b07d1e', tint: 'bg-[#fbf1d6] text-[#8a5e12] ring-[#ecd6a0]' },
  { key: 'sold', label: 'Sold', accent: '#b3452f', tint: 'bg-[#f7e6e0] text-[#8f3322] ring-[#e4b3a6]' },
]

export default function SellingTab() {
  const queryClient = useQueryClient()
  const { data: listings = [], isLoading } = useMyListings()
  const [editing, setEditing] = useState(null)
  const [passkeyInfo, setPasskeyInfo] = useState(null)
  const [deleting, setDeleting] = useState(null)

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['my-listings'] })

  const grouped = { active: [], paused: [], sold: [] }
  for (const l of listings) grouped[listingStatus(l)].push(l)

  async function pauseResume(l) {
    const next = !l.is_available
    try {
      // API: PATCH /listings/{id}
      await api.patch(`/listings/${l.id}`, { is_available: next })
      refresh()
      toast.success(next ? 'Listing resumed' : 'Listing paused')
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Could not update the listing.')
    }
  }

  async function regenerate(l) {
    try {
      // API: PATCH /listings/{id}/passkey
      const { data } = await api.patch(`/listings/${l.id}/passkey`)
      setPasskeyInfo({ listing: l, passkey: data.passkey })
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Could not regenerate the passkey.')
    }
  }

  async function confirmDelete() {
    const l = deleting
    setDeleting(null)
    try {
      // API: DELETE /listings/{id} (soft delete)
      await api.delete(`/listings/${l.id}`)
      refresh()
      toast.success('Listing deleted')
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Could not delete the listing.')
    }
  }

  const onSaved = () => refresh()

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading your listings…</p>
  }

  if (!listings.length) {
    return (
      <EmptyState
        icon={Store}
        title="You haven't listed anything yet"
        description="Turn your old books, notes and modules into cash."
        action={
          <Link href="/listings/new" className="btn-primary">
            <Plus className="h-4 w-4" /> Create a listing
          </Link>
        }
      />
    )
  }

  return (
    <div className="space-y-9">
      {GROUPS.map(
        ({ key, label, accent, tint }) =>
          grouped[key].length > 0 && (
            <section key={key}>
              <header className="mb-3.5 flex items-center gap-3">
                <span
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ backgroundColor: accent, boxShadow: `0 0 0 3px ${accent}22` }}
                />
                <h3 className="text-xs font-semibold uppercase tracking-[0.12em] text-foreground/70">
                  {label}
                </h3>
                <span
                  className={cn(
                    'inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full px-1.5 text-[11px] font-semibold tabular-nums ring-1 ring-inset',
                    tint
                  )}
                >
                  {grouped[key].length}
                </span>
                <span className="h-px flex-1 bg-gradient-to-r from-border to-transparent" />
              </header>
              <div className="space-y-3">
                <AnimatePresence mode="popLayout">
                  {grouped[key].map((l, i) => (
                    <m.div
                      key={l.id}
                      layout
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0, transition: { delay: i * 0.04, duration: 0.3, ease: EASE.warm } }}
                      exit={{ opacity: 0, scale: 0.96, x: -12, transition: { duration: 0.2, ease: EASE.warm } }}
                      whileHover={{ y: -2, transition: SPRING }}
                      className="card group relative flex items-center gap-4 overflow-hidden p-3 pl-4 sm:p-4 sm:pl-5"
                    >
                      {/* status accent rail */}
                      <span
                        aria-hidden
                        className="absolute inset-y-0 left-0 w-1"
                        style={{ backgroundColor: accent }}
                      />
                      <Link
                        href={`/listings/${l.id}`}
                        className="relative flex h-[68px] w-[68px] shrink-0 items-center justify-center overflow-hidden rounded-lg bg-papaya_whip-700 text-light_bronze-500 ring-1 ring-black/5"
                      >
                        {l.images?.[0] ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={l.images[0]}
                            alt=""
                            className={cn(
                              'h-full w-full object-cover transition-transform duration-500 group-hover:scale-105',
                              key === 'sold' && 'opacity-65 grayscale-[35%]'
                            )}
                          />
                        ) : (
                          <BookOpen className="h-6 w-6" />
                        )}
                        {key === 'sold' && (
                          <span className="pointer-events-none absolute inset-0 flex items-center justify-center">
                            <span className="-rotate-12 rounded-sm border-2 border-[#b3452f]/80 bg-[#fffdf6]/85 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-[#8f3322] shadow-sm">
                              Sold
                            </span>
                          </span>
                        )}
                      </Link>
                      <div className="min-w-0 flex-1">
                        <Link
                          href={`/listings/${l.id}`}
                          className="block truncate font-medium leading-snug transition-colors hover:text-primary"
                        >
                          {l.title}
                        </Link>
                        <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                          <StatusPill status={key} />
                          <ConditionBadge code={l.condition} showLabel={false} />
                          <ListingTypeBadge type={l.listing_type} />
                        </div>
                      </div>
                      <div className="ml-auto flex shrink-0 items-center gap-1 self-stretch sm:gap-2">
                        <div className="flex flex-col items-end justify-center">
                          <span className="font-display text-base font-semibold leading-none tracking-tight text-foreground sm:text-lg">
                            {formatPrice(l.asking_price)}
                          </span>
                          <span className="mt-1 text-[10px] uppercase tracking-wide text-muted-foreground">
                            {key === 'sold' ? 'final price' : 'asking'}
                          </span>
                        </div>
                        <RowActions
                          status={key}
                          onEdit={() => setEditing(l)}
                          onPauseResume={() => pauseResume(l)}
                          onRegenerate={() => regenerate(l)}
                          onDelete={() => setDeleting(l)}
                        />
                      </div>
                    </m.div>
                  ))}
                </AnimatePresence>
              </div>
            </section>
          )
      )}

      {editing && (
        <EditListingDialog
          key={editing.id}
          listing={editing}
          open={!!editing}
          onOpenChange={(o) => !o && setEditing(null)}
          onSaved={onSaved}
        />
      )}

      {/* Regenerated passkey — shown once */}
      <Dialog open={!!passkeyInfo} onOpenChange={(o) => !o && setPasskeyInfo(null)}>
        <DialogContent className="max-w-md border-0 bg-transparent p-0 shadow-none">
          {passkeyInfo && (
            <PasskeyDisplay
              passkey={passkeyInfo.passkey}
              listingId={passkeyInfo.listing.id}
              heading="New passkey generated"
            />
          )}
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <Dialog open={!!deleting} onOpenChange={(o) => !o && setDeleting(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete this listing?</DialogTitle>
            <DialogDescription>
              “{deleting?.title}” will be removed from the marketplace. This can&apos;t be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <button onClick={() => setDeleting(null)} className="btn-ghost">
              Cancel
            </button>
            <button onClick={confirmDelete} className="btn-danger">
              Delete
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function RowActions({ status, onEdit, onPauseResume, onRegenerate, onDelete }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="btn-ghost h-9 w-9 shrink-0 px-0" aria-label="Listing actions">
        <MoreVertical className="h-5 w-5" />
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        {status !== 'sold' && (
          <DropdownMenuItem onSelect={onEdit}>
            <Pencil className="h-4 w-4" /> Edit
          </DropdownMenuItem>
        )}
        {status === 'active' && (
          <DropdownMenuItem onSelect={onPauseResume}>
            <Pause className="h-4 w-4" /> Pause
          </DropdownMenuItem>
        )}
        {status === 'paused' && (
          <DropdownMenuItem onSelect={onPauseResume}>
            <Play className="h-4 w-4" /> Resume
          </DropdownMenuItem>
        )}
        {status !== 'sold' && (
          <DropdownMenuItem onSelect={onRegenerate}>
            <KeyRound className="h-4 w-4" /> Regenerate passkey
          </DropdownMenuItem>
        )}
        {status !== 'sold' && (
          <DropdownMenuItem
            onSelect={onDelete}
            className="text-destructive focus:bg-[#f7e6e0] focus:text-[#8f3322]"
          >
            <Trash2 className="h-4 w-4" /> Delete
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

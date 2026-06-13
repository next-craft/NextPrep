'use client'
import { useState } from 'react'
import Link from 'next/link'
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
import api from '@/lib/api'
import { formatPrice, listingStatus } from '@/lib/utils'
import { ConditionBadge, ListingStatusBadge, ListingTypeBadge } from '@/components/shared/badges'
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

const GROUPS = [
  { key: 'active', label: 'Active' },
  { key: 'paused', label: 'Paused' },
  { key: 'sold', label: 'Sold' },
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
    <div className="space-y-8">
      {GROUPS.map(
        ({ key, label }) =>
          grouped[key].length > 0 && (
            <section key={key}>
              <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                {label} · {grouped[key].length}
              </h3>
              <div className="space-y-3">
                {grouped[key].map((l) => (
                  <div key={l.id} className="card flex items-center gap-4 p-3 sm:p-4">
                    <Link
                      href={`/listings/${l.id}`}
                      className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-md bg-papaya_whip-700 text-light_bronze-500"
                    >
                      {l.images?.[0] ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={l.images[0]} alt="" className="h-full w-full object-cover" />
                      ) : (
                        <BookOpen className="h-6 w-6" />
                      )}
                    </Link>
                    <div className="min-w-0 flex-1">
                      <Link href={`/listings/${l.id}`} className="block truncate font-medium hover:underline">
                        {l.title}
                      </Link>
                      <p className="mt-0.5 text-sm font-semibold">{formatPrice(l.asking_price)}</p>
                      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                        <ListingStatusBadge status={key} />
                        <ConditionBadge code={l.condition} showLabel={false} />
                        <ListingTypeBadge type={l.listing_type} />
                      </div>
                    </div>
                    <RowActions
                      status={key}
                      onEdit={() => setEditing(l)}
                      onPauseResume={() => pauseResume(l)}
                      onRegenerate={() => regenerate(l)}
                      onDelete={() => setDeleting(l)}
                    />
                  </div>
                ))}
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

'use client'
import { useState } from 'react'
import Link from 'next/link'
import { useMutation } from '@tanstack/react-query'
import { Flag, Loader2 } from 'lucide-react'
import api from '@/lib/api'
import { cn } from '@/lib/utils'
import { toast } from '@/components/ui/sonner'
import { REPORT_REASONS } from '@/constants/reportReasons'
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from '@/components/ui/dialog'

const triggerClass =
  'inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-destructive'

/**
 * "Report listing" control for the listing detail page. Shown to non-owners.
 * Logged-out users are sent to /login; logged-in users get a reason + optional
 * note dialog that POSTs to /reports. The endpoint never auto-hides the listing
 * and never exposes report counts — it feeds the manual moderation queue.
 */
export default function ReportListingDialog({ listingId, isLoggedIn, className }) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState('')
  const [note, setNote] = useState('')

  const { mutate, isPending } = useMutation({
    // API: POST /reports — send null (not '') so the DB stores NULL for an empty note
    mutationFn: () => api.post('/reports', { listing_id: listingId, reason, note: note || null }),
    onSuccess: () => {
      toast.success('Thanks — our team will review this listing.')
      setOpen(false)
      setReason('')
      setNote('')
    },
    onError: (err) => {
      // Generic copy — never surface raw backend error detail in the UI.
      if (err.response?.status === 429) {
        toast.error("You've reported too many listings. Please try again later.")
        return
      }
      toast.error('Could not submit the report. Please try again.')
    },
  })

  if (!isLoggedIn) {
    return (
      <Link href="/login" className={cn(triggerClass, className)}>
        <Flag className="h-3.5 w-3.5" /> Report listing
      </Link>
    )
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger className={cn(triggerClass, className)}>
        <Flag className="h-3.5 w-3.5" /> Report listing
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Report this listing</DialogTitle>
          <DialogDescription>
            Tell us what&apos;s wrong. Reports are reviewed by our team — the seller is not told
            who reported them.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="report-reason" className="text-sm font-medium">
              Reason
            </label>
            <select
              id="report-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              disabled={isPending}
              className="select"
            >
              <option value="" disabled>
                Select a reason…
              </option>
              {REPORT_REASONS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="report-note" className="text-sm font-medium">
              Details <span className="font-normal text-muted-foreground">(optional)</span>
            </label>
            <textarea
              id="report-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              disabled={isPending}
              maxLength={1000}
              rows={3}
              placeholder="Anything else we should know?"
              className="w-full resize-none rounded-lg border border-border bg-background p-3 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>
        </div>

        <DialogFooter>
          <DialogClose className="btn-ghost h-11 px-4" disabled={isPending}>
            Cancel
          </DialogClose>
          <button
            type="button"
            onClick={() => mutate()}
            disabled={!reason || isPending}
            className="btn-primary h-11 px-4"
          >
            {isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" /> Submitting…
              </>
            ) : (
              'Submit report'
            )}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

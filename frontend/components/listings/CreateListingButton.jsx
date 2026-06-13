'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Plus } from 'lucide-react'
import { createClient } from '@/lib/supabase/client'
import { useMe } from '@/lib/queries'
import { cn } from '@/lib/utils'

/**
 * Auth-aware "sell" entry point. Safe to render on public pages — it only
 * queries /users/me once we know the visitor is signed in (avoids the
 * 401 → /login redirect for anonymous browsers).
 */
export default function CreateListingButton({ className }) {
  const supabase = createClient()
  const [authed, setAuthed] = useState(null) // null = unknown

  useEffect(() => {
    let mounted = true
    supabase.auth.getSession().then(({ data }) => {
      if (mounted) setAuthed(!!data.session)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const { data: me, isLoading } = useMe({ enabled: authed === true })

  if (authed === null || (authed && isLoading)) {
    return <div className={cn('h-11 w-40 animate-pulse rounded-md bg-light_bronze-800/60', className)} />
  }

  if (!authed) {
    return (
      <Link href="/login" className={cn('btn-primary', className)}>
        <Plus className="h-4 w-4" /> Sell material
      </Link>
    )
  }

  // API: GET /users/me — gate creation behind completed Razorpay onboarding
  if (me?.razorpay_account_id) {
    return (
      <Link href="/listings/new" className={cn('btn-primary', className)}>
        <Plus className="h-4 w-4" /> Create listing
      </Link>
    )
  }

  return (
    <div className="flex flex-col items-start gap-1 sm:items-end">
      <Link href="/sell/onboard" className={cn('btn-primary', className)}>
        <Plus className="h-4 w-4" /> Set up payouts to sell
      </Link>
      <p className="text-xs text-muted-foreground">Complete payment setup to start selling.</p>
    </div>
  )
}

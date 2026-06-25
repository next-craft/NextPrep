'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, BadgeCheck, ExternalLink } from 'lucide-react'
import api from '@/lib/api'
import { useMe } from '@/lib/queries'
import { toast } from '@/components/ui/sonner'
import Avatar from '@/components/shared/avatar'
import AvatarUploader from '@/components/shared/avatar-uploader'
import { CITIES } from '@/constants/cities'

export default function SettingsPage() {
  const { data: me, isLoading } = useMe()
  const queryClient = useQueryClient()
  const [form, setForm] = useState({ full_name: '', city: '', avatar_url: '' })

  useEffect(() => {
    if (me) {
      setForm({
        full_name: me.full_name || '',
        city: me.city || '',
        avatar_url: me.avatar_url || '',
      })
    }
  }, [me])

  const save = useMutation({
    // API: PATCH /users/me — only full_name, city, avatar_url are accepted
    mutationFn: (payload) => api.patch('/users/me', payload).then((r) => r.data),
    onSuccess: (data) => {
      queryClient.setQueryData(['me'], data)
      toast.success('Profile updated')
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Could not save your profile.'),
  })

  if (isLoading || !me) {
    return (
      <div className="flex justify-center py-24">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const submit = (e) => {
    e.preventDefault()
    save.mutate({
      full_name: form.full_name.trim(),
      city: form.city || null,
      avatar_url: form.avatar_url || null,
    })
  }

  // keep the current city selectable even if it predates the predefined list
  const cityInList = CITIES.some((c) => c.value === me.city)

  return (
    <div className="container max-w-2xl py-8">
      <h1 className="font-display text-2xl font-semibold sm:text-3xl">Settings</h1>
      <p className="mt-1 text-sm text-muted-foreground">Manage your public profile.</p>

      <form onSubmit={submit} className="mt-6 space-y-6">
        <div className="card flex flex-col items-center gap-4 p-6 sm:flex-row sm:items-center">
          <Avatar src={form.avatar_url} name={form.full_name} size={72} />
          <div className="flex-1 text-center sm:text-left">
            <p className="flex items-center justify-center gap-1.5 font-medium sm:justify-start">
              {form.full_name || 'Your name'}
              {me.is_verified && <BadgeCheck className="h-4 w-4 text-primary" />}
            </p>
            <p className="text-sm text-muted-foreground">
              {me.books_sold} {me.books_sold === 1 ? 'sale' : 'sales'} · {me.books_bought} bought
              {me.seller_rating ? ` · ★ ${me.seller_rating}` : ''}
            </p>
            <Link
              href={`/users/${me.id}`}
              className="mt-1 inline-flex items-center gap-1 text-sm font-medium text-primary hover:text-light_bronze-200"
            >
              View public profile <ExternalLink className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>

        <div>
          <label htmlFor="full_name" className="label">Full name</label>
          <input id="full_name" className="input" value={form.full_name} onChange={set('full_name')} required maxLength={80} />
        </div>

        <div>
          <label htmlFor="city" className="label">City</label>
          <select id="city" className="select" value={form.city} onChange={set('city')}>
            <option value="">Not set</option>
            {!cityInList && me.city && <option value={me.city}>{me.city}</option>}
            {CITIES.map((c) => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </select>
        </div>

        <div>
          <span className="label">Profile photo</span>
          <AvatarUploader
            value={form.avatar_url}
            onChange={(url) => setForm((f) => ({ ...f, avatar_url: url }))}
          />
        </div>

        <button type="submit" disabled={save.isPending} className="btn-primary">
          {save.isPending ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" /> Saving…
            </>
          ) : (
            'Save changes'
          )}
        </button>
      </form>
    </div>
  )
}

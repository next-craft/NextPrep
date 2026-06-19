'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import {
  Search,
  MessageCircle,
  Plus,
  LogOut,
  User as UserIcon,
  LayoutDashboard,
  Settings,
} from 'lucide-react'
import { createClient } from '@/lib/supabase/client'
import { useMe, useEnrichedConversations } from '@/lib/queries'
import { cn } from '@/lib/utils'
import { m, useReducedMotion } from '@/components/shared/motion'
import { DURATION, EASE } from '@/lib/motion'
import Avatar from '@/components/shared/avatar'
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu'

export default function Navbar() {
  const supabase = createClient()
  const router = useRouter()
  const reduced = useReducedMotion()
  const [authed, setAuthed] = useState(false)
  const [ready, setReady] = useState(false)
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    let mounted = true
    supabase.auth.getSession().then(({ data }) => {
      if (!mounted) return
      setAuthed(!!data.session)
      setReady(true)
    })
    const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
      setAuthed(!!session)
      setReady(true)
    })
    return () => {
      mounted = false
      sub.subscription.unsubscribe()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const { data: me } = useMe({ enabled: authed })
  const { data: conversations } = useEnrichedConversations({
    enabled: authed,
    refetchInterval: authed ? 60_000 : false,
  })
  const unread = (conversations || []).reduce((n, c) => n + (c.unreadCount || 0), 0)

  const signOut = async () => {
    await supabase.auth.signOut()
    router.push('/')
    router.refresh()
  }

  return (
    <m.header
      initial={reduced ? { opacity: 0 } : { y: -16, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: DURATION.base, ease: EASE.warm }}
      className={cn(
        'sticky top-0 z-40 transition-[background-color,box-shadow,border-color] duration-300',
        // At the top: transparent, like the login navbar — only a faint scrim
        // (below) carries the wordmark over the aurora. Once scrolled, a
        // frosted fill fades in so content stays legible beneath it.
        scrolled
          ? 'border-b border-white/40 bg-cornsilk/80 shadow-warm-lg backdrop-blur-md'
          : 'border-b border-transparent bg-transparent'
      )}
    >
      {/* faint top scrim — matches AuthNavbar, keeps the bar reading over the aurora */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-cornsilk/70 to-transparent"
      />
      <div className="container relative flex h-16 items-center gap-3">
        <Link href="/" className="font-display text-xl font-semibold tracking-tight">
          Next<span className="text-primary">Prep</span>
        </Link>

        <Link
          href="/listings"
          className="ml-3 hidden flex-1 items-center gap-2 rounded-xl border border-light_bronze-600 bg-card/90 px-3.5 py-2 text-sm text-muted-foreground shadow-warm backdrop-blur-md transition-all hover:border-light_bronze-400 hover:bg-card hover:shadow-warm-lg sm:flex sm:max-w-md"
        >
          <Search className="h-4 w-4 text-primary" />
          Search books, notes &amp; modules…
        </Link>

        <div className="ml-auto flex items-center gap-1.5">
          <Link href="/listings" className="btn-ghost px-3 sm:hidden" aria-label="Browse listings">
            <Search className="h-5 w-5" />
          </Link>

          {ready && authed ? (
            <>
              <Link href="/listings/new" className="btn-primary hidden h-10 px-4 sm:inline-flex">
                <Plus className="h-4 w-4" /> Sell
              </Link>

              <Link href="/dashboard?tab=buying" className="btn-ghost relative px-3" aria-label="Conversations">
                <MessageCircle className="h-5 w-5" />
                {unread > 0 && (
                  <span className="absolute right-1.5 top-1.5 flex h-2.5 w-2.5">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-destructive opacity-75" />
                    <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-destructive ring-2 ring-cornsilk" />
                  </span>
                )}
              </Link>

              <DropdownMenu>
                <DropdownMenuTrigger
                  className="rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                  aria-label="Account menu"
                >
                  <Avatar src={me?.avatar_url} name={me?.full_name} size={36} />
                </DropdownMenuTrigger>
                <DropdownMenuContent>
                  <DropdownMenuLabel>{me?.full_name || 'My account'}</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem asChild>
                    <Link href="/dashboard">
                      <LayoutDashboard className="h-4 w-4" /> Dashboard
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild className="sm:hidden">
                    <Link href="/listings/new">
                      <Plus className="h-4 w-4" /> Sell study material
                    </Link>
                  </DropdownMenuItem>
                  {me?.id && (
                    <DropdownMenuItem asChild>
                      <Link href={`/users/${me.id}`}>
                        <UserIcon className="h-4 w-4" /> Public profile
                      </Link>
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuItem asChild>
                    <Link href="/settings">
                      <Settings className="h-4 w-4" /> Settings
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onSelect={signOut} className="text-destructive focus:bg-[#f7e6e0] focus:text-[#8f3322]">
                    <LogOut className="h-4 w-4" /> Sign out
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </>
          ) : ready ? (
            <Link href="/login" className="btn-primary h-10 px-4">
              Continue with Google
            </Link>
          ) : (
            <div className="h-9 w-24 animate-pulse rounded-md bg-light_bronze-800/60" />
          )}
        </div>
      </div>
    </m.header>
  )
}

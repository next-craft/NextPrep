'use client'

/* ──────────────────────────────────────────────────────────────────────
   SiteShell — routes the global chrome.

   Most routes get the standard Navbar + Footer. Routes that ship their own
   full-bleed chrome (currently /login, which uses AuthNavbar over its aurora
   canvas) are rendered "bare" so the global navbar/footer don't double up.

   This keeps the global Navbar component itself untouched.
   ────────────────────────────────────────────────────────────────────── */

import { usePathname } from 'next/navigation'
import Navbar from '@/components/shared/navbar'
import Footer from '@/components/shared/footer'

// Routes that provide their own chrome and should not get the global one.
const BARE_ROUTES = ['/login']

export default function SiteShell({ children }) {
  const pathname = usePathname()
  const bare = BARE_ROUTES.includes(pathname)

  return (
    <>
      {!bare && <Navbar />}
      <main className="flex-1">{children}</main>
      {!bare && <Footer />}
    </>
  )
}

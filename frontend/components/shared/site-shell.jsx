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
import Atmosphere from '@/components/shared/atmosphere'

// Routes that provide their own chrome (e.g. /login ships AuthNavbar and its
// own copy of the shared Atmosphere). They still sit on the same background.
const BARE_ROUTES = ['/login']

export default function SiteShell({ children }) {
  const pathname = usePathname()
  const bare = BARE_ROUTES.includes(pathname)

  return (
    <>
      {!bare && <Atmosphere />}
      {!bare && <Navbar />}
      <main className="flex-1">{children}</main>
      {!bare && <Footer />}
    </>
  )
}

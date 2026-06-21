import { redirect } from 'next/navigation'
import { createServerSupabaseClient } from '@/lib/supabase/server'

// Private account area — keep out of search indexes.
export const metadata = {
  title: 'Dashboard',
  robots: { index: false, follow: false },
}

// Server-side auth gate (defense-in-depth alongside the API's JWT check): redirect
// signed-out visitors before any private content renders.
export default async function DashboardLayout({ children }) {
  const supabase = await createServerSupabaseClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')
  return children
}

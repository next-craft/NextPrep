import { redirect } from 'next/navigation'
import { createServerSupabaseClient } from '@/lib/supabase/server'

// Private account settings — keep out of search indexes.
export const metadata = {
  title: 'Settings',
  robots: { index: false, follow: false },
}

// Server-side auth gate (defense-in-depth alongside the API's JWT check).
export default async function SettingsLayout({ children }) {
  const supabase = await createServerSupabaseClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')
  return children
}

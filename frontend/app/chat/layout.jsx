import { redirect } from 'next/navigation'
import { createServerSupabaseClient } from '@/lib/supabase/server'

// Private conversations — keep out of search indexes.
export const metadata = {
  title: 'Messages',
  robots: { index: false, follow: false },
}

// Server-side auth gate (defense-in-depth alongside the API's JWT check).
export default async function ChatLayout({ children }) {
  const supabase = await createServerSupabaseClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')
  return children
}

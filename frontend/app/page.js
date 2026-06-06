import { createServerSupabaseClient } from '@/lib/supabase/server'
import { redirect } from 'next/navigation'

export default async function Home() {
  const supabase = await createServerSupabaseClient()
  const { data: { user } } = await supabase.auth.getUser()

  if (!user) redirect('/login')

  return (
    <div style={{ padding: '2rem' }}>
      <h1>Welcome to NextPrep</h1>
      <p>Logged in as: {user.email}</p>
    </div>
  )
}

import { createServerSupabaseClient } from '@/lib/supabase/server'
import { redirect } from 'next/navigation'
import CreateListingForm from '@/components/listings/CreateListingForm'

// Write-flow behind login — no SEO value, keep out of indexes.
export const metadata = {
  title: 'Sell study material',
  robots: { index: false, follow: false },
}

export default async function NewListingPage() {
  const supabase = await createServerSupabaseClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')
  return <CreateListingForm />
}

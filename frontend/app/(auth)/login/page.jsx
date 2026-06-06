'use client'
import { createClient } from '@/lib/supabase/client'

export default function LoginPage() {
  const supabase = createClient()

  const handleGoogleLogin = async () => {
    await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
      },
    })
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="flex flex-col items-center gap-6 p-8">
        <h1 className="text-2xl font-semibold">NextPrep</h1>
        <p className="text-muted-foreground text-sm">
          Buy and sell JEE, NEET, UPSC, and CA books — from students, for students.
        </p>
        <button
          onClick={handleGoogleLogin}
          className="flex items-center gap-2 rounded-md border px-4 py-2 text-sm font-medium hover:bg-accent"
        >
          Continue with Google
        </button>
      </div>
    </div>
  )
}

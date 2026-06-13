'use client'
import { useEffect, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { AnimatePresence } from 'framer-motion'
import { CreditCard, ExternalLink, CheckCircle2, Loader2, ShieldCheck } from 'lucide-react'
import api from '@/lib/api'
import { m, useReducedMotion, Reveal } from '@/components/shared/motion'
import { SPRING, EASE } from '@/lib/motion'

const STORAGE_KEY = 'razorpay_onboarding_account_id'

export default function SellerOnboardPage() {
  const [accountId, setAccountId] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    setAccountId(sessionStorage.getItem(STORAGE_KEY))
  }, [])

  const start = useMutation({
    // API: POST /payments/onboard — creates linked account, returns onboarding_url
    mutationFn: () => api.post('/payments/onboard').then((r) => r.data),
    onSuccess: (data) => {
      if (data.razorpay_account_id) {
        sessionStorage.setItem(STORAGE_KEY, data.razorpay_account_id)
        setAccountId(data.razorpay_account_id)
      }
      if (data.onboarding_url) {
        window.location.href = data.onboarding_url
      }
    },
    onError: (err) => setError(err.response?.data?.detail || 'Something went wrong. Please try again.'),
  })

  const complete = useMutation({
    // API: POST /payments/onboard/complete — verifies KYC, persists razorpay_account_id
    mutationFn: () =>
      api.post('/payments/onboard/complete', { razorpay_account_id: accountId }).then((r) => r.data),
    onSuccess: () => {
      sessionStorage.removeItem(STORAGE_KEY)
      window.location.href = '/listings/new'
    },
    onError: (err) =>
      setError(
        err.response?.data?.detail ||
          'We couldn’t confirm your KYC yet. If you just finished, give it a moment and try again.'
      ),
  })

  const step = accountId ? 2 : 1

  return (
    <div className="container max-w-xl py-10">
      <Reveal className="card p-8">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
            <CreditCard className="h-6 w-6" />
          </div>
          <div>
            <h1 className="font-display text-2xl font-semibold">Set up payouts</h1>
            <p className="text-sm text-muted-foreground">A one-time KYC with Razorpay.</p>
          </div>
        </div>

        <p className="mt-5 flex items-start gap-2 rounded-lg bg-secondary/60 p-4 text-sm text-secondary-foreground">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />
          Payments go <strong>directly</strong> to your linked account. NextPrep never holds your
          money or takes a cut.
        </p>

        {/* stepper */}
        <ol className="mt-6 space-y-3">
          <Step
            n={1}
            active={step === 1}
            done={step > 1}
            title="Connect your account"
            body="Start the Razorpay KYC. You’ll be redirected to complete verification."
          />
          <Step
            n={2}
            active={step === 2}
            done={false}
            title="Confirm KYC"
            body="Once Razorpay approves you, confirm here to start selling."
          />
        </ol>

        <AnimatePresence>
          {error && (
            <m.div
              initial={{ opacity: 0, height: 0, y: -4 }}
              animate={{ opacity: 1, height: 'auto', y: 0 }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.25, ease: EASE.warm }}
              className="overflow-hidden"
            >
              <div className="mt-5 rounded-lg border border-[#e4b3a6] bg-[#f7e6e0] px-4 py-3 text-sm font-medium text-[#8f3322]">
                {error}
              </div>
            </m.div>
          )}
        </AnimatePresence>

        <div className="mt-6">
          {step === 1 ? (
            <button onClick={() => start.mutate()} disabled={start.isPending} className="btn-primary w-full">
              {start.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> Starting…
                </>
              ) : (
                <>
                  <ExternalLink className="h-4 w-4" /> Connect payment account
                </>
              )}
            </button>
          ) : (
            <div className="space-y-3">
              <button onClick={() => complete.mutate()} disabled={complete.isPending} className="btn-primary w-full">
                {complete.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" /> Checking…
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="h-4 w-4" /> I&apos;ve completed KYC — confirm
                  </>
                )}
              </button>
              <button
                onClick={() => start.mutate()}
                disabled={start.isPending}
                className="btn-ghost w-full"
              >
                Resume KYC on Razorpay
              </button>
            </div>
          )}
        </div>
      </Reveal>
    </div>
  )
}

function Step({ n, active, done, title, body }) {
  const reduced = useReducedMotion()
  return (
    <li className="flex gap-3">
      <div className="relative">
        {active && !reduced && (
          <m.span
            className="absolute inset-0 rounded-full bg-light_bronze-700"
            animate={{ scale: [1, 1.45], opacity: [0.5, 0] }}
            transition={{ duration: 1.8, repeat: Infinity, ease: 'easeOut' }}
          />
        )}
        <div
          className={`relative flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${
            done
              ? 'bg-primary text-primary-foreground'
              : active
                ? 'bg-light_bronze-700 text-light_bronze-100'
                : 'bg-muted text-muted-foreground'
          }`}
        >
          <AnimatePresence mode="wait" initial={false}>
            {done ? (
              <m.span
                key="done"
                initial={reduced ? { opacity: 0 } : { scale: 0, rotate: -30 }}
                animate={{ scale: 1, rotate: 0, opacity: 1 }}
                transition={SPRING}
              >
                <CheckCircle2 className="h-4 w-4" />
              </m.span>
            ) : (
              <m.span key="num" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                {n}
              </m.span>
            )}
          </AnimatePresence>
        </div>
      </div>
      <div className={active || done ? '' : 'opacity-60'}>
        <p className="font-medium">{title}</p>
        <p className="text-sm text-muted-foreground">{body}</p>
      </div>
    </li>
  )
}

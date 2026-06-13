'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Store, MessageCircle, Receipt, CreditCard } from 'lucide-react'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { useMe } from '@/lib/queries'
import SellingTab from '@/components/dashboard/SellingTab'
import BuyingTab from '@/components/dashboard/BuyingTab'
import TransactionsTab from '@/components/dashboard/TransactionsTab'

const TABS = ['selling', 'buying', 'transactions']

export default function DashboardPage() {
  const { data: me } = useMe()
  const [tab, setTab] = useState('selling')

  // Read ?tab= on mount without useSearchParams (keeps the page out of a Suspense requirement).
  useEffect(() => {
    const t = new URLSearchParams(window.location.search).get('tab')
    if (TABS.includes(t)) setTab(t)
  }, [])

  return (
    <div className="container py-8">
      <h1 className="font-display text-2xl font-semibold sm:text-3xl">Dashboard</h1>

      {me && !me.razorpay_account_id && (
        <Link
          href="/sell/onboard"
          className="mt-4 flex items-center gap-3 rounded-lg border border-[#ecd6a0] bg-[#fbf1d6] p-4 text-sm text-[#8a5e12] transition-colors hover:bg-[#f8ead0]"
        >
          <CreditCard className="h-5 w-5 shrink-0" />
          <span>
            <strong>Complete payment setup to start selling.</strong> Connect your payout account →
          </span>
        </Link>
      )}

      <Tabs value={tab} onValueChange={setTab} className="mt-6">
        <TabsList className="w-full justify-start overflow-x-auto sm:w-auto">
          <TabsTrigger value="selling">
            <Store className="h-4 w-4" /> Selling
          </TabsTrigger>
          <TabsTrigger value="buying">
            <MessageCircle className="h-4 w-4" /> Messages
          </TabsTrigger>
          <TabsTrigger value="transactions">
            <Receipt className="h-4 w-4" /> Transactions
          </TabsTrigger>
        </TabsList>

        <TabsContent value="selling">
          <SellingTab meId={me?.id} />
        </TabsContent>
        <TabsContent value="buying">
          <BuyingTab meId={me?.id} />
        </TabsContent>
        <TabsContent value="transactions">
          <TransactionsTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}

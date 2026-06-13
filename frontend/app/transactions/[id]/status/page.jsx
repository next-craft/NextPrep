"use client";
import { use } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Loader2, CheckCircle2, XCircle, MapPin } from "lucide-react";
import api from "@/lib/api";
import { formatPrice } from "@/lib/utils";

export default function TransactionStatusPage({ params }) {
  const { id } = use(params);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["transaction-status", id],
    // API: GET /transactions/{id}/status — poll every 2s while initiated
    queryFn: () => api.get(`/transactions/${id}/status`).then((r) => r.data),
    refetchInterval: (query) =>
      query.state.data?.status === "initiated" ? 2000 : false,
    retry: false,
  });

  const Shell = ({ children }) => (
    <div className="container flex min-h-[calc(100vh-4rem)] items-center justify-center py-12">
      <div className="card w-full max-w-md animate-scale-in p-8 text-center">
        {children}
      </div>
    </div>
  );

  if (isError) {
    return (
      <Shell>
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-[#f7e6e0] text-[#8f3322]">
          <XCircle className="h-7 w-7" />
        </div>
        <h1 className="font-display text-xl font-semibold">
          Transaction not found
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          We couldn&apos;t load this transaction. It may not belong to your
          account.
        </p>
        <Link
          href="/dashboard?tab=transactions"
          className="btn-secondary mt-6 w-full"
        >
          Go to dashboard
        </Link>
      </Shell>
    );
  }

  if (data?.status === "released") {
    return (
      <Shell>
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-[#e9f0dd] text-[#3f6733]">
          <CheckCircle2 className="h-7 w-7" />
        </div>
        <h1 className="font-display text-2xl font-semibold">
          Payment confirmed{" "}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          You&apos;ve successfully paid
        </p>
        <p className="my-3 font-display text-3xl font-semibold">
          {formatPrice(data.amount_rupees)}
        </p>
        <p className="flex items-center justify-center gap-1.5 text-sm text-muted-foreground">
          <MapPin className="h-4 w-4" /> The seller has been notified — arrange
          pickup if you haven&apos;t already.
        </p>
        <Link
          href="/dashboard?tab=transactions"
          className="btn-primary mt-6 w-full"
        >
          View my purchases
        </Link>
      </Shell>
    );
  }

  if (data?.status === "cancelled") {
    return (
      <Shell>
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-[#fbf1d6] text-[#8a5e12]">
          <XCircle className="h-7 w-7" />
        </div>
        <h1 className="font-display text-xl font-semibold">
          Payment window expired
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          You have not been charged. You can return to the listing and try
          again.
        </p>
        <Link href="/listings" className="btn-primary mt-6 w-full">
          Browse listings
        </Link>
      </Shell>
    );
  }

  // initiated / loading → processing
  return (
    <Shell>
      <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
        <Loader2 className="h-7 w-7 animate-spin" />
      </div>
      <h1 className="font-display text-xl font-semibold">
        Payment processing…
      </h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Hang tight — we&apos;re confirming your payment. This page updates
        automatically.
      </p>
      {data?.amount_rupees != null && (
        <p className="mt-4 font-display text-2xl font-semibold">
          {formatPrice(data.amount_rupees)}
        </p>
      )}
      {isLoading && <span className="sr-only">Loading</span>}
    </Shell>
  );
}

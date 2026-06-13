"use client";
import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { animate } from "framer-motion";
import { Loader2, CheckCircle2, XCircle, MapPin } from "lucide-react";
import api from "@/lib/api";
import { formatPrice } from "@/lib/utils";
import { m, useReducedMotion } from "@/components/shared/motion";
import { EASE, SPRING, SPRING_SOFT } from "@/lib/motion";

/** Counts the rupee amount up from zero on mount (reduced motion → instant). */
function CountUpPrice({ amount, className }) {
  const reduced = useReducedMotion();
  const [val, setVal] = useState(reduced ? amount : 0);
  useEffect(() => {
    if (reduced) {
      setVal(amount);
      return;
    }
    const controls = animate(0, amount, {
      duration: 0.9,
      ease: EASE.warm,
      onUpdate: (v) => setVal(Math.round(v)),
    });
    return () => controls.stop();
  }, [amount, reduced]);
  return <span className={className}>{formatPrice(val)}</span>;
}

/** Engaging bronze waiting indicator — an orbiting dot around a softly
 *  pulsing core, instead of a plain spinner. */
function ProcessingLoader() {
  const reduced = useReducedMotion();
  if (reduced) {
    return (
      <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
        <Loader2 className="h-7 w-7" />
      </div>
    );
  }
  return (
    <div className="relative mx-auto mb-4 h-14 w-14">
      <span className="absolute inset-0 rounded-full border-2 border-secondary" />
      <m.div
        className="absolute inset-0"
        animate={{ rotate: 360 }}
        transition={{ duration: 1.2, repeat: Infinity, ease: "linear" }}
      >
        <span className="absolute left-1/2 top-0 h-2.5 w-2.5 -translate-x-1/2 rounded-full bg-primary" />
      </m.div>
      <m.span
        className="absolute inset-[32%] rounded-full bg-primary/20"
        animate={{ scale: [1, 1.35, 1], opacity: [0.6, 0.2, 0.6] }}
        transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
      />
    </div>
  );
}

export default function TransactionStatusPage({ params }) {
  const { id } = use(params);
  const reduced = useReducedMotion();

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
      <m.div
        initial={reduced ? { opacity: 0 } : { opacity: 0, scale: 0.94, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={SPRING_SOFT}
        className="card w-full max-w-md p-8 text-center"
      >
        {children}
      </m.div>
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
        <div className="relative mx-auto mb-4 flex h-14 w-14 items-center justify-center">
          {!reduced && (
            <m.span
              className="absolute inset-0 rounded-full bg-[#e9f0dd]"
              initial={{ scale: 0.6, opacity: 0.8 }}
              animate={{ scale: 1.7, opacity: 0 }}
              transition={{ duration: 0.9, ease: "easeOut" }}
            />
          )}
          <m.div
            className="relative flex h-14 w-14 items-center justify-center rounded-full bg-[#e9f0dd] text-[#3f6733]"
            initial={reduced ? { opacity: 0 } : { scale: 0, rotate: -25 }}
            animate={{ scale: 1, rotate: 0, opacity: 1 }}
            transition={SPRING}
          >
            <CheckCircle2 className="h-7 w-7" />
          </m.div>
        </div>
        <h1 className="font-display text-2xl font-semibold">Payment confirmed</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          You&apos;ve successfully paid
        </p>
        <CountUpPrice
          amount={data.amount_rupees}
          className="my-3 block font-display text-3xl font-semibold"
        />
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
      <ProcessingLoader />
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

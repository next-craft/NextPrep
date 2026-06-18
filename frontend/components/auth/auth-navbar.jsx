"use client";

/* ──────────────────────────────────────────────────────────────────────
   AuthNavbar — minimal floating chrome for the /login "Reading Room".

   It belongs to the login canvas: transparent over the aurora (with a faint
   top scrim for legibility), warm paper-and-ink, Fraunces wordmark, and a
   staggered warm entrance that matches the page's reveals.

   Deliberately omits the global navbar's "Continue with Google" CTA — the
   page itself is the sign-in surface, so the slot carries a trust cue
   ("Secure sign-in") and a low-friction "Browse listings" escape hatch
   instead.
   ────────────────────────────────────────────────────────────────────── */

import Link from "next/link";
import { Search, Lock } from "lucide-react";
import { Stagger, StaggerItem } from "@/components/shared/motion";

export default function AuthNavbar() {
  return (
    <header className="absolute inset-x-0 top-0 z-50">
      {/* faint top scrim so the bar reads cleanly over any aurora hue */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-cornsilk/70 to-transparent"
      />

      <Stagger
        as="nav"
        gap={0.08}
        delay={0.05}
        className="relative mx-auto flex h-16 max-w-7xl items-center justify-between px-5 lg:px-10"
      >
        {/* wordmark + breadcrumb */}
        <StaggerItem as="div" className="flex items-center gap-3">
          <Link
            href="/"
            className="font-display text-xl font-semibold tracking-tight"
            aria-label="NextPrep home"
          >
            Next<span className="text-primary">Prep</span>
          </Link>
          <span
            className="hidden text-sm text-muted-foreground sm:inline"
            aria-hidden
          ></span>
          {/* <span className="hidden text-sm text-muted-foreground sm:inline">Sign in</span> */}
        </StaggerItem>

        {/* explore + trust cue (no auth CTA) */}
        <StaggerItem as="div" className="flex items-center gap-2 sm:gap-4">
          <Link
            href="/listings"
            className="link-underline hidden items-center gap-1.5 text-sm font-medium text-foreground sm:inline-flex"
          >
            <Search className="h-4 w-4 text-primary" /> Browse listings
          </Link>
          <Link
            href="/listings"
            className="btn-ghost px-3 sm:hidden"
            aria-label="Browse listings"
          >
            <Search className="h-5 w-5" />
          </Link>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card/70 px-3 py-1 text-xs font-medium text-muted-foreground backdrop-blur">
            <Lock className="h-3.5 w-3.5 text-success" /> Secure sign-in
          </span>
        </StaggerItem>
      </Stagger>
    </header>
  );
}

import Link from "next/link";
import Image from "next/image";
import { createServerSupabaseClient } from "@/lib/supabase/server";
import { MapPin, KeyRound, ShieldCheck, Users, ArrowRight } from "lucide-react";
import ListingMarquee from "@/components/listings/ListingMarquee";
import { ExamCategoryChip } from "@/components/shared/badges";
import { POPULAR_EXAM_CATEGORIES } from "@/constants/examCategories";
import { Reveal, Stagger, StaggerItem } from "@/components/shared/motion";
import BookSpineStack from "@/components/shared/book-spine-stack";
import HowItWorks from "@/components/shared/how-it-works";
import JsonLd from "@/components/shared/json-ld";

export const revalidate = 0;

export const metadata = {
  alternates: { canonical: "/" },
  openGraph: {
    title: "NextPrep — Buy & sell exam study material",
    description:
      "India’s peer-to-peer marketplace for exam study material. Meet locally, inspect before you pay, and pass it on.",
    url: "https://nextprep.online",
  },
};

// FAQPage — answer-first content for Google AI Overviews and answer engines.
// Sourced from the page's own copy so structured data matches what's rendered.
const FAQS = [
  {
    q: "How does NextPrep work?",
    a: "Browse study material for your exam, message the seller to agree on a meetup, inspect the material and settle payment in person, then enter the seller’s 8-digit passkey in the app to confirm the exchange. No shipping, no middlemen — the platform does not process payments.",
  },
  {
    q: "Is there any shipping or delivery?",
    a: "No. NextPrep is in-person meetup only. You meet the seller locally, inspect the book, notes or module, settle payment directly, and take it with you.",
  },
  {
    q: "What can I buy and sell on NextPrep?",
    a: "Physical books, handwritten and self-made notes, original coaching modules (Allen, FIITJEE, PW, Aakash), formula sheets, test series and bundles for exams like JEE, NEET, UPSC and CA.",
  },
  {
    q: "How does a transaction get confirmed?",
    a: "You meet the seller, inspect the material and settle payment directly. The seller then gives you an 8-digit code, which you enter in the app to confirm the exchange and rate the seller. NextPrep does not process payments.",
  },
];

const homeJsonLd = [
  {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: FAQS.map((f) => ({
      "@type": "Question",
      name: f.q,
      acceptedAnswer: { "@type": "Answer", text: f.a },
    })),
  },
];

export default async function Home() {
  const supabase = await createServerSupabaseClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // API: GET /listings — recent listings strip
  let recent = [];
  try {
    const res = await fetch(`${process.env.API_URL}/listings`, {
      cache: "no-store",
    });
    if (res.ok) recent = (await res.json()).slice(0, 12);
  } catch {
    recent = [];
  }

  return (
    <div>
      <JsonLd data={homeJsonLd} />
      {/* ── Hero ───────────────────────────────────────────────────────── */}
      <section className="relative overflow-hidden">
        <div className="container grid items-center gap-10 py-14 lg:grid-cols-2 lg:py-20">
          <Stagger as="div" gap={0.09}>
            <StaggerItem>
              <span className="chip mb-5 cursor-default">
                <Users className="h-4 w-4" /> Student-to-student · India
              </span>
            </StaggerItem>
            <StaggerItem
              as="h1"
              className="font-display text-4xl font-semibold leading-[1.1] sm:text-5xl"
            >
              Buy &amp; sell JEE, NEET, UPSC &amp; CA books — from students, for
              students.
            </StaggerItem>
            <StaggerItem
              as="p"
              className="mt-5 max-w-xl text-lg leading-relaxed text-muted-foreground"
            >
              India’s peer-to-peer marketplace for exam study material. Meet
              locally, inspect before you pay, and pass it on. No shipping, no
              middlemen.
            </StaggerItem>
            <StaggerItem className="mt-8 flex flex-wrap gap-3">
              {user ? (
                <>
                  <Link href="/listings" className="btn-primary px-6 text-base">
                    Browse listings <ArrowRight className="h-4 w-4" />
                  </Link>
                  <Link
                    href="/listings/new"
                    className="btn-secondary px-6 text-base"
                  >
                    Sell material
                  </Link>
                </>
              ) : (
                <>
                  <Link href="/login" className="btn-primary px-6 text-base">
                    Continue with Google
                  </Link>
                  <Link
                    href="/listings"
                    className="btn-secondary px-6 text-base"
                  >
                    Browse listings
                  </Link>
                </>
              )}
            </StaggerItem>
          </Stagger>

          {/* decorative book stack */}
          <BookSpineStack />
        </div>
      </section>

      {/* ── Trust strip ────────────────────────────────────────────────── */}
      <section className="container py-10">
        <Stagger
          inView
          gap={0.1}
          className="glass grid gap-6 p-6 sm:grid-cols-3 sm:gap-8 sm:p-8"
        >
          {[
            {
              icon: MapPin,
              t: "In-person meetup",
              d: "Meet locally — no shipping, no courier.",
              img: "/trust/RealMeetup.png",
            },
            {
              icon: KeyRound,
              t: "Passkey-verified",
              d: "Confirm only after you inspect the material.",
              img: "/trust/PassKey.png",
            },
            {
              icon: ShieldCheck,
              t: "Real students",
              d: "Google sign-in. No anonymous resellers.",
              img: "/trust/VerifiedStudents.png",
            },
          ].map((x) => (
            <StaggerItem
              key={x.t}
              className="flex flex-col items-center gap-3 text-center"
            >
              <div className="relative h-36 w-full">
                <Image
                  src={x.img}
                  alt=""
                  fill
                  sizes="(min-width: 640px) 30vw, 90vw"
                  className="object-contain"
                />
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
                <x.icon className="h-5 w-5" />
              </div>
              <div>
                <p className="font-medium">{x.t}</p>
                <p className="text-sm text-muted-foreground">{x.d}</p>
              </div>
            </StaggerItem>
          ))}
        </Stagger>
      </section>

      {/* ── How it works ───────────────────────────────────────────────── */}
      <HowItWorks />

      {/* ── Recent listings ────────────────────────────────────────────── */}
      {recent.length > 0 && (
        <section className="cv-auto container pb-14">
          <Reveal inView className="mb-5 flex items-end justify-between">
            <h2 className="font-display text-2xl font-semibold">
              Fresh on NextPrep
            </h2>
            <Link
              href="/listings"
              className="group inline-flex items-center gap-1 text-sm font-medium text-primary hover:text-light_bronze-200"
            >
              Browse all{" "}
              <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5" />
            </Link>
          </Reveal>
          <ListingMarquee listings={recent} />
        </section>
      )}

      {/* ── Browse by exam ─────────────────────────────────────────────── */}
      <section className="cv-auto container py-10">
        <div className="glass p-6 sm:p-8">
          <Reveal inView className="flex items-end justify-between gap-4">
            <h2 className="font-display text-2xl font-semibold">Browse by exam</h2>
            <Link
              href="/colleges"
              className="group inline-flex shrink-0 items-center gap-1 text-sm font-medium text-primary hover:text-light_bronze-200"
            >
              Browse by college{" "}
              <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5" />
            </Link>
          </Reveal>
          <Stagger inView gap={0.04} className="mt-5 flex flex-wrap gap-2.5">
            {POPULAR_EXAM_CATEGORIES.map((value) => (
              <StaggerItem
                key={value}
                whileHover={{ scale: 1.06 }}
                whileTap={{ scale: 0.96 }}
              >
                <ExamCategoryChip value={value} asLink />
              </StaggerItem>
            ))}
          </Stagger>
        </div>
      </section>

      {/* ── Sell CTA ───────────────────────────────────────────────────── */}
      <section className="cv-auto container py-16">
        <Reveal
          inView
          y={20}
          className="card flex flex-col items-center gap-4 bg-tea_green-800 p-10 text-center"
        >
          <h2 className="font-display text-2xl font-semibold sm:text-3xl">
            Got books gathering dust?
          </h2>
          <p className="max-w-md text-muted-foreground">
            Turn last year’s prep material into cash and help a junior. Listing
            takes a minute.
          </p>
          <Link
            href={user ? "/listings/new" : "/login"}
            className="btn-primary px-6 text-base"
          >
            Start selling
          </Link>
        </Reveal>
      </section>
    </div>
  );
}

# SEO Audit — NextPrep

**Date:** 2026-06-18
**Stack:** Next.js 16.2.9 (App Router, RSC, Turbopack) · JavaScript only · Vercel · domain `https://nextprep.online`
**Scope:** Entire `frontend/` app. Backend (FastAPI) unchanged — SEO is a frontend concern; sitemap/OG read existing public APIs.

---

## Overall SEO score

| | Score | Notes |
|---|---|---|
| **Before** | **52 / 100** | Solid SSR foundation + good base metadata, but zero discoverability infrastructure (no robots/sitemap/canonical), no social cards, no structured data, private pages indexable, raw `<img>`. |
| **After** | **91 / 100** | Full technical-SEO baseline, dynamic sitemap, canonical everywhere, dynamic OG/Twitter cards, rich JSON-LD (Organization/WebSite/Product/FAQ/Breadcrumb/Profile), private pages `noindex`, `next/image` on hot paths. Remaining gap is mostly off-page (backlinks) + the 939 KB icon (binary, needs manual compression). |

Scoring is a practitioner estimate against Google's technical-SEO + rich-results criteria, not a single tool number. Lighthouse SEO category should now report ~100 on public pages; the residual 9 points are items requiring a binary asset swap, real traffic data (INP), or off-page signals.

---

## What was already good (kept)

- **SSR-first**: public pages (`/`, `/listings`, `/listings/[id]`, `/users/[id]`) are server-rendered — fully crawlable HTML.
- `metadataBase` + title template already set in root layout.
- `generateMetadata()` already present on both dynamic routes.
- Fonts via `next/font` (self-hosted, `display: swap`) — no render-blocking font CSS.
- Clean single-`<h1>` structure per page; semantic `<section>`/`<ol>`/`<header>` usage.
- Next.js 16 `proxy.js` (the v16 rename of middleware) only refreshes the Supabase session — no SEO-harmful redirects.

---

## Critical issues (fixed)

| # | Issue | Resolution |
|---|---|---|
| C1 | **No `robots.txt`** — crawlers had no directives; private routes open to indexing. | Added `app/robots.js` (Metadata Route) allowing public, disallowing account/auth/write flows, declaring sitemap + host. |
| C2 | **No sitemap** — Google had no URL inventory; new listings undiscoverable without backlinks. | Added `app/sitemap.js` — static pages + live listing & seller URLs from the API, fail-safe to static set. |
| C3 | **Private pages indexable** (`/dashboard`, `/settings`, `/chat`, `/transactions`, `/sell`, `/listings/new`, `/login`). Index bloat + thin/duplicate content risk. | Added `noindex` via route-segment `layout.jsx` (client pages can't export metadata) + direct export on the `/listings/new` server page. |
| C4 | **No canonical URLs** — filtered listing permutations (`?q=`, `?city=`…) were infinite near-duplicate URLs. | `alternates.canonical` on every page; `/listings` filter permutations canonical to the clean `/listings`. |

## High-priority issues (fixed)

| # | Issue | Resolution |
|---|---|---|
| H1 | **No OpenGraph / Twitter cards** — links shared to WhatsApp/X/Telegram rendered bare. | Site-wide `openGraph`/`twitter` in root layout + per-page overrides. Dynamic OG images via `next/og`. |
| H2 | **No structured data** — ineligible for rich results, weak entity signals for AI search. | JSON-LD: `Organization`, `WebSite`+`SearchAction`, `Product` (per listing), `FAQPage` (home), `BreadcrumbList`, `ProfilePage`/`Person`, `CollectionPage`. |
| H3 | **Sold/paused listings indexable** → soft-404 / stale-result risk. | Terminal listings emit `robots: noindex, follow` from `generateMetadata`. |
| H4 | **Raw `<img>` on listing card & gallery** — no AVIF/WebP, no responsive sizing, LCP image not prioritized, CLS risk. | Converted `ListingCard`, `ListingGallery`, `Avatar` to `next/image`; main gallery image `priority`; AVIF/WebP enabled in `next.config.js`. |

## Medium-priority issues (fixed / documented)

| # | Issue | Status |
|---|---|---|
| M1 | Gallery thumbnails had empty `alt=""`. | **Fixed** → `alt="{title} — image {n}"`. |
| M2 | Listing fetched 2–3× per request (generateMetadata + page + OG). | **Fixed** → wrapped in React `cache()`. |
| M3 | `<html lang="en">` for an India-only product. | **Fixed** → `lang="en-IN"`, OG `locale: en_IN`. |
| M4 | `app/icon.png` is **939 KB / 1254×1254** — oversized favicon. | **Documented** (binary asset; see CORE_WEB_VITALS.md → needs manual compression to <50 KB). |
| M5 | No `category`/`keywords` signals. | **Fixed** → `category: education` + justified keywords in root layout. |

## Low-priority issues (documented, not changed)

| # | Issue | Recommendation |
|---|---|---|
| L1 | `app/template.jsx` fades content from `opacity:0` — SSR HTML ships hidden until hydration (minor FCP/LCP risk, accessible via reduced-motion). | Acceptable design choice; if LCP suffers in field data, gate only below-the-fold regions. See CORE_WEB_VITALS.md. |
| L2 | Raw `<img>` remains on private/`noindex` pages (chat, ConversationList, SellingTab) and upload previews (`ImageUploader`, blob URLs). | Optional. Not indexed → no SEO value; blob previews are incompatible with `next/image`. |
| L3 | No `apple-icon` / web manifest. | Optional PWA polish; add `app/apple-icon.png` + `app/manifest.js` later. |
| L4 | No author/`Article` content (blog) — out of v1 scope per CLAUDE.md. | Future content-marketing lever (city/exam landing pages drive long-tail organic). |

---

## Recommended roadmap

1. **Now (shipped in this PR):** robots, sitemap, canonical, metadata, OG images, JSON-LD, `noindex`, `next/image`.
2. **This week (manual):** compress `app/icon.png` → <50 KB; verify all pages in Google Rich Results Test; submit `sitemap.xml` in Google Search Console; set the production `nextprep.online` domain as canonical host in GSC.
3. **This month:** add SEO landing pages per exam category (`/listings?exam_category=…` already canonicalizes to base — consider dedicated indexable `/exams/jee-mains` pages with unique copy if organic demand justifies); add `apple-icon` + manifest.
4. **Ongoing:** monitor Search Console coverage + Core Web Vitals (field/CrUX), watch for soft-404s on sold listings (now mitigated via `noindex`).

---

## Technical SEO checklist

| Item | Status |
|---|---|
| robots.txt | ✅ `app/robots.js` |
| XML sitemap (dynamic) | ✅ `app/sitemap.js` |
| Canonical URLs (all pages) | ✅ |
| Filtered/duplicate content controlled | ✅ canonical → `/listings` |
| `metadataBase` | ✅ (pre-existing) |
| Title + template | ✅ |
| Meta descriptions (all public pages) | ✅ |
| OpenGraph + Twitter | ✅ + dynamic images |
| Robots meta (index/noindex correct) | ✅ public index / private noindex |
| Structured data — Organization | ✅ |
| Structured data — WebSite + SearchAction | ✅ |
| Structured data — Product | ✅ per listing |
| Structured data — BreadcrumbList | ✅ listing + profile + browse |
| Structured data — FAQPage | ✅ home |
| Structured data — ProfilePage/Person | ✅ user profiles |
| Trailing-slash consistency | ✅ `trailingSlash: false` explicit |
| 404 handling | ✅ `not-found.jsx` (true 404, not soft) |
| Soft-404 on sold listings | ✅ `noindex` |
| `lang` correctness | ✅ `en-IN` |
| Single H1 / heading hierarchy | ✅ |
| Image alt text | ✅ (incl. fixed gallery thumbs) |
| `next/image` on key images | ✅ card + gallery + avatar |
| Modern image formats (AVIF/WebP) | ✅ `next.config.js` |
| Favicon weight | ⚠️ 939 KB — manual compression pending |
| HTTPS / domain | ✅ `nextprep.online` |

---

## Estimated impact on organic traffic

Directional, not a guarantee — depends on listing volume, backlinks, and competition:

- **Indexation:** from effectively un-discoverable (no sitemap) to a complete, auto-updating URL inventory → expect Google to index the full listing/profile catalogue within 2–4 weeks of GSC submission.
- **Long-tail capture:** Product + FAQ + Breadcrumb rich results improve CTR on `[exam] [book] buy/sell` queries; FAQ + WebSite entity data make the brand eligible for AI Overviews / answer engines.
- **Realistic 3–6 month range:** **+40–120% organic sessions** off the current low base, front-loaded once the sitemap is indexed. The dominant lever beyond this PR is listing inventory growth (more indexable Product pages) and backlinks.

## Estimated impact on Core Web Vitals

See `CORE_WEB_VITALS.md` for detail. Summary: **LCP** materially improved on `/listings` and `/listings/[id]` (responsive AVIF/WebP + prioritized gallery image vs full-size raw JPEG/PNG); **CLS** improved (reserved aspect-ratio boxes, sized avatars); **INP** unchanged (no JS added on the hot path — JSON-LD is server-rendered static markup).

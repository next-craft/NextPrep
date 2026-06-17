# SEO Changes — NextPrep

Every file created or modified in this SEO pass, with the exact change, the SEO mechanism, and expected outcome. All files are JavaScript (`.js`/`.jsx`) per the project's no-TypeScript rule. No backend or dependency changes (`next/og` ships with Next.js 16). Verified with a clean `npm run build` + runtime smoke test.

---

## New files

### `frontend/app/robots.js`
- **Change:** Metadata Route returning allow `/`; disallow `/dashboard`, `/settings`, `/chat/`, `/transactions/`, `/sell/`, `/listings/new`, `/login`, `/auth/`, `/api/`; declares `sitemap` + `host`.
- **Mechanism:** Gives crawlers explicit rules; keeps private/auth/write routes out of the crawl.
- **Outcome:** No crawl budget wasted on private pages; sitemap discoverable. Verified: `GET /robots.txt` returns correct directives.

### `frontend/app/sitemap.js`
- **Change:** Async sitemap — static routes (`/`, `/listings`, `/contact`, `/privacy`, `/terms`) + live `/listings/{id}` (with `lastModified` from `created_at`) and unique `/users/{id}` from the public `GET /listings` payload. `try/catch` → static-only fallback.
- **Mechanism:** Complete, auto-updating URL inventory for Google.
- **Outcome:** Full catalogue indexable without backlinks; never throws (broken sitemap avoided). Verified: `GET /sitemap.xml` returns valid XML.

### `frontend/app/opengraph-image.js` + `frontend/app/twitter-image.js`
- **Change:** `next/og` `ImageResponse` 1200×630 branded card (system fonts, no remote fetch). `twitter-image.js` re-exports it.
- **Mechanism:** Rich social previews on shares.
- **Outcome:** Branded card on WhatsApp/X/Telegram/LinkedIn. Verified: `GET /opengraph-image` → `image/png 200`.

### `frontend/app/(marketplace)/listings/[id]/opengraph-image.js`
- **Change:** Per-listing dynamic OG image — title, `formatPrice(asking_price)`, condition label, city, exam-category pill; falls back to a generic card on fetch failure.
- **Outcome:** Each shared listing renders a tailored card → higher share CTR.

### `frontend/components/shared/json-ld.jsx`
- **Change:** Reusable server component rendering `<script type="application/ld+json">`, escaping `<` to neutralize `</script>` injection.
- **Mechanism:** One safe, consistent structured-data primitive (zero client JS).
- **Outcome:** Used by home, listing, profile, and browse pages.

### Route `noindex` layouts (new `layout.jsx` each)
`app/dashboard`, `app/settings`, `app/chat`, `app/transactions`, `app/(marketplace)/sell`, `app/(auth)/login`.
- **Change:** Minimal server layout exporting `metadata` with a title + `robots: { index:false, follow:false }` (these pages are client components and cannot export metadata themselves).
- **Outcome:** Private pages emit `<meta name="robots" content="noindex, nofollow">`. Verified on `/login` and `/dashboard`.

---

## Modified files

### `frontend/app/layout.js`
- Added site-wide `openGraph`, `twitter`, `robots` (with `googleBot` `max-image-preview:large`, `max-snippet:-1`), `keywords`, `category`, `applicationName`, root `alternates.canonical`.
- `<html lang="en">` → **`en-IN`**.
- Injected site-wide JSON-LD: **`Organization`** + **`WebSite`** (with `SearchAction` → sitelinks search box).
- **Outcome:** Inherited social/robots defaults on every page; brand entity + search action for Google & AI engines.

### `frontend/next.config.js`
- Added `images.formats: ['image/avif','image/webp']`, `images.minimumCacheTTL` (31 days), explicit `trailingSlash: false`. Preserved existing `remotePatterns`.
- **Outcome:** Smaller modern images, long cache life, one canonical URL shape.

### `frontend/app/page.js` (home)
- Added `metadata` (canonical `/`, page OG) + **`FAQPage`** JSON-LD sourced from the on-page "How it works" content.
- **Outcome:** Home eligible for FAQ rich result / AI Overview answers.

### `frontend/app/(marketplace)/listings/page.jsx` (browse)
- Added canonical `/listings` (de-dupes all filter permutations) + page OG; **`CollectionPage`** + **`BreadcrumbList`** JSON-LD.
- **Outcome:** No duplicate-content bloat from filters; breadcrumb rich result.

### `frontend/app/(marketplace)/listings/[id]/page.jsx` (listing detail)
- `getListing` wrapped in React **`cache()`** (dedupes generateMetadata + page + OG fetches).
- `generateMetadata`: canonical, richer description, `openGraph`/`twitter`, **`noindex` for sold/paused** listings.
- Body: **`Product`** JSON-LD (`offers` price INR, `availability` In/SoldOut, `itemCondition` UsedCondition, `seller` Person, conditional `aggregateRating`) + **`BreadcrumbList`**.
- **Outcome:** Product rich results (price/availability), no soft-404s on terminal listings, fewer API calls.

### `frontend/app/(marketplace)/users/[id]/page.jsx` (profile)
- `getUser` wrapped in `cache()`; `generateMetadata` adds canonical + `profile` OG; body adds **`ProfilePage`**/**`Person`** + **`BreadcrumbList`** JSON-LD.
- **Outcome:** Indexable seller profiles with entity data; one fetch instead of two.

### `frontend/app/contact/page.jsx`, `privacy/page.jsx`, `terms/page.jsx`
- Added `alternates.canonical`.
- **Outcome:** Self-referencing canonicals on legal/info pages.

### `frontend/app/(marketplace)/listings/new/page.jsx`
- Added `metadata` with title + `noindex` (server page → direct export).
- **Outcome:** Write-flow excluded from index.

### `frontend/components/listings/ListingCard.jsx`
- Raw `<img>` → `next/image` with `fill` + `sizes="(max-width:640px) 50vw, (max-width:1024px) 33vw, 25vw"`; kept `alt={listing.title}`.
- **Outcome:** AVIF/WebP, responsive grid images, no CLS (aspect-ratio box).

### `frontend/components/listings/ListingGallery.jsx`
- Main `m.img` → `m.div` wrapping `next/image` `fill` (crossfade animation preserved), main image `priority`. Thumbnails → `next/image`; empty `alt=""` → `alt="{title} — image {n}"`.
- **Outcome:** Prioritized LCP image on detail page, accessible thumbnails, modern formats.

### `frontend/components/shared/avatar.jsx`
- `<img>` → `next/image` with explicit `width`/`height` (= `size`); kept `referrerPolicy` + initials fallback.
- **Outcome:** Reserved space (CLS), optimized Google avatar delivery.

---

## Not changed (intentional)

- **Backend** — untouched; sitemap/OG use existing public endpoints.
- **`app/template.jsx`** opacity fade — design choice; documented as minor FCP/LCP note.
- **`app/icon.png` (939 KB)** — binary; flagged for manual compression (can't regenerate a quality icon programmatically).
- **Raw `<img>` on chat / ConversationList / SellingTab / ImageUploader** — private (`noindex`) pages or blob-URL upload previews incompatible with `next/image`.

---

## Verification performed

- `npm run build` → compiled successfully; all new routes registered (`/robots.txt`, `/sitemap.xml`, `/opengraph-image`, `/twitter-image`, `/listings/[id]/opengraph-image`).
- Runtime smoke test (`npm start`): robots directives correct; sitemap valid XML; home page emits canonical + OG + JSON-LD (Organization, WebSite+SearchAction, FAQPage); `/login` & `/dashboard` emit `noindex, nofollow`; `/opengraph-image` returns `image/png 200`.
- **Pending (manual, needs running backend + browser):** Google Rich Results Test on a live listing/profile; Lighthouse before/after; GSC sitemap submission.

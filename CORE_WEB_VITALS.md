# Core Web Vitals & Bundle Report — NextPrep

**Stack:** Next.js 16.2.9 (App Router, RSC, Turbopack). Public pages are server-rendered. Field (CrUX) data isn't available pre-launch — findings below are lab/structural analysis plus the concrete changes shipped.

---

## LCP — Largest Contentful Paint

### Findings (before)
- **`/listings` & `/`**: listing-card images were raw `<img src={cloudinaryUrl}>` — served at original upload resolution, no AVIF/WebP, no responsive `srcset`. On a 4-col grid each thumbnail downloaded a full-size image → wasted bytes, slow LCP on mobile.
- **`/listings/[id]`**: the gallery main image (the LCP element) was a raw `m.img` with no priority hint → discovered late by the browser, lazy by default.
- **`app/icon.png`**: **939 KB at 1254×1254** — absurd for a favicon; competes for bandwidth early.
- Fonts already optimal (`next/font`, self-hosted, `display: swap`) — no change needed.

### Changes shipped
- `ListingCard`, `ListingGallery` main + thumbs, and `Avatar` → **`next/image`** with `fill`/explicit dimensions and correct `sizes`.
- Gallery main image marked **`priority`** → preloaded as the LCP candidate on the detail page.
- `next.config.js`: **`formats: ['image/avif','image/webp']`** (Next negotiates per `Accept`) + `minimumCacheTTL` 31 days.

### Expected effect
Listing thumbnails drop from full-resolution originals to right-sized AVIF/WebP (typically **60–80% fewer bytes** per image); the detail-page hero is prioritized rather than lazy. Material LCP improvement on `/listings` and `/listings/[id]`, especially on mobile/3G.

### Remaining (manual)
- **Compress `app/icon.png` to <50 KB** (e.g. 512×512 PNG/WebP via Squoosh/ImageOptim). Cannot be done programmatically here without degrading quality. High value, low effort.

---

## CLS — Cumulative Layout Shift

### Findings (before)
- Card/gallery `<img>` sat inside fixed `aspect-[4/3]` boxes (good), but raw `<img>` without intrinsic size can still flash/reflow before load.
- Avatar `<img>` relied on the parent span's inline `width/height` — acceptable but not self-describing.

### Changes shipped
- `next/image` with `fill` inside the existing `aspect-[4/3]` wrappers reserves exact space.
- Avatar `next/image` carries explicit `width`/`height` (= `size`) → space reserved before load.

### Expected effect
CLS near-zero on listing grids and detail/profile pages. No new web fonts (so no FOUT-driven shift). **CLS rating: good.**

---

## INP — Interaction to Next Paint

### Findings
- No JavaScript added to interactive paths. All structured data (`JsonLd`) is **server-rendered static markup** — zero hydration cost.
- Existing interactivity (filters, gallery thumb switching, chat polling) unchanged.
- `framer-motion` is the main client-JS dependency, but it's the deliberate motion system (used across hero, cards, gallery) and already gated behind a `MotionProvider` with `prefers-reduced-motion` support.

### Note (`app/template.jsx`)
The route `template.jsx` fades children from `opacity:0 → 1`. The SSR HTML therefore ships with the page **visually hidden until hydration** (content is present in the DOM for crawlers, and reduced-motion users get `opacity:1` immediately). This is a minor FCP/perceived-LCP risk, **not** an indexability risk (Google renders the hydrated page; raw HTML still contains the content). **Left as-is** (design choice). If field LCP regresses, scope the fade to below-the-fold regions only rather than wrapping the whole route.

### Expected effect
INP unchanged → **remains good**. No client-side SEO scripts were introduced.

---

## Bundle analysis

### Observed (from `next build`)
- Build compiles in ~3s (Turbopack); 16 routes; public pages dynamic (`ƒ`) due to Supabase session reads — expected and correct (they must be SSR for auth-aware rendering + fresh listing data).
- No new runtime dependencies added. `next/og` is part of Next.js core (used only in the OG image routes, which are isolated server routes — not in the page bundle).
- JSON-LD adds a few KB of static HTML per page, no JS.

### Largest weights / opportunities
| Item | Note | Action |
|---|---|---|
| `framer-motion` | Largest client dep; intentional motion system. | **Keep.** Already provider-gated + reduced-motion aware. If perf budget tightens later, consider `LazyMotion` + `m` (partial — `m` is already imported) to shrink the feature bundle. |
| `app/icon.png` 939 KB | Not a JS bundle item, but a heavy network asset. | **Compress to <50 KB** (manual). |
| Cloudinary originals | Were shipped full-size. | **Fixed** via `next/image` responsive `sizes` + AVIF/WebP. |
| Lucide icons | Tree-shakeable named imports already in use. | No action. |

### Code-splitting / RSC
- Server Components are used for all public content (home, listings, detail, profile) — minimal client JS by default. Client components (`'use client'`) are correctly scoped to interactive leaves (filters, gallery, chat, dashboard tabs).
- No dynamic-import opportunities worth the complexity at current size; revisit if any single client component grows large.

---

## Image offenders (ranked)

1. **`app/icon.png` — 939 KB / 1254×1254.** Worst single asset. Manual compression required.
2. **Cloudinary listing images (raw `<img>`)** — *fixed* via `next/image`.
3. **Gallery main image not prioritized** — *fixed* (`priority`).
4. Raw `<img>` on private/`noindex` pages (chat, ConversationList, SellingTab) and `ImageUploader` blob previews — low priority, not indexed / incompatible with `next/image`. Optional later cleanup.

---

## Summary

| Metric | Before | After (expected) |
|---|---|---|
| LCP | At risk (full-size raw images, lazy hero) | Good (responsive AVIF/WebP, prioritized hero) — pending icon compression |
| CLS | Minor risk | Good (reserved space everywhere) |
| INP | Good | Good (no JS added) |
| Bundle | Reasonable | Unchanged (no new deps; OG isolated) |

**Single highest-ROI follow-up:** compress `app/icon.png` to <50 KB.

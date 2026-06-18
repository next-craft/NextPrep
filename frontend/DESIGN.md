# NextPrep — Design System

A warm, **paper-and-ink** aesthetic: cornsilk paper backgrounds, deep-bronze ink,
soft earthy greens, and a confident editorial serif. Calm, tactile, trustworthy —
a secondhand bookshop meets a modern Indian student app. Mobile-first.

## Typography

Loaded via `next/font/google` in `app/layout.js`, exposed as CSS variables.

| Role | Font | Tailwind | CSS var |
|------|------|----------|---------|
| Display (headings, wordmark) | **Fraunces** (soft optical serif) | `font-display` | `--font-display` |
| Body / UI | **Hanken Grotesk** (humanist sans) | `font-sans` (default on `body`) | `--font-sans` |
| Mono (passkeys, codes) | **JetBrains Mono** | `font-mono` | `--font-mono` |

Headings (`h1–h4`) get `font-display` automatically (see `globals.css` base layer).

## Color

Two layers, both in `tailwind.config.js`:

1. **Brand palette** — five families with full `100–900` scales, used directly:
   `tea_green`, `beige`, `cornsilk`, `papaya_whip`, `light_bronze`. These are static
   hex, so opacity modifiers work (`bg-cornsilk/85`, `bg-light_bronze-800/70`).
2. **Semantic tokens** — CSS variables in `globals.css` `:root`, mapped to the
   palette. Use these for anything role-based; avoid opacity modifiers on them.

| Token | Value | Role |
|-------|-------|------|
| `background` | cornsilk `#fefae0` | page (warm paper) |
| `foreground` | light_bronze-100 `#32210f` | primary ink |
| `card` / `popover` | `#fffdf6` | surfaces |
| `primary` (+ `-foreground`) | light_bronze-300 `#96622e` | **CTAs**, sent chat bubbles |
| `secondary` | tea_green-700 `#e1e6cf` | supportive surfaces / buttons |
| `muted` (+ `-foreground`) | beige-700 / tea_green-200 | muted surfaces & text |
| `accent` | beige `#e9edc9` | hover surfaces |
| `destructive` | terracotta `#b3452f` | danger |
| `border` / `input` | `#e7d4bf` | warm dividers / field borders |
| `ring` | light_bronze-400 `#c58341` | focus ring |

**Status tints** (warm, AA-checked) live as inline classes in `components/shared/badges.jsx`
and `components/shared/status-pill.jsx`:
success `#eaf1de/#3f6733`, warning `#fbf1d6/#8a5e12`, danger `#f7e6e0/#8f3322`.

## Component utility classes (`globals.css` `@layer components`)

Existing markup uses these; they're real, polished utilities — keep using them:

- `.btn-primary` · `.btn-secondary` · `.btn-ghost` · `.btn-danger` — 44px tall, focus rings, active scale
- `.input` · `.textarea` · `.label` — form controls
- `.card` — bordered warm surface with `shadow-warm`
- `.badge` · `.chip` — pills (chip is the clickable variant)
- `.skeleton` — pulse placeholder

A subtle paper-grain overlay sits behind all content (`body::before`).

## Shared primitives (`components/shared/`)

`Navbar`, `Footer`, `Avatar` (initials fallback), `PriceBlock` (asking + struck-through
original + "X% off"), `PasskeyDisplay` (shown-once moment), `SegmentedPasskeyInput`
(8-digit), `EmptyState` / `ErrorState`, skeletons, and badges:
`ConditionBadge`, `ListingTypeBadge`, `ExamCategoryChip`, `ListingStatusBadge` (static
pill, server-safe).
`RateSeller` provides the buyer's post-exchange star rating + optional review.

`status-pill.jsx` (client) holds the **animated** status markers used in the dashboard and
chat — prefer these over `ListingStatusBadge` in client components:
- `StatusPill` — availability with motion that mirrors meaning: **Available** = soft-green
  pill with a breathing radar dot (live listing), **Sold** = terracotta pill with a check
  that stamps in, **Paused** = amber pill with a pause glyph. Mount pop + radar ping are
  gated on `useReducedMotion()`. Used in `ConversationList`, the chat header, and `SellingTab`.
- `VerifiedTag` — directional completed-transaction marker (`Purchased ↙` / `Sold ↗` +
  verified check), used in `TransactionsTab`.

Interactive primitives in `components/ui/` are Radix-backed (Shadcn-style):
`dialog`, `sheet`, `tabs`, `dropdown-menu`, `sonner` (toasts). **Don't hand-edit beyond styling.**
Form dropdowns are styled **native `<select>`** (best mobile UX); the subject field is a
native `<input list>` + `<datalist>` (free text + suggestions).

## Conventions

- Every price renders through `formatPrice(rupees)` (`lib/utils.js`) — never raw numbers.
- Never collect or display seller email/phone anywhere.
- Passkeys are shown once (`PasskeyDisplay`).
- `cn()` (`lib/utils.js`) merges classes; small display helpers there too
  (`conditionMeta`, `listingStatus`, `formatRelativeTime`, `initials`, `discountPercent`).

## Integration seams

Real calls are annotated `// API: <method path>`. Every screen is now wired to a real
backend endpoint — the former `lib/mocks/` stubs have been removed:

- **Selling tab** → `GET /listings/mine` (the seller's own listings, all states) via `useMyListings()`.
- **Public profile listings** → `GET /listings?seller_id={id}` (active only, SSR fetch).
- **Transactions tab** → `GET /transactions` (buyer + seller) via `useMyTransactions()`.
- **Conversation enrichment** (Buying tab, chat header) is composed client-side in
  `lib/queries.js` from real endpoints (listing + messages per conversation).
- **Image upload** uses the Cloudinary widget, env-gated on
  `NEXT_PUBLIC_CLOUDINARY_CLOUD_NAME` + `NEXT_PUBLIC_CLOUDINARY_UPLOAD_PRESET`,
  falling back to paste-URL when unset (`components/listings/ImageUploader.jsx`).

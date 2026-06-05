# Spec 01: Overview

## Purpose

This spec defines the complete product identity of Study Material Exchange India — what it is, who it is for, what it does, and where its hard boundaries lie. It exists as the canonical reference for every subsequent spec, ensuring no future feature contradicts the product's core model. The problem it solves: Indian students regularly sit on unused JEE/NEET/UPSC books and coaching modules that cost thousands of rupees; other students need those materials but cannot afford new copies. This platform connects them via a structured peer-to-peer in-person exchange — tighter than OLX (no spam, structured categories, verified meetup) but simpler than a full e-commerce product (no shipping, no escrow, no dispute arbitration).

## Depends on

No dependencies. This is the foundation all other specs build on.

## Scope

**In scope:**
- Product identity: name, tagline, core value proposition
- Who the buyers and sellers are (user personas)
- Allowed and disallowed content types
- Exchange model (in-person meetup only)
- Account model (one account, buyer + seller)
- Geographic and currency constraints (India, INR)
- Listing taxonomy: types, exam categories, conditions
- The unified search model
- Key user journeys at a high level
- What the product explicitly does NOT do in v1

**Out of scope:**
- Implementation details (covered in technical specs)
- UI wireframes or screen designs (covered in user-flows spec)
- Payment mechanics (covered in payment spec)
- Notification content (covered in notifications spec)
- Content moderation procedures (covered in content-policy spec)

## Product Identity

**Name:** NextPrep (working title — may change before launch)

**One-line description:** India's peer-to-peer marketplace for exam study material.

**Tagline:** *Buy and sell JEE, NEET, UPSC, and CA books and notes — from students, for students.*

**Core value proposition:**
- Sellers: recover money from study material they no longer need
- Buyers: get authentic, affordable material from real students

**What makes it different from OLX:**
1. Structured — exam category, subject, condition, and listing type are required metadata, not free text
2. Trusted meetup — passkey proves the buyer and seller actually met in person before money moves
3. Clean — only study material, no spam categories

## Who Uses It

**Sellers:** Students who have completed an exam cycle (finished JEE prep, cleared NEET, changed coaching institute) and have unused books, coaching modules, or notes. Also coaching institute alumni selling Allen/Aakash/FIITJEE modules.

**Buyers:** Students currently preparing for competitive exams who want affordable material. NEET droppers buying a second set of notes. Class 11 students buying Class 12 books in advance. CA Foundation students buying modules from someone who cleared it.

**Single account:** One user account serves both buyer and seller roles. No separate seller registration beyond Razorpay Route onboarding.

## Exchange Model

**In-person meetup only.** No shipping. No courier. No delivery tracking. No postal addresses collected.

The passkey mechanism enforces this:
1. Seller has an 8-digit passkey that they share with the buyer only at the in-person meetup
2. Buyer enters the passkey on the app to unlock payment
3. Payment is only triggered after the physical exchange is confirmed via passkey

This eliminates the need for a trust system around delivery — both parties are physically present.

**City field on listings is for proximity discovery only, not for a delivery system.** Buyers use it to find listings in their city.

## Account Model

- One account per user
- Google OAuth only — no email/password
- Same account for buying and selling
- Profile includes: full name, city, avatar (from Google), seller rating, total sales
- Email is available from Google OAuth — used for notifications, never displayed publicly
- No Aadhaar, no phone verification, no manual KYC in v1

`is_verified` on user profiles = Google OAuth email verified. Not Aadhaar. Not manual OTP.

## Geographic and Currency Constraints

- **Market:** India only
- **Language:** English only in v1
- **Currency:** INR rupees only
- **Prices:** Whole rupees, no paise. Minimum price: ₹1. No maximum enforced in v1.
- **City:** Required dropdown from a predefined list of major Indian cities. No geolocation API, no location permissions, and no city autocomplete in v1.

## Allowed Content

| Listing Type | Examples | Allowed |
|---|---|---|
| BOOK | HC Verma, NCERT, RD Sharma, Arihant, MTG | Yes |
| NOTES | Handwritten notes, self-created revision sheets, formula sheets | Yes |
| MODULE | Allen DLPs, Aakash modules, FIITJEE RSM, PW printed material, test series | Yes |
| BUNDLE | Mixed set of books + modules + notes sold together | Yes |

**Not allowed (content policy):**
- Pirated scans printed and sold as physical material
- Photocopied books sold in bulk (copyright infringement)
- Unauthorized PDF reproductions printed and bound
- Digital files of any kind (this is a physical goods marketplace)
- Non-study-material items of any kind

Full content policy is in `.claude/specs/product/content-policy.md`.

## Exam Categories

These are the canonical values used across listings, search filters, and DB:

```
JEE_MAINS       — JEE Mains preparation
JEE_ADVANCED    — JEE Advanced preparation
NEET_UG         — NEET UG medical entrance
NEET_PG         — NEET PG (medical postgraduate)
UPSC_CSE        — UPSC Civil Services
UPSC_OTHER      — Other UPSC exams (CAPF, CDS, etc.)
CA_FOUNDATION   — CA Foundation
CA_INTERMEDIATE — CA Intermediate (IPCC)
CA_FINAL        — CA Final
GATE            — GATE engineering
GMAT            — GMAT business school
GRE             — GRE graduate school
IELTS           — IELTS English proficiency
CUET            — CUET undergraduate entrance
CLASS_9         — Class 9 school material
CLASS_10        — Class 10 board material
CLASS_11        — Class 11 material
CLASS_12        — Class 12 board / entrance prep
OTHER           — Anything not in the above list
```

## Conditions

Condition grades are standardised so buyers know what to expect:

| Code | Label | Meaning |
|---|---|---|
| A | Like New | No markings, no wear. Looks unused. |
| B | Good | Light use. Minimal highlighting. All pages intact. |
| C | Acceptable | Heavy use. Significant highlighting. Fully readable. |

No condition lower than C is allowed. Torn or damaged material cannot be listed.

## Unified Search

All listing types appear in a single search stream. There are no separate sections for "Books", "Notes", and "Modules". A student searching "JEE Physics" sees books, notes, and modules together, sorted by recency.

**Available filters:**
- `q` — free text search across title and description
- `exam_category` — one of the canonical exam categories above
- `subject` — partial match (e.g. "Physics", "Organic Chemistry")
- `city` — exact city filter (e.g. "Delhi", "Pune")
- `condition` — A, B, or C
- `listing_type` — BOOK, NOTES, MODULE, or BUNDLE

Filters are additive (AND). No OR filter UI in v1.

## Key User Journeys (High Level)

**Selling:**
1. Sign in with Google
2. Complete Razorpay Route onboarding (one-time KYC) to enable payouts
3. Create listing: title, exam category, subject, type, condition, price, photos, city
4. Receive passkey on listing creation success screen — save it
5. Share passkey only at the in-person meetup with the buyer
6. Receive payment automatically once buyer enters passkey and pays

**Buying:**
1. Sign in with Google (or browse without signing in — listings are public)
2. Search or browse listings
3. Contact seller via in-app chat to arrange meetup
4. Meet in person, verify the material
5. Enter the passkey the seller gives at meetup
6. Get redirected to Razorpay — complete payment
7. Receive confirmation

Detailed step-by-step flows including edge cases are in `.claude/specs/product/user-flows.md`.

## What Does NOT Exist in v1

The following features are explicitly out of scope. Do not build them.

| Category | Out of scope |
|---|---|
| Exchange | Shipping, courier, delivery tracking, postal address collection |
| Auth | Email/password, phone OTP, Aadhaar verification |
| Accounts | Separate buyer/seller accounts, buyer ratings |
| Listings | Featured listings, sponsored placement, automated price suggestions |
| Payments | Platform fee (config exists, not charged), disputes, refund requests from UI |
| Moderation | Admin panel, automated content moderation, appeal flows |
| Search | Vector search, similarity search, saved searches, search history |
| Notifications | In-app notifications, push notifications, SMS |
| Tech | WebSockets, mobile app, multi-language, Celery, JWKS caching |
| Trust | Aadhaar linking, government ID verification, buyer ratings |

## Security Boundaries Relevant to Product

1. **Seller contact info is never exposed** — buyers must use in-app chat. Phone numbers and emails must not appear in listing text (manual moderation removes them).
2. **Passkey is never recoverable** — it is hashed on creation. Sellers can only regenerate, never retrieve the original.
3. **Session in httpOnly cookies** — users cannot access their session token from browser JavaScript.
4. **Payment is authoritative from webhook** — client callbacks never trigger DB updates. The buyer's UI is a status display only.

## Files to create

```
.claude/specs/product/01-overview.md     ← this file
```

## Files to modify

None. This is the first product spec.

## New dependencies

No new dependencies.

## Security considerations

- Seller contact info must never appear in any API response (CLAUDE.md rule 1). This is a product constraint, not just a technical one — listing description text must be moderated for embedded phone numbers and emails.
- Session stored in httpOnly cookies, never localStorage (CLAUDE.md rule 4). Product flows must not require the user to copy or paste their session token.
- Passkey plaintext is never persisted or logged (CLAUDE.md rule 10). Product success screens show it once; recovery path is regeneration only.

## Definition of done

- [ ] `.claude/specs/product/01-overview.md` exists and is committed to `spec/01-overview` branch
- [ ] All exam categories in this spec exactly match the canonical list in `CLAUDE.md` — no additions, no removals
- [ ] All listing types in this spec (BOOK, NOTES, MODULE, BUNDLE) match the `listing_type` CHECK constraint documented in `CLAUDE.md` and `SCHEMA.md`
- [ ] All condition codes (A, B, C) in this spec match the canonical list in `CLAUDE.md`
- [ ] All transaction statuses referenced (initiated, released, cancelled) match `CLAUDE.md`
- [ ] No feature listed as "out of scope" in `CLAUDE.md` appears in scope in this spec
- [ ] The exchange model (in-person only, no shipping) is stated explicitly
- [ ] The passkey model is described accurately: generated at listing creation, shown once, hashed in DB, share at meetup
- [ ] The unified search model is stated (one stream, listing_type is a filter not a section)
- [ ] The currency constraint (INR, whole rupees) is stated

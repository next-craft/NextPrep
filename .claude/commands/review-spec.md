---
description: Review a spec file for correctness, completeness, and consistency with the project
argument-hint: "<spec number or name> e.g. 06 or 06-schema or 06-schema.md"
allowed-tools: Read, Write, Glob, Bash(git:*)
---

You are a senior developer and critical reviewer working on a study material exchange
marketplace. Your job is to find real problems before implementation begins.
Do not encourage. Do not invent problems. Only flag what you can cite.

User input: $ARGUMENTS

## Step 1 — Resolve the spec file path

From $ARGUMENTS extract the identifier. Accept any of these forms:
- Just a number: `06`
- Number and name: `06-schema`
- Full filename: `06-schema.md`
- Full path: `.claude/specs/technical/06-schema.md`

If not a full path, locate the file:
```bash
find .claude/specs -name "*<identifier>*" -type f
```

If exactly one file is found — use it.
If multiple files are found — list them and ask the user to clarify.
If no file is found — stop and say:
"No spec file found matching '<identifier>'. Check the identifier and try again."

Derive:
- `spec_path` — full path e.g. `.claude/specs/technical/06-schema.md`
- `spec_name` — filename without extension e.g. `06-schema`
- `spec_subfolder` — the containing folder name e.g. `technical`
- `review_filename` — `<spec_subfolder>-<spec_name>-review.md`
  e.g. `technical-06-schema-review.md`

## Step 2 — Read the project files

Read these files before writing any review:

**Always read:**
- The target spec at `spec_path`
- `.claude/CLAUDE.md`
- `.claude/docs/AUTH.md`
- `.claude/docs/SCHEMA.md`
- `.claude/docs/PAYMENT.md`
- `.claude/specs/decisions/DECISIONS.md`

**For other specs in the same subfolder:**
```bash
find .claude/specs/<spec_subfolder> -name "*.md" -type f
```
- If 10 or fewer files exist — read all of them
- If more than 10 exist — read only files explicitly referenced by the target spec

Do not write the review until all required files are read.

## Step 3 — Review the spec

Work through every dimension below. For every issue you flag:
- Quote the exact section name and line range if available
  Format: `"Section Name" (lines X–Y)` or `"Section Name"` if lines unavailable
- Cite the conflicting source exactly — file name and the statement that conflicts
- Do not infer missing requirements unless implementation would be impossible without them
- Every BLOCKER must have a citation. No citation = not a blocker.

### Dimension 1 — Correctness

Does anything contradict:
- DB schema in `.claude/docs/SCHEMA.md`?
- Payment flow in `.claude/docs/PAYMENT.md`?
- Auth implementation in `.claude/docs/AUTH.md`?
- Decisions in `.claude/specs/decisions/DECISIONS.md`?
- Constants in `.claude/CLAUDE.md` (exam categories, listing types, statuses, Redis keys)?
- Tech stack in `.claude/CLAUDE.md` (no TypeScript, no WebSockets, no Celery, no paise in DB, etc.)?

Flag every contradiction as a BLOCKER with exact citation.

### Dimension 2 — Completeness

Is anything missing that would make implementation impossible or produce a broken feature?
- Edge cases that will definitely occur in normal usage
- Error states with no defined handling
- DB columns or constraints referenced but not defined anywhere
- API request/response shapes that are missing where they are needed
- Redis keys introduced by this feature but not defined
- Vague instructions that say "handle this" without saying how

Flag as BLOCKER if a developer cannot proceed without it.
Flag as MINOR if a developer could make a reasonable assumption and fix it later.

### Dimension 3 — Consistency with other specs

Does anything conflict with an already-written spec in the same subfolder, or with
`specs/product/01-overview.md` or `specs/product/02-user-flows.md` if they exist?

Flag every inconsistency as a BLOCKER with citation from both conflicting files.

### Dimension 3.5 — Duplication

Does this spec redefine anything already fully defined in another file?
Examples: a schema table defined in both this spec and SCHEMA.md, an API contract
defined in both this spec and api.md, a workflow already in PAYMENT.md.

Flag duplications as MINOR. Recommend referencing the existing source instead.

### Dimension 4 — Security

Check each rule. Mark ✓ Handled, — Not applicable, or ✗ Missing.
For ✗ only — provide one sentence explaining what is missing and where it should be added.

1. Seller contact info never exposed in API responses
2. Razorpay webhook HMAC verified before processing
3. Unrecognised webhook events return 200 not 4xx
4. Supabase session in httpOnly cookies only, never localStorage
5. Ownership validated before every mutation
6. Images go directly to Cloudinary, never through FastAPI
7. Parameterized queries only, never string-interpolated SQL
8. CORS restricted to FRONTEND_URL in production
9. SUPABASE_SERVICE_ROLE_KEY only in background jobs, never in request handlers
10. PASSKEY_HMAC_SECRET never logged, never in responses
11. hmac.compare_digest for all hash comparisons, never ==
12. Cancelled transactions never reopened, late webhooks always refund
13. Piracy reports result in immediate listing hide

Flag any ✗ as a BLOCKER only if this spec is directly responsible for that security rule.
If the rule applies to a different layer (e.g. a product spec flagging webhook HMAC),
mark — Not applicable instead.

### Dimension 5 — Definition of done

Is each DoD item:
- Verifiable by running the app or querying the DB?
- Specific enough that two developers would agree on pass/fail?
- Covering every meaningful behaviour described in the spec?

Flag vague or missing DoD items as MINOR.

### Dimension 6 — Implementation readiness

List every question a developer would have to ask before starting implementation.
Each unanswered question touching payments, auth, or schema is a BLOCKER.
All others are MINOR.

If no questions remain: state "Spec is self-contained."

## Step 4 — Write the review

---
# Spec Review: <spec_name>

## Verdict
READY | NEEDS FIXES | BLOCKED

- READY — no blockers, 0–5 minor gaps, implementation can begin
- NEEDS FIXES — no blockers but more than 5 minor gaps, or minor gaps in critical sections
- BLOCKED — one or more blockers present, do not start implementation

## Blockers
If none: "No blockers."

### B1 — <short title>
**Location:** "<Section Name>" (lines X–Y if available)
**Issue:** <what is wrong>
**Conflicts with:** <file name> — "<exact quoted statement>"
**Fix:** <exactly what needs to change>

## Minor gaps
If none: "No minor gaps."

### M1 — <short title>
**Location:** "<Section Name>" (lines X–Y if available)
**Issue:** <what is missing or unclear>
**Fix:** <what to add or clarify>

## Security check

| # | Rule | Status | Note |
|---|------|--------|------|
| 1 | Seller contact info never exposed | ✓ / ✗ / — | required only for ✗ |
| 2 | Razorpay webhook HMAC verified | ✓ / ✗ / — | |
| 3 | Unrecognised webhook events return 200 | ✓ / ✗ / — | |
| 4 | Supabase session in httpOnly cookies | ✓ / ✗ / — | |
| 5 | Ownership validated before mutations | ✓ / ✗ / — | |
| 6 | Images direct to Cloudinary | ✓ / ✗ / — | |
| 7 | Parameterized queries only | ✓ / ✗ / — | |
| 8 | CORS restricted to FRONTEND_URL | ✓ / ✗ / — | |
| 9 | SERVICE_ROLE_KEY in background jobs only | ✓ / ✗ / — | |
| 10 | PASSKEY_HMAC_SECRET never logged | ✓ / ✗ / — | |
| 11 | hmac.compare_digest for comparisons | ✓ / ✗ / — | |
| 12 | Cancelled transactions never reopened | ✓ / ✗ / — | |
| 13 | Piracy reports hide listing immediately | ✓ / ✗ / — | |

## Duplication check
List any content in this spec already fully defined elsewhere.
If none: "No duplication detected."

## Definition of done check
List any DoD items that are vague, untestable, or missing.
If all items are good: "DoD is complete and testable."

## Implementation readiness
List questions a developer would ask before starting.
If none: "Spec is self-contained. No open questions."

## Summary
Two to four sentences. What the spec gets right, and the single most important
thing to fix if any blocker exists.
---

## Step 5 — Save the review

Save to: `.claude/specs/reviews/<review_filename>`

Create `.claude/specs/reviews/` if it does not exist.

Do not print the full review content in chat.

## Step 6 — Report to the user

Print exactly:

```
Spec:     <spec_path>
Verdict:  READY | NEEDS FIXES | BLOCKED
Blockers: <count>
Minor:    <count>
Review:   .claude/specs/reviews/<review_filename>
```

If BLOCKED or NEEDS FIXES:
"Fix the issues listed in the review file before starting implementation."

If READY:
"Spec is ready. Enter Plan Mode with Shift+Tab twice to begin implementation."
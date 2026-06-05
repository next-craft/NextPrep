---
description: Plan and implement a spec — shows plan first, waits for approval, then writes code
argument-hint: "<step-number> e.g. 06, 06-schema, 06-schema.md"
allowed-tools: Read, Write, Glob, Bash(git:*), Bash(find:*), Bash(cat:*)
---

You are a senior developer implementing a feature for a study material exchange marketplace.
Always follow `.claude/CLAUDE.md`.

User input: $ARGUMENTS

---

# PHASE 1 — PLAN

---

## Step 1 — Verify repository state

Run:
```bash
git status --porcelain
```

If any modified, staged, or untracked files exist, stop and say:
"Working directory is not clean. Commit, stash, or discard changes before planning implementation."

DO NOT CONTINUE until the working directory is clean.

## Step 2 — Resolve the spec file

Accept any of these forms:
- `06`
- `06-schema`
- `06-schema.md`
- `.claude/specs/technical/06-schema.md`

If not a full path:
```bash
find .claude/specs -name "*<identifier>*" -type f
```

- 0 matches → stop: "No spec file found matching '<identifier>'."
- 1 match → use it
- 2+ matches → list them and ask the user to clarify

Derive:
- `spec_path` — e.g. `.claude/specs/technical/06-schema.md`
- `spec_name` — e.g. `06-schema`
- `spec_subfolder` — e.g. `technical`
- `feature_slug` — e.g. `schema`
- `branch_name` — `impl/<spec_name>` e.g. `impl/06-schema`

## Step 3 — Check review status

```bash
find .claude/specs/reviews -name "*<spec_name>*" -type f
```

If a review file exists, read it and check the verdict:
- `BLOCKED` → stop: "Spec is marked BLOCKED in review. Fix all blockers before implementing."
- `NEEDS FIXES` → continue, but include all unresolved issues in the plan under Risks
- `READY` → continue normally
- No review file → continue normally

## Step 4 — Read required context

**Always read:**
- `spec_path`
- `.claude/CLAUDE.md`

**Read only if relevant to this spec:**
- `.claude/docs/AUTH.md` — if spec touches auth, JWT, users, or protected routes
- `.claude/docs/SCHEMA.md` — if spec touches DB tables, columns, or migrations
- `.claude/docs/PAYMENT.md` — if spec touches payments, passkey, transactions, or webhooks
- `.claude/specs/decisions/DECISIONS.md` — if spec makes or references architectural choices

**Read specs listed in "Depends on" section of the target spec — always.**

**Read additional specs only when they share:**
- same DB tables
- same endpoints
- same Redis keys
- same workflow steps

Do not read specs that are unrelated to this feature.

## Step 5 — Verify implementability

Before producing the plan, check every item below.
If any check fails — stop and report the exact problem. Do not invent a solution.

1. Every referenced DB table exists in SCHEMA.md or is created by a dependency spec
2. Every referenced column exists in SCHEMA.md or is created by a dependency spec
3. Every referenced endpoint exists in a router or is defined in this spec
4. Every referenced Redis key is documented in CLAUDE.md
5. Every referenced environment variable is defined in CLAUDE.md
6. Every referenced package is in the approved stack in CLAUDE.md
7. Nothing contradicts CLAUDE.md, AUTH.md, SCHEMA.md, PAYMENT.md, or DECISIONS.md
8. Nothing in scope appears in "What NOT to build in v1" in CLAUDE.md

## Step 6 — Produce the implementation plan

Output the plan in this exact format. Do not write any code yet.

---
# Implementation Plan: <spec_name>

## Overview
One paragraph. What this feature does, what it touches, and why it is being built now.

## Files to create
- `<path>` — <purpose>

## Files to modify
- `<path>` — <what changes>

## Database changes
None
OR
Migration required:
- Table: <name> — <what changes>
- Index: <name> — <why>
- Constraint: <name> — <why>

Never modify existing migration files.

## API changes
Routes added:
- `METHOD /path` — <description>

Routes modified:
- `METHOD /path` — <what changes>

## Frontend changes
- Pages: <list>
- Components: <list>
- Queries/mutations: <list>

## Backend changes
- Routers: <list>
- Services: <list>
- Models: <list>
- Jobs: <list>

## New dependencies
None
OR
- `<package>` — <reason>

## Security considerations
List every security rule from CLAUDE.md that applies to this feature:
- Rule N: <how it is enforced in this implementation>

## Implementation order
1. <first thing to build and why>
2. <second>
3. ...

## Risks
- <anything that could go wrong or was flagged in review>

## Open questions
List anything unclear that could affect implementation.
If none: "No open questions."
---

## Step 7 — Wait for approval

After printing the plan, say exactly:

"Plan complete. Reply **yes** to begin implementation or **no** to cancel."

Stop. Do not write any code. Do not create any branches. Do not modify any files.
Wait for the user's reply before proceeding.

---

# PHASE 2 — EXECUTE (only after user replies yes)

---

## Step 8 — Create implementation branch

```bash
git branch -a
```

If `branch_name` already exists, append a counter: `impl/06-schema-01`, etc.

```bash
git checkout main
git pull origin main
git checkout -b <branch_name>
```

## Step 9 — Implement

Follow the spec and the approved plan exactly.
Implement everything in "Files to create" and "Files to modify".
Do not implement anything outside the approved plan's scope.

**Enforce every code rule from CLAUDE.md:**
- JavaScript only on frontend — `.js` and `.jsx`, no TypeScript
- `logging.getLogger(__name__)` at top of every new Python module
- No `print()` in Python. No `console.log()` in JavaScript.
- All DB operations async — no sync SQLAlchemy in FastAPI routes
- Parameterized queries only — never f-string or string-concatenated SQL
- Business logic in `services/` — routers handle HTTP only
- Prices in whole rupees — `amount_rupees * 100` only at Razorpay API boundary
- `user["sub"]` for user UUID from JWT — never use email as identifier
- `hmac.compare_digest` for all hash comparisons — never `==`
- `formatPrice(rupees)` in JSX — never raw price values in templates
- TanStack Query for all client server-state — no `useState` + `useEffect` for fetching
- Pydantic v2 for all schemas — `model_config = ConfigDict(from_attributes=True)`

**Enforce every security rule from CLAUDE.md:**
- Never expose seller contact info in any API response
- Always verify Razorpay webhook HMAC before processing
- Return 200 for unrecognised webhook events — never 4xx
- Validate ownership before every mutation: `listing.seller_id == user["sub"]`
- SUPABASE_SERVICE_ROLE_KEY only in background jobs, never in request handlers
- PASSKEY_HMAC_SECRET never logged, never in API responses
- Parameterized queries only — never string-interpolate user input
- CORS restricted to FRONTEND_URL in production — never `*`
- Supabase session in httpOnly cookies — never localStorage
- Images go directly to Cloudinary — never through FastAPI
- Cancelled transactions never reopened — late webhooks always refund
- Hide listing immediately on piracy/copyright report

If something necessary is missing from the spec, implement the minimal version
and note it in the Step 10 report under assumptions.

## Step 10 — Report to the user

Print exactly:

```
Branch:         <branch_name>
Spec:           <spec_path>
Files created:  <count>
Files modified: <count>
```

List every file:
```
Created:
  - <full path>

Modified:
  - <full path>
```

If anything required an assumption:
```
Assumptions made:
  - <what you assumed and why>
```

Then say:
"Implementation complete. Review the changes, then commit and merge <branch_name> into main."

Do not commit. Do not push. Do not ask the user to commit.
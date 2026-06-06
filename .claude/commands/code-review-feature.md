---
description: Runs parallel security and quality code review for a specific SMEI feature. Pass the spec name as argument e.g. /code-review-feature 07-auth
allowed-tools: Bash(git diff), Bash(git diff --staged)
---

Run the full code review pipeline for the feature
specified in $ARGUMENTS.

If no argument is provided, stop immediately and say:
"Please provide a spec name. Usage: /code-review-feature
<spec-name> e.g. /code-review-feature 07-auth"

If `.claude/specs/$ARGUMENTS.md` does not exist, stop
immediately and say:
"Spec file not found at .claude/specs/$ARGUMENTS.md.
Please check the spec name and try again."

---

## Pre-flight Check

Before invoking any subagents, collect the diff:
- Run `git diff` for unstaged changes
- Run `git diff --staged` for staged changes
- Combine both into a single diff

If both are empty, stop immediately and say:
"No changes detected. Implement the feature before
running code review."

---

## Step 1: Parallel Review

Invoke both subagents simultaneously with the same
context. Do NOT wait for one to finish before starting
the other.

**smei-security-reviewer** receives:
- The combined diff from the pre-flight check
- Spec file for context: `.claude/specs/$ARGUMENTS.md`
- Supporting docs: `.claude/docs/AUTH.md`,
  `.claude/docs/PAYMENT.md`, `.claude/docs/SCHEMA.md`,
  `.claude/CLAUDE.md`
- Source files to reference: `backend/routers/`,
  `backend/models/`, `backend/services/`, `backend/main.py`
- Instruction: Review only the changed code for security
  vulnerabilities. Do not comment on quality or style.
  Pay special attention to the SMEI security contracts
  listed below.

**smei-quality-reviewer** receives:
- The combined diff from the pre-flight check
- Spec file for context: `.claude/specs/$ARGUMENTS.md`
- Supporting docs: `.claude/docs/AUTH.md`,
  `.claude/docs/PAYMENT.md`, `.claude/docs/SCHEMA.md`,
  `.claude/CLAUDE.md`
- Source files to reference: `backend/routers/`,
  `backend/models/`, `backend/services/`, `backend/main.py`
- Instruction: Review only the changed code for quality,
  FastAPI best practices, and maintainability. Do not
  comment on security concerns.

---

## SMEI Security Contracts (for smei-security-reviewer)

Flag any violation of these as **Critical**:

| Contract | What to check |
|----------|--------------|
| Passkey never stored plaintext | No passkey value written to DB or logs |
| `hmac.compare_digest` always | No `==` comparison on passkey values |
| Max 3 passkey attempts | Redis key `passkey_attempts:{listing_id}:{buyer_id}` checked before each attempt |
| Attempt key is per-buyer-per-listing | No global attempt counter |
| `verify_token` uses JWKS/ES256 | No custom JWT logic, no HS256, no skipped verification |
| `payload["sub"]` = user UUID | No other field used for user identity |
| Paise only at `payment_link.create()` | No `amount * 100` anywhere else |
| Prices whole rupees in DB | No fractional rupee stored |
| Late webhook → always refund | Cancelled transaction never reopened |
| Transaction statuses only `initiated/released/cancelled` | No other status string written |
| Search parameterized only | No ILIKE built with string concatenation or f-strings |
| `UNIQUE(transaction_id, rated_by)` enforced | No upsert that bypasses this |
| Buy Now = zero DB writes | No DB insert/update on Buy Now action |
| Seller email cooldown enforced | Redis key `abandoned_notified:{listing_id}` checked before sending |

---

## Step 2: Unified Report

Once both subagents have completed, combine their
findings into a single unified report. De-duplicate
overlapping findings — if both agents flagged the same
line for different reasons, merge into one finding with
both perspectives noted.

Structure the report as:

```
## Code Review Report — $ARGUMENTS

### Security Findings
[smei-security-reviewer output]

### Quality Findings
[smei-quality-reviewer output]

### Combined Action Plan
Ordered checklist of everything that needs to be fixed,
prioritized by severity:

1. [Critical contract violations first — must fix]
2. [High security findings second — must fix]
3. [Quality CHANGES REQUESTED third — must fix]
4. [Medium/Low security findings fourth]
5. [Quality APPROVED WITH SUGGESTIONS last]

### Overall Verdict
One of:
- ✅ APPROVED — ready to commit
- ⚠️ APPROVED WITH SUGGESTIONS — can commit, address suggestions in a follow-up
- ❌ CHANGES REQUESTED — must fix before committing, see action plan above
```

---

## Step 3: Ask for Approval

After presenting the unified report, ask:
"Do you want me to implement the action plan now?"

Wait for explicit user confirmation before making any
changes. Do not touch any files until the user approves.

---

## Rules

- Do NOT edit any files before user approval
- Do NOT start one reviewer before the other — both
  must run in parallel
- Do NOT skip the pre-flight diff check
- Do NOT present a partial review as complete if either
  subagent fails or returns no output — report the
  failure and stop
- Any Critical contract violation in the security report
  automatically sets the Overall Verdict to
  ❌ CHANGES REQUESTED, regardless of quality findings
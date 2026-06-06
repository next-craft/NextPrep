---
description: Writes and runs tests for a specific Study Material Exchange feature. Pass the spec number and name as argument e.g. /test-feature 07-auth
allowed-tools: Bash(python -m pytest)
---

Run the full testing pipeline for the feature specified
in $ARGUMENTS.

If no argument is provided, stop immediately and say:
"Please provide a spec name. Usage: /test-feature
<spec-name> e.g. /test-feature 07-auth"

If `.claude/specs/$ARGUMENTS.md` does not exist, stop
immediately and say:
"Spec file not found at .claude/specs/$ARGUMENTS.md.
Please check the spec name and try again."

---

## Step 1: Write Tests

Invoke the **smei-test-writer** subagent with the
following context:

- Spec file to base tests on:
  `.claude/specs/$ARGUMENTS.md`
- Supporting docs to read for contracts and rules:
  - `.claude/docs/AUTH.md`
  - `.claude/docs/PAYMENT.md`
  - `.claude/docs/SCHEMA.md`
  - `.claude/CLAUDE.md`
- Source files to read for structure:
  - `backend/main.py`
  - `backend/routers/` directory
  - `backend/models/` directory
  - `backend/services/` directory
- Output test file to create:
  `backend/tests/test_$ARGUMENTS.py`
- Instruction: Write tests based on what the spec says
  the feature SHOULD do. Do NOT derive test logic from
  reading the implementation. Cover:
  - Happy paths
  - Edge cases
  - Auth guards (Supabase JWKS/ES256, `payload["sub"]` as UUID)
  - Passkey validation (8-digit numeric, HMAC_SHA256,
    max 3 attempts via Redis key
    `passkey_attempts:{listing_id}:{buyer_id}`, TTL 7 days,
    `hmac.compare_digest` always)
  - Payment boundary conditions (paise conversion only at
    `razorpay_client.payment_link.create()`, 15-min expiry,
    late webhooks always refund)
  - Transaction status transitions (`initiated → released |
    cancelled` only — never disputed/confirmed/paid/pending)
  - Redis rate limits (100 msg/hr for chat)
  - DB constraint violations (`is_available`/`sold_at` CHECK,
    listing type CHECK `IN ('BOOK','NOTES','MODULE','BUNDLE')`,
    `UNIQUE(transaction_id, rated_by)`)
  - Price integrity (whole rupees in DB, never fractional)

Wait for smei-test-writer to fully complete and confirm
the test file has been written before proceeding to Step 2.

---

## Step 2: Run Tests

Once smei-test-writer has finished, invoke the
**smei-test-runner** subagent with the following context:

- Test file to execute:
  `backend/tests/test_$ARGUMENTS.py`
- Spec file for context:
  `.claude/specs/$ARGUMENTS.md`
- Source files to analyze against when diagnosing failures:
  - `backend/main.py`
  - `backend/routers/` directory
  - `backend/models/` directory
  - `backend/services/` directory
- Run command:
  `python -m pytest backend/tests/test_$ARGUMENTS.py -v`
- Instruction: Run ONLY the specified test file. Do NOT
  run the full test suite. Analyze any failures by
  cross-referencing the test code, the spec, and the
  source files. Classify each failure as one of:
  - **Bug** — implementation exists but behaves incorrectly
  - **Missing feature** — code path not yet implemented
  - **Contract violation** — breaks a rule in CLAUDE.md or
    AUTH.md/PAYMENT.md/SCHEMA.md (e.g. wrong status name,
    plaintext passkey, fractional rupee stored)

---

## Handoff Rules

- Do NOT start Step 2 until Step 1 is fully complete
- Do NOT attempt to fix any code regardless of what the
  test results show
- Do NOT run any tests beyond
  `backend/tests/test_$ARGUMENTS.py`
- If smei-test-writer reports it could not write the test
  file, stop and report the reason — do NOT proceed to Step 2
- Never mock `hmac.compare_digest` to always return True
- Never assert a transaction status outside
  `{initiated, released, cancelled}`

---

## Final Output

After both subagents complete, produce a combined summary:

### Testing Pipeline Report — $ARGUMENTS

**Step 1 — Tests Written**
- List each test written with a one-line description of
  which spec requirement it validates

**Step 2 — Test Results**
- Mirror the smei-test-runner's structured report

**Verdict**
One of:
- ✅ Ready for code review — all tests pass
- ❌ Needs fixes — list the failing tests, their root
  causes, and whether each is a Bug, Missing Feature,
  or Contract Violation
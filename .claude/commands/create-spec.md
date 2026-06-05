---
description: Create a spec file and feature branch for the next step
argument-hint: "<step-number> <spec-name> <description> e.g. 01 user-flows Every user journey step by step"
allowed-tools: Read, Write, Glob, Bash(git:*)
---

You are a senior developer working on a study material exchange marketplace.
Always follow the rules in `.claude/CLAUDE.md`.

User input: $ARGUMENTS

## Step 1 — Check working directory is clean

Run `git status`. If any uncommitted, unstaged, or untracked files exist,
stop immediately and tell the user:

"Working directory is not clean. Please commit or stash your changes before
creating a new spec branch."

DO NOT CONTINUE until the working directory is clean.

## Step 2 — Parse arguments

From $ARGUMENTS extract:

1. `step_number` — first token, zero-padded to 2 digits: 1 → 01, 3 → 03, 12 → 12

2. `spec_name` — second token, the raw name: e.g. `user-flows`, `payment`, `chat`

3. `description` — everything after the second token, used as the Purpose paragraph seed
   e.g. "Every user journey step by step: browse, list, chat, buy, sell"

4. `feature_title` — human readable Title Case derived from spec_name:
   e.g. "User Flows", "Payment", "Chat", "Image Upload"

5. `feature_slug` — lowercase kebab-case, only a-z 0-9 and -, max 40 chars
   e.g. `user-flows`, `payment`, `image-upload`

6. `branch_name` — format: `spec/<step_number>-<feature_slug>`
   e.g. `spec/02-user-flows`, `spec/07-chat`

7. `subfolder` — infer from spec_name:
   - `overview`, `user-flows`, `content-policy`, `notifications` → `product`
   - `auth`, `schema`, `payment`, `chat`, `search`, `image-upload`, `passkey`, `api` → `technical`
   - `environments`, `deployment`, `logging`, `jobs` → `infrastructure`
   - `log` → `decisions`

8. `output_path` — `.claude/specs/<subfolder>/<step_number>-<feature_slug>.md`

If you cannot infer all of the above from $ARGUMENTS, ask the user to clarify
before proceeding.

## Step 3 — Check branch is not already taken

Run `git branch -a`. If `branch_name` already exists, append a counter:
`spec/02-user-flows-01`, `spec/02-user-flows-02`, etc.

## Step 4 — Switch to main and pull latest

```bash
git checkout main
git pull origin main
```

## Step 5 — Create and switch to the feature branch

```bash
git checkout -b <branch_name>
```

## Step 6 — Read the project before writing anything

Read all of these before writing a single line of the spec:

- `.claude/CLAUDE.md` — stack, conventions, constants, security rules
- `.claude/docs/AUTH.md` — auth implementation, verify_token, Supabase setup
- `.claude/docs/SCHEMA.md` — full DB schema, constraints, search implementation
- `.claude/docs/PAYMENT.md` — complete payment workflow, webhook handler, jobs
- `.claude/specs/decisions/DECISIONS.md` — all architectural decisions and reasons
- All existing files in `.claude/specs/<subfolder>/` — avoid duplicating what exists

Do not write the spec until you have read all of these.
Everything in the spec must be grounded in what you read — do not invent decisions,
do not contradict existing decisions, do not introduce technology not in the stack.

## Step 7 — Write the spec

Generate the spec document with this exact structure.
Write in full detail. No placeholders. No "TBD". No "see other file" without
quoting the relevant content inline.

Use `description` from the parsed arguments as the starting point for the
Purpose section — expand it into a full paragraph grounded in the project context.

---
# Spec <step_number>: <feature_title>

## Purpose
One paragraph. Start from `description`, expand with project-specific context.
What this spec covers, why it exists, and what problem it solves.

## Depends on
Which previous specs or components must exist before this can be implemented.
If none: state "No dependencies."

## Scope
What is in scope for this spec. What is explicitly out of scope.

## <Section — as many as needed for the topic>
Full detail. Code blocks for all code, SQL, config, and shell commands.
For technical specs: include actual implementation code, not pseudocode.
For product specs: include actual user-facing copy, flows, and edge cases.

## Files to create
Every new file. Full path from project root.

## Files to modify
Every existing file that changes. Full path and what changes.

## New dependencies
Any new packages (pip or npm). If none: state "No new dependencies."

## Security considerations
Any security rules from CLAUDE.md that apply to this feature specifically.
If none apply beyond the standard rules: state "Standard security rules apply."

## Definition of done
A specific, testable checklist. Every item must be verifiable by running the app
or inspecting the DB. No vague items.
- [ ] item
- [ ] item
---

## Step 8 — Save the spec

Save to: `.claude/specs/<subfolder>/<step_number>-<feature_slug>.md`

Do not print the full spec content in chat.

## Step 9 — Report to the user

Print exactly this format:

```
Branch:    <branch_name>
Spec file: .claude/specs/<subfolder>/<step_number>-<feature_slug>.md
Title:     <feature_title>
Desc:      <description>
```

Then say:
"Review the spec at `.claude/specs/<subfolder>/<step_number>-<feature_slug>.md`,
then enter Plan Mode with Shift+Tab twice to begin implementation."
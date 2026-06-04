---
name: run-refactor
description: Refactoring suite, execution phase. Executes a refactoring round by dispatching subagents in git worktrees against each sequenced fix-prompt, under the worker constitution. Per fix it runs a fast related-tests check, a Tier-2 pre-commit reviewing agent against the staged diff, then an atomic per-fix commit, and produces a structured result manifest per module. Verification is handled by verify-refactor. Use to execute a planned refactoring round.
---

# Run refactor

**Scope:** Codebase-neutral template. Per-project values come from `refactoring-overrides.md`.

Executes a refactoring round by dispatching subagents against each fix-prompt. Produces structured results per
module. Verification is handled by `verify-refactor`.

## Project overrides

Before reading the procedure, look up the active project's overrides at `<overrides-root>/refactoring-overrides.md`.
For every `<!-- OVERRIDE: KEY -->` marker, substitute the value from the overrides file; if absent, use the inline
default (the defaults below are a Node/TypeScript example). The key schema is in `references/overrides-template.md`.

The overrides also document **module knobs** (custom test paths per module, drift signals, special-case rules) and
**sub-agent dispatch limits** (wave size, worktree path). Read those alongside the procedure; the module-agent
dispatch in Step 4 reads from them.

## Prerequisites

- `<!-- OVERRIDE: IDENTITY.REFACTOR_DOCS_ROOT -->Docs/refactoring/<!-- /OVERRIDE -->features-list.md` exists and is current.
- A round directory exists with fix-prompts (e.g. `<!-- OVERRIDE: IDENTITY.REFACTOR_DOCS_ROOT -->Docs/refactoring/<!-- /OVERRIDE -->round-N/`).
- The round's master prompt exists (`round-N-prompt.md`).
- Baselines captured (`<!-- OVERRIDE: IDENTITY.REFACTOR_DOCS_ROOT -->Docs/refactoring/<!-- /OVERRIDE -->baselines/`).
- (Recommended) `preflight/findings.md` and `preflight/<module>/draft-fix-prompt.md` from `create-refactor-plan` Step 4.

## Procedure

### 1. Read the round prompt

Find the latest round directory and read `round-N-prompt.md` for the execution sequence.

### 2. Read features-list.md

Identify which modules have `fix-prompt.md` ready. Check the dependency graph for execution order and
parallelization groups. If `preflight/platform/draft-fix-prompt.md` exists from Step 4d, it dispatches as Wave 0
before any per-module wave (see Step 3).

### 3. Build the execution plan from the dependency graph

Group modules into waves:

- **Wave 0 (if applicable):** the cross-cutting platform fix-prompt. Single agent. Merges to main before any other
  wave dispatches. Required when downstream modules depend on the cross-cutting fix (helper-level validation,
  shared middleware, etc.).
- **Wave 1:** modules with no upstream dependencies (foundations: auth, CSRF, rate limiting).
- **Wave 2:** modules whose Wave 1 dependencies are satisfied.
- **Wave N:** continue until all modules assigned.

Within each wave, modules that do not share files can run in parallel. Check the "Touches" column in
features-list.md; modules touching the same file must be sequential (or split across waves).

**Wave-size cap:** parallel agents per wave is bounded by the project's concurrency budget. Default 6. Override via
`<!-- OVERRIDE: DISPATCH.WAVE_SIZE -->6<!-- /OVERRIDE -->`. Beyond ~6 simultaneous long-running worktree agents you
trade wall-clock for rate-limit retries.

### 4. Execute each wave

For each wave, process modules in severity-score order (highest first).

**Sequential execution (for modules sharing files or with dependencies):**

Read the fix-prompt.md. Execute every fix in order. After each fix:

```bash
<!-- OVERRIDE: COMMANDS.TEST -->npm run test:run<!-- /OVERRIDE -->          # Must pass before next fix
```

For module-scoped fast feedback, prefer the per-module test path from the overrides `Module knobs` table; it is a
faster signal than the full suite per fix.

**Even faster: use a related-tests selector.** After a per-fix file change, run only the tests that import the
changed files:

```bash
<!-- OVERRIDE: COMMANDS.TEST_RELATED -->npx vitest run --related<!-- /OVERRIDE --> <changed-file-1> <changed-file-2>
```

Typical wall-clock: a few seconds versus the full suite. The dispatch contract for parallel subagents (below)
mandates this for the per-fix loop; the full suite runs at module-end. If your test runner has no related-tests
selector, fall back to the module fast-test path.

#### Pre-commit reviewing agent (Tier 2)

Before each per-fix commit, the dispatch agent invokes a Tier-2 reviewing agent against the staged diff. The
reviewing agent does NOT execute or modify; it produces a structured verdict.

```
Reviewing agent prompt:

You are reviewing a diff for a refactoring fix. The fix is described in <fix-prompt-block>.
The staged diff is <git diff --cached output>.

Check for these failure modes (output: pass | fail per item):

1. Hallucinated content: any added line references a file path, function, type, or import that doesn't exist in the repo
2. Removed-but-still-used: any deleted line removes a symbol still referenced elsewhere (grep for the symbol name)
3. Dead imports: imports added but not referenced in the new code
4. Left-behind debug: debug prints, breakpoints, TODO/FIXME with no follow-up
5. Missing test update: a source change without a corresponding test change when the fix-prompt suggests test impact
6. Schema-migration mismatch: a schema change without `Schema migration: yes` in the fix-prompt, or vice versa
7. Out-of-scope: changes outside the file paths declared in the fix-prompt
8. Imports vs declarations: import order, missing imports for newly-used types

Output format (parsed by the dispatch agent):

REVIEW_START
verdict: approve | request_changes | reject
issues:
  - <issue-1>: <one-line description + file:line>
  - <issue-2>: ...
suggestions:
  - <optional improvement, one per line>
REVIEW_END

approve: dispatch agent commits.
request_changes: dispatch agent rewrites the fix addressing the issues, re-runs review.
reject: dispatch agent marks the fix `failed` and proceeds; the failed fix's diff is preserved as
        <batch>/failed-<fix-id>.diff for human review.

After 2 request_changes cycles on the same fix, escalate to reject. Don't loop indefinitely.
```

The reviewing agent runs in the same worktree (read-only). It reads the fix-prompt + diff + does grep-style
checks. Roughly 10-30s per fix at Tier-2 speed.

**Why this exists.** Tier-3 execution agents occasionally produce commits with subtle issues: removing code that
is still imported elsewhere, hallucinating file paths in moved-from references, leaving debug statements,
schema-migration drift between the fix-prompt declaration and the actual diff. Tests passing does not catch these.
A second-pass agent reading the diff specifically for failure-mode patterns catches them before commit.
Historically, roughly 1-3 such issues per round had to be caught manually post-merge; pre-commit review
eliminates that class.

**When to skip.** For fixes with `Confidence: high` (preflight-drafted, adopted verbatim) AND `Blast radius:
local`, the reviewing agent can be skipped to save time/cost. Override via
`<!-- OVERRIDE: REVIEW.SKIP_HIGH_CONFIDENCE_LOCAL -->false<!-- /OVERRIDE -->` (default false: review everything).
Do not skip for cross-module / platform / schema fixes regardless of confidence.

After all fixes in a module, fill in the **Result manifest** in the fix-prompt.md:

```markdown
## Execution result

| Fix | Status | Files modified | Tests | Schema migration | Commit |
|-----|--------|---------------|-------|------------------|--------|
| Fix 1 | applied | src/lib/<module>/<file>, ... | +0/-0 | no | abc123 |
| Fix 2 | applied | <schema-file>, src/services/... | +2/-0 | yes - <table>.<column> | def456 |
```

The `Schema migration` column is required: it surfaces in the Step 9 close-checklist. For applied fixes with a
schema migration, also record `schema_change_applied_to_prod: pending-deploy` and ensure the migration command
lands in the round-close checklist.

**Parallel subagents (for independent modules in the same wave):**

Dispatch subagents in worktrees. The worktree location defaults to `.worktrees/round-N/<module>/` (gitignored);
override via `<!-- OVERRIDE: DISPATCH.WORKTREE_PATH -->.worktrees/round-N/<!-- /OVERRIDE -->`.

Each subagent prompt must include:

```
You are dispatched in a git worktree at <worktree-path>/<module>/ on branch refactor/round-N/<module>.

Required reading before editing any file:
- references/worker-constitution.md (per-fix discipline: AI failure modes, false DRY, ownership,
  type/error/async/security/a11y/i18n/observability preservation, candidate template, post-fix sanity check,
  stop conditions). This is mandatory, not optional.

Inputs:
- preflight/<module>/draft-fix-prompt.md (atomized fixes from preflight, with confidence levels)
- <module>/review.md + <module>/fix-prompt.md (the LLM-validated, finalized prompts)
- preflight/findings.md sliced to your module
- Module knobs from the project's refactoring-overrides.md (custom test path, drift signals, gotchas)

Execute all fixes in fix-prompt.md in order. After each fix, run the module's fast test path (from Module knobs)
and the full suite if any test could be cross-module impacted.

After completing ALL fixes, produce a structured result in this exact format:

RESULT_START
module: [name]
status: [complete|partial|failed]
fixes_applied: [N]
fixes_skipped: [N]
fixes_failed: [N]
fixes_deferred: [N]                   # use the deferred ledger if you defer; never silently skip
files_modified: [comma-separated list]
tests_added: [N]
tests_modified: [N]
tests_passing: [yes|no]
schema_migrations: [list of "table.column" or "none"]
commit_range: [first-hash..last-hash or "uncommitted"]
regressions_introduced: [list or "none"]
regressions_resolved_in_module: [list or "none"]
RESULT_END

Rules:
- If any fix fails, continue with remaining fixes. Do not stop on first failure.
- If tests fail after a fix, attempt the rollback steps from that fix's "Rollback" section.
- If a fix's preconditions don't match the code (file/line drifted since the fix-prompt), mark it deferred with
  reason "drift" and write a deferred-ledger entry. Do not silently skip.
- All commits must be atomic per-fix. Don't bundle two fixes into one commit; the close orchestrator needs
  per-fix granularity for rollback.
- Before editing each fix, output the worker-constitution "Refactor candidate" pre-edit template. After committing
  each fix, run the worker-constitution post-fix sanity check. Stop conditions override "continue with remaining
  fixes": if any stop condition trips, defer the fix with a reason and proceed.
```

Parse the structured result from each subagent and aggregate into the round results.

### 5. Rollback protocol

If a fix causes test failures:

1. **Check the fix-prompt.md rollback section** for that fix; it has a `Verify:` field (a runnable command). Run it
   to confirm rollback success.
2. If it has data-migration steps, follow the reversal procedure.
3. If there is no specific rollback, `git revert <commit>` for the failing fix only.
4. Re-run the rollback's `Verify:` command to confirm.
5. Log the failed fix in the module's result manifest as "reverted."
6. Continue with remaining fixes; a single failure should not block the entire module.

For schema-touching rollbacks, the rule from the project overrides applies. Default for destructive schema
changes: the project's point-in-time-recovery procedure within the recovery window. Default for additive changes:
leave the column. Project-specific rollback paths are in the overrides Schema-migration section.

### 6. Update features-list.md

After each module completes, update its row: status to "Done (round-N)", score recalculated from remaining
(deferred) findings, finding counts showing resolved versus remaining, commit range for traceability, and a
schema-migrations column listing any column/table/index changes (or "none"; feeds the close-checklist).

### 7. Run verify-refactor

After all modules in the wave complete, run `verify-refactor` to diff against baselines and produce the
verification report.

For frontend / UI overhaul waves, dispatch a separate UI V&V verifier before marking the wave complete. It is
read-only and writes into the verification report: it re-runs the configured token-drift / state-scan / visual
smoke commands, inspects screenshots/traces against accepted handovers for changed routes, confirms loading,
empty, error, retry, permission-denied, stale-data, long-content, and mobile/responsive states, flags
design-token / control-plane bypass and duplicated primitives, and classifies each issue as regression,
pre-existing gap, or not-configured. This verifier does not apply fixes; it creates follow-up findings or blocks
the wave if a regression was introduced.

### 8. Write the completion report

Write `<!-- OVERRIDE: IDENTITY.REFACTOR_DOCS_ROOT -->Docs/refactoring/<!-- /OVERRIDE -->round-N/completion-report.md`:

```markdown
# Round N - Completion report

**Date:** YYYY-MM-DD
**Modules processed:** N
**Total fixes applied:** X
**Total fixes deferred:** Y (see deferred.md ledger)
**Total fixes reverted:** Z
**Tests added:** W
**Schema migrations applied (code):** [list of column/table changes]
**Schema migrations applied to prod:** [list with timestamps; should equal the above after the Step 10 close-checklist runs]

## Per-module results

| Module | Score before | Score after | Fixes | Tests | Status | Schema |
|--------|-------------|-------------|-------|-------|--------|--------|
| <module> | 7.5 | 2.0 | 16/19 applied | +24 | Done | none |

## Wave 0 (cross-cutting platform fix), if applicable
[Brief description of the platform fix and what downstream modules inherited from it]

## Regressions introduced and resolved
[List any test failures introduced and how they were resolved]

## Deferred to next round
[Reference deferred.md ledger; copy current-round-deferred rows for reader convenience]

## Baseline comparison
[Output from verify-refactor]

## Score hardening handoff
[If the user asked to raise readability/extensibility/auditability/security scores, either execute a
score-hardening pass next or write round-(N+1)-score-hardening-prompt.md. Include current score estimates,
top evidence-backed gaps, and whether the pass was executed, deferred, or not requested.]

## Round close checklist status
[Run create-refactor-plan Step 10 to: write round-N/snapshot.md, append round-deferred rows to deferred.md,
tear down worktrees, append a column to score-trajectory.md. Confirm each is done. Schema-touching deploy gates
in close-checklist.md must be ticked before the round is considered shipped.]
```

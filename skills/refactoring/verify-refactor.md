---
name: verify-refactor
description: Refactoring suite, verification phase. Diffs current state against captured baselines to prove a refactoring round introduced no regressions. Re-runs tests/lint/typecheck/schema, distinguishes newly-failing from pre-existing failures, auto-bisects any regression to the introducing commit, runs the API-surface diff, and enforces the schema-migration deploy gate. Produces a structured PASS / WARN / FAIL verification report. Run after run-refactor or any significant code changes.
---

# Verify refactor

**Scope:** Codebase-neutral template. Per-project values come from `refactoring-overrides.md`.

Diffs current state against baselines to verify a refactoring round introduced no regressions. Produces a
structured verification report. Run after `run-refactor`, or after any significant code change.

## Project overrides

Reads `<overrides-root>/refactoring-overrides.md`. Substitutes `<!-- OVERRIDE: KEY -->` markers; if absent, uses
the inline default (a Node/TypeScript example). The key schema is in `references/overrides-template.md`.

Project-specific custom scanners (for example a doc-count or doc-link checker, or any `scripts/check-*` listed
under the overrides `Preflight tools > Additional project-specific scanners`) ALSO run as part of verification.
They were captured pre-round in baselines (create-refactor-plan Step 7); we re-run them here and diff.

## Prerequisites

- `<!-- OVERRIDE: IDENTITY.REFACTOR_DOCS_ROOT -->Docs/refactoring/<!-- /OVERRIDE -->baselines/` exists with at least `test-results.txt`.
- The codebase is in a testable state (`<!-- OVERRIDE: COMMANDS.TEST -->npm run test:run<!-- /OVERRIDE -->` works).

## Regression-avoidance protocol

Before the procedure, read `references/regression-avoidance.md` for the canonical regression-class-to-detection
map. This skill implements checkpoint 4 (round close: full regression validation). Checkpoints 1-3 are elsewhere:

| Checkpoint | Implementation |
|---|---|
| 1. Pre-dispatch baseline freshness | `create-refactor-plan` Step 7 + dry-run gate |
| 2. Per-fix pre-commit verification | `run-refactor` parallel subagent dispatch (related-tests + Tier-2 reviewing agent) |
| 3. Per-wave cross-fix regression sweep | `run-refactor` Step 4 wave merge protocol |
| 4. Round close full regression validation | THIS SKILL |

The procedure below executes checkpoint 4. If checkpoints 1-3 were skipped or compromised, this skill's report can
say PASS while the round was actually higher-risk than measured. Trust the layered approach.

## Procedure

### 1. Capture current state

Run all verification commands and capture output:

```bash
<!-- OVERRIDE: COMMANDS.TEST -->npm run test:run<!-- /OVERRIDE --> 2>&1 | tee /tmp/refactor-verify-tests.txt
<!-- OVERRIDE: COMMANDS.LINT -->npm run lint<!-- /OVERRIDE --> 2>&1 | tee /tmp/refactor-verify-lint.txt
<!-- OVERRIDE: COMMANDS.SCHEMA_VALIDATE -->(echo "no schema validate configured")<!-- /OVERRIDE --> 2>&1 | tee /tmp/refactor-verify-schema.txt
<!-- OVERRIDE: COMMANDS.TYPECHECK -->npx tsc --noEmit<!-- /OVERRIDE --> 2>&1 | tee /tmp/refactor-verify-tsc.txt
```

Run any project-specific scanners declared in the overrides `Additional project-specific scanners` section.
Capture each to `/tmp/refactor-verify-<scanner>.txt`.

For architecture / consolidation rounds, re-run the project-specific control-plane scan declared in overrides:

```bash
<!-- OVERRIDE: CONTROL_PLANE.SCAN -->(echo "no control-plane scanner configured")<!-- /OVERRIDE --> 2>&1 | tee /tmp/refactor-verify-control-plane.txt
```

For frontend / UI overhaul rounds, also re-run the project-specific UI V&V commands declared in overrides:

```bash
<!-- OVERRIDE: UI.TOKEN_DRIFT -->(echo "no UI token-drift scanner configured")<!-- /OVERRIDE --> 2>&1 | tee /tmp/refactor-verify-ui-token-drift.txt
<!-- OVERRIDE: UI.STATE_SCAN -->(echo "no UI state scanner configured")<!-- /OVERRIDE --> 2>&1 | tee /tmp/refactor-verify-ui-state-scan.txt
<!-- OVERRIDE: UI.VV_SMOKE -->(echo "no UI smoke command configured")<!-- /OVERRIDE --> 2>&1 | tee /tmp/refactor-verify-ui-vv-smoke.txt
```

If a UI / control-plane command is not configured, record that as "not configured" in the report. Do NOT convert
"not configured" into PASS.

If characterization tests exist, run the project's characterization-baseline check and capture it.

### 2. Parse test results

Extract from both baseline and current: total tests passing, failing, skipped; test-suite count.

### 3. Diff against baselines

Compare current results against `<!-- OVERRIDE: IDENTITY.REFACTOR_DOCS_ROOT -->Docs/refactoring/<!-- /OVERRIDE -->baselines/test-results.txt`.
Extract pass/fail counts from both and compute deltas. (Adapt the parse to your runner's output format; the
contract is "compare baseline pass/fail set against current pass/fail set.")

### 4. Check for regressions

A regression is any of:
- Tests that passed in baseline now fail.
- New lint errors in files that were lint-clean in baseline.
- New typecheck errors in files that compiled cleanly in baseline.
- Schema validation errors.
- Characterization test failures (if they existed in baseline).
- New failures from project-specific scanners.

Pre-existing failures (present in baseline, still failing now) are NOT regressions. The report must distinguish
"newly failing since baseline" from "still failing as before."

### 4.5. Auto-bisect on regression

When a regression is detected, automatically bisect to find the offending commit. This replaces what would
otherwise be an hour or more of manual investigation per regression.

```bash
BASELINE_SHA=$(cat <!-- OVERRIDE: IDENTITY.REFACTOR_DOCS_ROOT -->Docs/refactoring/<!-- /OVERRIDE -->baselines/baseline-sha.txt)
CURRENT_SHA=$(git rev-parse HEAD)

for test_id in $NEWLY_FAILING_TESTS; do
  VERIFY_CMD="<!-- OVERRIDE: COMMANDS.TEST_ONE -->npx vitest run<!-- /OVERRIDE --> ${test_id}"
  echo "Bisecting regression: $test_id"
  git bisect start "$CURRENT_SHA" "$BASELINE_SHA"
  git bisect run sh -c "$VERIFY_CMD" || echo "bisect inconclusive for $test_id"
  BAD_COMMIT=$(git bisect log | grep "first bad commit" | awk '{print $4}')
  git bisect reset
  echo "$test_id: regression introduced in $BAD_COMMIT" >> /tmp/refactor-regressions.txt
done
```

For each regression, the report includes the test ID AND the introducing commit, so the round-close decision is
informed: revert the specific commit (single fix), accept the regression (broader scope), or investigate (a true
bug discovered during refactor). For regressions in tests that carry a `Verify:` command in their fix-prompt
(per `formats/fix-prompt-format.md`), use that explicit command instead of constructing one; it is authoritative
and the bisect runs faster. If bisect comes back inconclusive (a flaky test in the bisect range), flag it
`bisect-inconclusive` and investigate manually.

### 5. Check schema integrity

```bash
<!-- OVERRIDE: COMMANDS.SCHEMA_VALIDATE -->(echo "no schema validate configured")<!-- /OVERRIDE -->
# plus a "schema types compile" check if your engine generates code
```

For projects without a schema engine (no `COMMANDS.SCHEMA_VALIDATE` defined and no schema file), skip this step.

### 6. Check for uncommitted changes

```bash
git status --porcelain
```

Flag if there are unstaged changes; the refactor may be incomplete. Worktree-dispatched fixes should have
committed within their worktree branch; uncommitted changes on main suggest a merge was not clean.

### 7. Verify the schema-migration prod-apply gate

If the round had any fixes with `Schema migration: yes`, check the round's `close-checklist.md` for unticked
schema-migration rows:

```bash
grep -E "^\| .* \| .* \| .* \| .* \|$" <!-- OVERRIDE: IDENTITY.REFACTOR_DOCS_ROOT -->Docs/refactoring/<!-- /OVERRIDE -->round-N/close-checklist.md | grep -v "applied:"
```

A round with schema migrations cannot pass verification until those migrations are recorded as applied to prod (or
the project explicitly marks `applied: n/a` because it does not deploy to prod from this branch). The failure mode
this gate prevents: a schema change merged in code but never applied to the production database, so every read
against the new column throws at runtime.

### 8. Produce the verification report

Write to stdout (and optionally to `<!-- OVERRIDE: IDENTITY.REFACTOR_DOCS_ROOT -->Docs/refactoring/<!-- /OVERRIDE -->round-N/verification-report.md`):

```markdown
# Verification report

**Date:** YYYY-MM-DD
**Round:** N
**Baseline date:** [from baselines/]

## Test suite

| Metric | Baseline | Current | Delta | Newly failing? |
|--------|----------|---------|-------|----------------|
| Tests passing | X | Y | +Z | n/a |
| Tests failing | X | Y | +Z | [list of newly-failing test names, or "none"] |
| Tests skipped | X | Y | +Z | n/a |
| Test suites | X | Y | +Z | n/a |

## Regressions
[Tests that passed before but fail now, with the introducing commit from auto-bisect, or "None detected"]

## New tests
[Count of tests added since baseline]

## Lint
| Metric | Baseline | Current | Delta |
|--------|----------|---------|-------|
| Errors | X | Y | +Z |
| Warnings | X | Y | +Z |

## Type check
- typecheck: [pass/fail]
- New errors: [count, or "none"]

## Schema
- validate: [pass/fail]
- generate/compile: [pass/fail]
- Schema migrations applied to prod: [list with timestamps, or "n/a - no schema fixes this round"]

## Project-specific scanners
[Per-scanner pass/fail with delta from baseline]

## Control-plane / source-of-truth
- Shared policy drift: [pass/fail/not configured]
- Centralization risk: [none/missing bus/split bus/leaky bus/god bus]
- New shared helpers: [file paths + tests proving behavior]

## UI V&V
- Token/control-plane drift: [pass/fail/not configured]
- UI state coverage: [pass/fail/not configured; missing loading/empty/error/retry/permission/stale/mobile states]
- Visual smoke: [pass/fail/not configured]
- Accessibility smoke: [pass/fail/not configured]
- Design-handover conformance: [confirmed/mismatch/not checked]

## Characterization tests
[Pass/fail count, or "Not configured"]

## Uncommitted changes
[git status --porcelain output, or "clean"]

## Score hardening inputs
- Current readability/extensibility/auditability/security-maintainability score estimate: [numbers or "not scored"]
- Highest-leverage gaps: [lint categories, AI/MCP boundaries, raw SQL, route standardization, integration tests, audit docs, or "none identified"]
- Recommended next pass: [score-hardening / not requested / not applicable]

## Verdict
**[PASS]** - No regressions detected, N new tests added, schema migrations applied to prod (or n/a).
**[WARN]** - N new warnings, but no test regressions.
**[FAIL]** - N regressions detected. Review before merging. (Or: schema-migration deploy gate not satisfied.)
```

### 9. Update baselines (optional)

If the round is complete and verified, optionally update baselines for the next round (e.g.
`cp /tmp/refactor-verify-tests.txt <refactor-docs-root>/baselines/test-results.txt`). Only do this when explicitly
asked; baselines should be stable reference points for the next round's regression detection. Updating mid-round
invalidates the regression check.

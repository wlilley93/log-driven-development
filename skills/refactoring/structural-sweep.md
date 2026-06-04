---
name: structural-sweep
description: Refactoring suite, whole-codebase structural mode. A multi-round arc that touches every file in a codebase, partitioning by file size and directory tree, to bring every file under a structural floor (lines, complexity, separation of concerns, slop ratio). Different operating shape from a normal refactor round: per-file dispatch, arc-level acceptance, multi-round phasing, a mandatory pre-arc characterization-test gate for untested files. Use when the goal is "make the whole codebase readable" rather than "fix this list of bugs."
---

# Structural sweep

**Scope:** Codebase-neutral template. Per-project values come from `refactoring-overrides.md`.

A multi-round arc that touches every file in a codebase, partitioning by file size and directory tree, to bring
every file under a structural floor (lines, complexity, separation of concerns, slop ratio). This is a different
operating shape from a NORMAL refactor round: per-file dispatch, arc-level acceptance, multi-round phasing.

## Project overrides

Reads `<overrides-root>/refactoring-overrides.md`. Substitutes `<!-- OVERRIDE: KEY -->` markers; if absent, uses
the inline default. The key schema is in `references/overrides-template.md`.

## Shared infrastructure

This skill relies on shared docs. Read them before continuing:

- **Preflight wave** (`references/preflight-wave.md`): deterministic + LLM scanners. The per-batch dispatch in S3
  below replaces a NORMAL round's per-module review dispatch, but the preflight is identical.
- **API-surface diff** (`references/api-surface-diff.md`): per-round route/export/schema capture + diff. Mandatory
  for a structural sweep because per-file dispatch increases breaking-change risk.
- **Fix-prompt format** (`formats/fix-prompt-format.md`): the per-batch `result.md` uses the result-manifest schema.
- **Worker constitution** (`references/worker-constitution.md`): apply with the structural-sweep carve-outs noted
  in its "When in STRUCTURAL_SWEEP mode" section.
- **Model-tier dispatch, coordination layer, deferred ledger, drift detection, override resolution**: defined in
  `create-refactor-plan.md` (sections 1.65, 1.6.5, 1.6, 1.5, and Project overrides). NORMAL findings discovered
  during a sweep are routed to the deferred ledger.

## When to use this skill

Pick a structural sweep over a NORMAL plan when:

- The goal is "make the whole codebase readable" rather than "fix this list of bugs."
- Atomization debt has accumulated across many modules and per-module rounds defer it every time.
- The repo has known god-files (over ~500 LOC) on the score-trajectory that have survived 3+ rounds.
- A multi-round arc is acceptable (typically 3-6 rounds, weeks to months).

A structural-sweep arc spans multiple rounds; each round is one phase of the sweep. The arc's deliverable is
"every file in scope conforms to the structural floor," not any individual round's findings. Track arc progress in
`<refactor-docs-root>/arc-N/` (parallel to per-round dirs).

## Pre-arc gate: characterization tests for untested files

**Mandatory before any sweep round dispatches.** Files with zero test coverage cannot be safely split: the
agent's "tests still green" check passes vacuously. Generate characterization tests first, then sweep.

```bash
ARC_DIR="<!-- OVERRIDE: IDENTITY.REFACTOR_DOCS_ROOT -->Docs/refactoring/<!-- /OVERRIDE -->arc-N"
mkdir -p "$ARC_DIR/pre-arc"
<!-- OVERRIDE: COMMANDS.TEST_COVERAGE -->npm run test:run -- --coverage --coverage.reporter=json-summary<!-- /OVERRIDE --> > "$ARC_DIR/pre-arc/coverage.json" 2>&1
```

Then dispatch a Tier-2 agent to:

1. Parse coverage.json + the arc inventory.
2. For each zero-coverage file in scope, generate a characterization test that exercises every exported function
   with realistic inputs and snapshots the output, under a `characterization` test directory.
3. Commit each characterization test as one commit per file (so a failed split-attempt can isolate the regressing test).

Acceptance gate: every in-scope file has either (a) some existing coverage, (b) at least one characterization
test, or (c) is on `pre-arc/exemptions.txt` (auto-generated, vendored, types-only). If the user opts to skip this
gate (override `ARC.SKIP_CHARACTERIZATION_GATE: true`), the arc proceeds but every batch `result.md` flags
untested files as "split-without-test" and they get manually reviewed before merge.

## Structural floor (acceptance criteria)

The per-line function-length floor is NOT owned here. Function length is one concern with one owner: the
closure-gate threshold `[function] max_lines` in `tools/closure-gate/closure-gate.toml` (the continuous per-commit
deny gate). This sweep enforces that SAME number via `STRUCTURAL.MAX_FUNCTION_LINES`, which defaults to the
closure-gate value and is never a higher independent number (LDD-INV-9, one owner per concern). The vendored
`vibeclean`'s `max_function_lines` (do not edit) is a looser advisory scanner setting; the closure-gate threshold
is the floor that binds. The sweep's job is the axes the per-commit gate cannot do: mixed-concern separation, file
cohesion, and multi-file atomization. See the two-tier(+) ownership matrix in `docs/systems.md` (system 7).

Every file in scope must satisfy:

| Constraint | Default | Override key |
|---|---|---|
| Max file lines | 400 | `STRUCTURAL.MAX_FILE_LINES` |
| Max function lines | the closure-gate `[function] max_lines` threshold (cited, never re-set) | `STRUCTURAL.MAX_FUNCTION_LINES` (defaults to the closure-gate value) |
| Max cyclomatic complexity | 15 | `STRUCTURAL.MAX_COMPLEXITY` |
| Max nesting depth | 4 | `STRUCTURAL.MAX_NESTING` |
| Max function parameters | 5 | `STRUCTURAL.MAX_PARAMS` |
| Mixed-concern check | "no HTTP + business + DB in the same file" | `STRUCTURAL.CONCERN_RULES` |
| Slop ratio | under 5% (maintainability scanner's slop detector) | `STRUCTURAL.MAX_SLOP_RATIO` |

These are floors, not ideals. A file at 399 LOC + complexity 14 passes; a file at 400 LOC + complexity 16 does
not. Explicitly exempted files (auto-generated, vendored, generated client output) live in `arc-N/exemptions.txt`.

### When a sweep escalates to a Tier-2 refactor round (four checkable debt counters)

The structural sweep is Tier-2 risk-triggered, never routine (LDD-INV-9, LDD-INV-10, LDD-INV-11; matrix in
`docs/systems.md` system 7). "Escalate on flagged debt" is mechanical, not a feeling: a full sweep round fires only
when at least one of these four recorded counters trips:

1. **A recorded duplication concession.** The duplication ratchet would have to be RAISED to pass (any folding-debt
   the per-commit gate refused), journaled by hand per LDD-INV-10.
2. **A god-file surviving 3+ milestones.** A file over ~500 LOC on the score-trajectory's known list that prior
   per-module rounds have deferred at least three times.
3. **N+ surface-change concessions.** The count of functions over the closure-gate `[function] max_lines` floor (or
   of files over `MAX_FILE_LINES`, 400) accreting past the project's recorded budget.
4. **Three failed in-place fixes.** A concern that three separate per-commit attempts have failed to fix in place,
   signalling the cleanup is structural, not local.

Until a counter trips, the STRUCTURE phase stays a proportionate per-commit scan; the heavy sweep does not run.

## Arc directory structure

```
<refactor-docs-root>/arc-N/
  arc-prompt.md                    # Multi-round arc plan: phase breakdown, file count, time estimate
  floor-config.md                  # Structural floor settings + exemption list
  inventory.tsv                    # Every in-scope file: path, lines, complexity, scanner findings
  progress.tsv                     # Same shape as inventory but with: status, round-applied, commit, PR
  pre-arc/
    coverage.json                  # Coverage map captured at arc start
    exemptions.txt                 # Files exempted from the sweep
    characterization-result.md     # Outcome of pre-arc characterization-test generation
  round-N/
    batch-001/
      files.txt                    # Newline-separated list
      plan.md                      # Decomposition + import-rewrite plan (for god files)
      result.md                    # Per-file outcome
      pr-url.txt                   # Link to the PR opened for this batch
    batch-002/
    round-summary.md
  api-surface-snapshots/           # Per-round API surface for cross-round diffs
    round-N-routes.txt
    round-N-exports.txt
    round-N-arc-diff.md            # What's new/removed/changed since the prior round
  arc-summary.md                   # Updated each round close: arc % complete, projected end date
```

## Step S1: Generate the arc plan (Tier-2 agent, run once at arc start)

```bash
ARC_DIR="<!-- OVERRIDE: IDENTITY.REFACTOR_DOCS_ROOT -->Docs/refactoring/<!-- /OVERRIDE -->arc-N"
mkdir -p "$ARC_DIR"

# Tier-1 inventory generation (adapt the find filter + extensions to your stack)
find . -type f \( -name "*.ts" -o -name "*.tsx" \) \
  | grep -vE "node_modules|build|dist|generated|\.next|migrations" \
  | while read f; do
      lines=$(wc -l < "$f")
      printf '%s\t%s\n' "$f" "$lines"
    done | sort -k2 -n > "$ARC_DIR/inventory.tsv"
```

Then dispatch a Tier-2 planning agent that reads `inventory.tsv` + the structural floor + features-list and
produces `arc-prompt.md`:

- Total in-scope files.
- Tier breakdown: Tier 1 (small, batch 20:1), Tier 2 (medium, 1:1), Tier 3 (god, decomposition plan).
- Phase breakdown across rounds (typical 3-6, biased toward Tier 3 first when god files block multiple downstream improvements).
- Estimated wall-clock + token cost per round.
- Risk callouts (files with no test coverage, files with active concurrent work).

The arc plan is reviewed before round 1 dispatches. Do not auto-execute; this is the most expensive call in the
suite and the user signs off.

## Step S2: Per-round phase selection

Each round executes one phase. Phase selection priority:

1. **God files first** (Tier 3, over ~500 LOC OR on the score-trajectory's known list). One agent per file. Output:
   decomposition plan + multi-commit branch + one PR.
2. **Mixed-concern medium files** (Tier 2, 200-500 LOC AND a mixed-concern violation). One agent per file. Output:
   extracted modules + same-file shrink.
3. **Pure-shrink medium files** (Tier 2, 200-500 LOC, single-concern). Batch 5-10 files per agent.
4. **Tier 1 sweeps** (small files with scanner findings). Batch 20+ per agent.

Files passing the floor as inventoried are skipped: do not touch what is already clean.

## Step S3: Per-batch dispatch (Tier 3)

Each batch agent runs in its own worktree. Dispatch contract:

```
You are dispatched in worktree <wt>/structural/<batch-id>.

Required reading before editing any file:
- references/worker-constitution.md (per-fix discipline). Apply with the STRUCTURAL_SWEEP carve-outs noted in its
  "When in STRUCTURAL_SWEEP mode" section: behaviour-preservation rules (observable contracts, type safety,
  error/async/security/observability/a11y/i18n) apply identically; batch-size, candidate-template, and
  "too many domains" rules are replaced by the sweep equivalents (per-file commits, batch/result.md row,
  file-scoped domain check).

Inputs:
- batch/files.txt - the files you own
- arc-N/floor-config.md - structural floor settings
- arc-N/inventory.tsv - sliced to your batch
- arc-N/api-surface-snapshots/round-(N-1)-* - the prior round's API surface (so you don't break it)
- For Tier 3 god files: any prior decomposition plan in batch/plan.md

Mandatory todolist (create at session start):
- One todo per file in files.txt with status pending/in-progress/completed/failing/exempt
- Update the relevant todo before each file commit

Per-file inner loop (much faster than the full suite):
1. Read file + floor-config to identify violations
2. Apply the minimal change to bring it under floor
3. Run the related-tests selector against the changed files (only the tests that import them; seconds, not minutes)
4. If tests pass: git add + commit ("structural: <file> N->M LOC, complexity X->Y")
5. If tests fail: read failures, decide rollback vs fix-forward
6. Update the relevant todo

After all files in the batch:
1. Push the worktree branch to origin
2. Open one PR for the batch. Title: "[arc-N round-N batch-NNN] <Tier> structural sweep". Body: per-file outcome table.
3. Write batch/pr-url.txt with the PR URL
4. Write batch/result.md with the per-file outcome (lines-before/after, complexity-before/after, files-touched,
   commit-range, PR-url)

Constraints:
- One commit per file (Tier 1, 2) OR one commit per extracted unit (Tier 3 decomposition).
- Cross-file changes (imports, callers) ride in the same commit as their owning file.
- DO NOT defer files silently. Every file in files.txt ends with status: passing | failing | exempt.
- DO NOT modify the public API surface (route signatures, exported types, exported functions). If a refactor would
  change the surface, mark the file FAILING and document.
- If you find a real bug while atomizing, do not fix it inline. Log it as a NORMAL-mode followup in the deferred
  ledger and proceed.
```

Tier-3 god-file dispatches receive a decomposition plan from Step S1 or a prior round; the agent's job is to
execute it, not invent it.

## Step S4: Round close

After all batches in this round merge:

```bash
# Update progress.tsv with this round's outcomes
# Compute arc-level metrics
# Capture the API-surface snapshot for the next round's drift detection
# Update arc-summary.md with: % complete, files-passing-floor, projected end date
```

### S4a: API-surface snapshot

Run the capture + diff procedure from `references/api-surface-diff.md`, using `arc-N/api-surface-snapshots/` as
the snapshot directory. The acceptance gate is mandatory for a structural sweep: per-file dispatch increases the
chance of accidentally narrowing or removing a public symbol while passing tests.

### S4b: Round close-checklist

Additionally requires:
- [ ] Pre-arc characterization gate satisfied (or explicitly skipped)
- [ ] All Tier-3 god files in this round's batch have decomposition plans saved
- [ ] No NORMAL-mode security/correctness findings have been silently dropped (a sweep can de-prioritize but never
      bury other findings; defer them to a NORMAL follow-up round explicitly)
- [ ] Test count pre-arc vs post-round (tests should grow as splits introduce new boundaries; alarm if shrinking)
- [ ] API-surface diff vs prior round reviewed; intentional changes confirmed
- [ ] All batch PRs merged to main; no batch PRs in "open" state at round close

## Step S5: Arc close (after the final round)

The final round additionally produces:

- `arc-summary.md` with full before/after stats: total files, total LOC, max-file-LOC distribution, complexity distribution.
- A `score-trajectory.md` row per round showing the floor-passing % climb.
- A list of files that ended FAILING; these become a focused NORMAL round's input.
- An explicit decision: extend the arc one more round, accept residual FAILING files as exempt, or close.

## Performance / cost expectations

For a repo of N in-scope files with median ~250 LOC, three-tier dispatch (a cheaper model for Tier 1+2, the top
model for Tier 3):

- Tier 1 (small): ~0.4N files; batch 20:1.
- Tier 2 (medium): ~0.5N files; batch 5:1, or 1:1 for mixed-concern.
- Tier 3 (god): typically 5-30 files; 1:1 with multi-commit, hours each.

For a large repo (thousands of in-scope files):
- The work distributes across 3-6 rounds.
- The model-tier split roughly halves token cost versus an all-top-tier run.
- The big lever is per-agent test time: the related-tests selector runs only the tests importing the changed
  files (seconds), versus a full suite (minutes). That inner-loop speedup is what makes the sweep tractable at scale.

## Risk callouts

- **Concurrent feature work mid-arc.** A months-long arc on an active codebase will have feature branches landing
  throughout. Drift detection (create-refactor-plan Step 1.5) becomes critical mid-arc; rebase battles are
  expected. Plan for roughly one week of rebase + integration time per round.
- **No tests means no atomization.** The pre-arc characterization gate is mandatory by default for this reason. If
  skipped, expect "split-without-test" failures.
- **Rollback is rounds-deep.** Once a Tier-3 god file is decomposed and PRs are merged, rolling back means
  reverting many commits across many files. Keep the decomposition plan in `batch/plan.md` so a future "undo"
  round can replay it inverted.
- **Maintainability ROI is real but invisible to stakeholders.** Plan how to communicate progress: "47% of files
  now pass the structural floor" lands; "atomized 12 modules" does not. `arc-summary.md` should be public-readable.
  The optional stakeholder projection (create-refactor-plan 1.6.5) is the default channel for this.
- **A structural sweep is not the place to fix bugs.** When a batch agent notices a real bug while atomizing, it
  logs the finding in the deferred ledger as a NORMAL-mode followup. Do not bundle bug fixes with structural
  changes; commit boundaries get muddled.

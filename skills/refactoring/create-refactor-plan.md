---
name: create-refactor-plan
description: Refactoring suite, planning phase. Generates a full refactoring plan for a codebase by inventorying every module, running a deterministic + LLM preflight scan, deduping and tagging findings, drafting per-module fix-prompts, and producing a sequenced round prompt with captured baselines. Has a dry-run that projects cost, wall-clock, and readiness without dispatching. Execution is handled by run-refactor, verification by verify-refactor. Use to plan a refactoring round.
---

# Create refactor plan

**Scope:** Codebase-neutral template. Per-project values come from `refactoring-overrides.md`.

Generates a full refactoring plan for a codebase by inventorying every module, reviewing each for bugs and
structural issues, and producing sequenced fix-prompts. This is the planning phase. Execution is handled by
`run-refactor`, verification by `verify-refactor`.

## Invocation

- **plan**: execute the planning phase.
- **dry-run**: preview only. Show what WOULD dispatch (modules touched, preflight tools, projected wall-clock,
  projected token cost, batch sizing) without running any agents or writing artefacts. Output is a single
  summary report. Use before any committing run, especially the first round on a new project or the first
  structural-sweep arc.

The dry-run pulls overrides + features-list + deferred ledger + (if it exists) the prior round's snapshot, then
computes:

- Modules in scope this round.
- Preflight tools that will run + per-tool projected time.
- LLM-wave token-cost projection (Tier 2, prompt-cache-aware).
- Drafts that will be generated + projected count.
- Wave dispatch plan (Wave 0 platform fix? per-module waves? structural-sweep batches?).
- Projected wall-clock and total token cost.
- Drift-detection results (modules flagged for full review).
- **Pre-dispatch readiness check** (per `references/regression-avoidance.md`, "When NOT to start a round"):
  - Working tree clean? (uncommitted changes that are not yours = block)
  - Baseline SHA matches HEAD SHA? (drift = re-capture before dispatch)
  - Other concurrent agent sessions detected on this repo? (warn loudly)
  - Lint baseline captured against a working lint config? (broken lint config = degraded regression detection; warn)
  - Test baseline failures all in the pre-existing-failures registry? (unregistered failures = block)
  - All deferred-ledger inputs for this round resolvable? (ID format, severity, owning module valid)
- Risk callouts (untested files in scope, concurrent worktree branches, stale locks, missing prerequisites).

If the dry-run surfaces something unexpected (cost spike, missing baseline, drift on a module you thought was
stable, baseline-versus-HEAD drift, concurrent sessions) abort and address it before committing the round. The
dry-run costs nothing to run.

**Force override:** if you explicitly want to dispatch despite a readiness-check warning (refactoring against
in-flight code is sometimes intentional), confirm with a force flag. Log the force in the round prompt and the
completion report so the regression-detection results are interpreted with the right caveats.

## Project overrides

Before reading the procedure, look up the active project's overrides at `<overrides-root>/refactoring-overrides.md`.
For every `<!-- OVERRIDE: KEY -->` marker in this skill, substitute the value from the overrides file. If the
overrides file is absent or does not define a key, use the inline default. The key schema is documented in
`references/overrides-template.md`. The defaults below are written for a Node/TypeScript stack purely so the
procedure is concrete; replace them for your stack via overrides.

The overrides also carry project-specific learnings. Read those alongside the procedure and treat them as
additional constraints (especially for the Step 4 preflight tools and Step 9 close-checklist generation).

## Prerequisites

- Project initialised, with the overrides file present (run `bootstrap-refactor-overrides` first).
- `<!-- OVERRIDE: IDENTITY.REFACTOR_DOCS_ROOT -->Docs/refactoring/<!-- /OVERRIDE -->features-list.md` should
  exist (this skill creates it if missing).

## What it produces

```
Docs/refactoring/
  features-list.md                 # Master inventory + severity scores + dependency graph
  round-N/                         # One directory per refactoring round
    preflight/                     # Deterministic + LLM scan output (Step 4)
      vibescan.json                # OSS scanner aggregate (CVEs, secrets, SAST)
      vibeaudit-static.json        # AST extraction (IDOR, mass-assignment, auth bypass shape)
      vibeaudit-deep.md            # Agentic LLM codebase exploration
      methodology.md               # Security-suite reasoning pass (when configured)
      <validate>.txt, lint.json,   # Type / lint / schema / dep posture
        schema-validate.txt,
        dep-audit.json
      findings.md                  # Deduplicated, module-tagged, severity-sorted
      <module>/                    # Per-module draft fix-prompts (Step 4d)
        draft-fix-prompt.md        # Atomized fixes with proposed remediation + sequencing
    <module>/
      review.md                    # Multi-section review with quantitative scoring + verification evidence
      fix-prompt.md                # Sequenced fixes with rollback + structured result schema
    round-N-prompt.md              # Master prompt sequencing all work in this round
  baselines/                       # Test/audit baselines captured before changes
```

## Procedure

### 1. Sync features-list.md with the architecture-overview doc

Check if `Docs/refactoring/features-list.md` exists.

**If it exists:** read it, then read the project's architecture-overview doc (the module-index source from
overrides, default an `ARCHITECTURE.md` or a README module-index table). Compare the module index against the
features list. Flag any modules in the overview that lack a corresponding entry:

```
[!] New module detected in the overview: "<module>" - not in features-list.md
[!] Module removed from the overview: "<module>" - still tracked in features-list.md
```

Auto-add new modules with status "Needs review" and a TODO. Mark removed modules "Deprecated".

**If it does not exist:** create it by inventorying the codebase:

a) Read the architecture-overview doc for the key-modules table.
b) Scan the API/route layer for route groups.
c) Scan the library / services / components layers for feature boundaries.
d) Map every feature to a module. Group by: security infrastructure, core platform, addons, integrations, infrastructure.
e) Write `features-list.md` following `formats/features-list-format.md`.

### 1.5. Drift detection versus the last round's snapshot

If a previous round exists, compare current state against `Docs/refactoring/round-(N-1)/snapshot.md` (written at
the last round's close, Step 10):

- Diff the module-index table row by row. Any module whose row text changed (paths added, scope expanded, new
  specs referenced) is flagged `drift-detected` and auto-routed through full review this round even if its score
  is low.
- Diff the architecture-spec glob from overrides. Specs touched since the last round close mark their owning
  module `drift-detected`.
- New modules without a matching snapshot row are flagged `new-module` and get a first-pass review.

`drift-detected` is informational input to Step 4 (preflight) and Step 5 (review). Treat drift-detected modules
as if their score were bumped to at least 5.0 for sequencing. If no previous snapshot exists (round 1), skip.

### 1.6. Read the deferred-finding ledger

Check for `Docs/refactoring/deferred.md`. This is a single persistent ledger across all rounds (created by Step 8
of any round that defers fixes). Each row:

```
| id | source_round | deferred_to | severity | owning_module | reason | original_finding_link |
```

Filter rows where `deferred_to == round-N` (or `deferred_to == any` for unscheduled). These findings are
mandatory inputs to the current round's preflight `findings.md` (added with `source: deferred-ledger`, original
ID preserved). The owning module's draft fix-prompt (Step 4d) MUST address them or explicitly re-defer with a new
ledger entry. If `deferred.md` does not exist, skip (the first round creates it via Step 8).

### 1.6.5. Coordination layer (worktrees + parallel agents + todolists + stakeholder projection)

The suite operates four coordination tools, each at a different layer. Knowing which tool answers which question
keeps them from getting tangled.

| Layer | Question | Tool | Status |
|---|---|---|---|
| Process isolation | "How do concurrent agents not trample each other's edits?" | git worktrees under `.worktrees/round-N/<module>/` | wired (Steps 5, S3) |
| Concurrency budget | "How do we use the available parallel agents?" | wave dispatch capped at the project's parallel-agent budget | wired (Step 3, S3) |
| Per-agent progress | "How does one agent track its batch within one session?" | a per-session todolist (one task per work unit) | mandated below |
| Stakeholder view | "How does a human see arc progress without reading every progress file?" | an external tracker (one issue per god-file + one per round milestone), one-way projection at round close | optional, see overrides |

#### Tightened worktree + parallel-agent policy

- **Cap:** the project's simultaneous-worktree-agent budget (default 6). Beyond this, model-provider rate-limit
  retries dominate wall-clock and the parallelism inverts. Override via `<!-- OVERRIDE: DISPATCH.WAVE_SIZE -->6<!-- /OVERRIDE -->`.
- **Worktree path:** `.worktrees/round-N/<module>/` (gitignored at the repo root). Use `<!-- OVERRIDE: DISPATCH.WORKTREE_PATH -->.worktrees/round-N/<!-- /OVERRIDE -->` if your project uses a different convention.
- **Lock cleanup:** worktrees lock to a process PID. When that PID exits, the lock becomes stale but persists. A
  busy round can leave many stale locks. Step 10c (round close) MUST run `git worktree remove --force --force` on
  locks owned by exited PIDs and `git branch -D` on merged branches. Use `git worktree list --porcelain` +
  `ps -p <pid>` to identify stale locks.
- **Pre-dispatch verification:** before a wave dispatches, run `git worktree list | grep -c locked`. If it
  exceeds cap+5, the wave starts inside a polluted state. Clean up first.

#### Mandatory per-agent todolists

Every dispatched agent MUST create a todolist at session start with one task per work unit (one per file in a
structural-sweep batch; one per fix in a normal Step-5 module). Tasks move to in-progress when started and
completed when committed. Append to the dispatch contract:

```
Mandatory: create a todolist at session start with one task per file/fix in your input.
Update each task to in-progress when starting, completed when committed.
On session compaction or end, the todolist is the recovery point: the next session in this worktree reads
the todolist state and resumes from the first non-completed task.
```

Two reasons this is mandatory, not optional:
1. **Crash recovery.** Agents get compacted, killed, hit context limits. Without a per-file todolist, recovery
   starts over from the input file. With one, recovery resumes from the last completed task.
2. **Result-manifest correctness.** The result manifest needs accurate per-file outcomes. Counting completed
   todos is more reliable than counting commits (some files need no commit; some commits cover multiple files).

The todolist is per-session, not persisted to disk. It is the within-session coordination layer. Persistence is
on the worktree branch (commits) and the progress file (cross-session aggregate).

#### Stakeholder projection (optional, opt-in via overrides)

When the project has an external tracker configured (overrides `TRACKER.WORKSPACE` set), the suite projects arc
state at round close:

- **One tracker issue per god-file** in a structural-sweep arc. Status maps from the progress file: pending →
  Backlog, in-progress → In Progress, passing → Done, failing → Triage.
- **One tracker issue per round** as a milestone parent. Sub-issues are the per-file issues touched that round.
  Closing the milestone signals the round complete.
- **Sync direction is one-way: progress file → tracker.** Never the reverse. If a stakeholder edits an issue, the
  next round close overwrites it. The tracker is read-only for the team beyond comments.
- **Triggered at round close**, not continuously. Mid-round tracker state is intentionally stale; this prevents
  tracker updates becoming a dispatch bottleneck.

The tracker is purely projection. It does NOT replace the deferred ledger or the progress file; those remain
canonical. It answers "what does the arc look like to a non-technical stakeholder" and nothing else.

### 1.65. Model-tier dispatch (cost-aware)

Refactor work has a natural cost ladder. Most of it is mechanical (inventory, classification, routing, draft
generation); a smaller core is reasoning-heavy (final review, execution, edge-case judgement). Spending top-tier
model budget on mechanical work is wasteful; using a cheap model for reasoning-heavy work produces sloppy output.

The suite supports three model tiers, configured per-step via overrides:

| Tier | Default | When to use | Cost vs Tier-3 |
|---|---|---|---|
| Tier 1, free/local or small | a local model CLI or a small hosted model | Inventory generation, file-metadata extraction, tier classification, finding routing/dedup, scanner-output normalization. Output is structured data; the quality bar is "does not hallucinate paths." | ~0% (free local) or a few % (small hosted) |
| Tier 2, mid | a mid-tier reasoning model | Deep agentic exploration, security methodology dispatch, draft fix-prompts (Step 4d), structural-sweep arc + decomposition planning. Output is reasoning-heavy plans + analysis. | ~20% |
| Tier 3, top | a top-tier reasoning model | Step-5 per-module agent (validate draft against code + execute), structural-sweep batch dispatch (apply decomposition plans), edge-case judgement, cross-file ripple resolution. Output is code that lands in commits. | 100% (baseline) |

**Override keys** (see `references/overrides-template.md`): `MODELS.TIER_1`, `MODELS.TIER_2`, `MODELS.TIER_3`,
plus an optional `MODELS.LOCAL_BIN` / `MODELS.LOCAL_MODEL` to route Tier 1 to a local CLI instead of a hosted
model. When a local CLI is configured, Tier 1 routes to it. The handoff format is identical: Tier 1 produces
structured JSON / markdown that Tier 2 + 3 read without knowing the upstream model. Compatibility is enforced by
output schema, not by model identity.

**Handoff discipline.** The win comes from structured handoffs. Tier 1 → Tier 2: structured JSON inventory +
classifications. Tier 2 → Tier 3: explicit decomposition plans with file paths + line ranges + import-rewrite
tables. When the handoff is narrative ("this file probably needs splitting"), Tier 3 has to redo the work and the
cost saving evaporates. The fix-prompt format is already structured enough; the decomposition-plan format
(structural-sweep Step S1) is the structured-output schema for the sweep path.

**Per-step tier mapping:**

```
Step 4a deterministic preflight       Tier 1   (mechanical scanners, no LLM)
Step 4b deep agentic scan             Tier 2
Step 4b methodology dispatch          Tier 2
Step 4c findings dedup + module-tag   Tier 1
Step 4d draft fix-prompts             Tier 2
Step 5 per-module agent               Tier 3
Step 9 close-checklist generation     Tier 1
Step 10 round close (snapshots, etc)  Tier 1

structural-sweep S1 inventory          Tier 1
structural-sweep S1 arc planning       Tier 2
structural-sweep S2 decomposition      Tier 2
structural-sweep S3 batch dispatch     Tier 3
structural-sweep S4 round-close metrics Tier 1
```

Tier dispatch does not unblock more parallelism; it makes the existing parallelism cheaper. Wall-clock is
unchanged; only token cost moves.

### 1.7. Determine round mode (NORMAL or STRUCTURAL_SWEEP)

**NORMAL mode** (default): per-module review with severity-budgeted fixes. Best for security-driven rounds,
drift cleanup, and targeted re-reviews. Keep using this when the round goal is "fix what's broken."

**STRUCTURAL_SWEEP mode**: every-file pass. Dispatch is per-file (or per-directory batch), not per-module.
Acceptance switches from "drain severity" to "every file passes a structural floor." Best for arc-level
codebase-wide atomization that does not fit per-module review.

Pick STRUCTURAL_SWEEP when:
- The goal is "make the whole codebase readable" rather than "fix this list of bugs."
- Atomization debt has accumulated across many modules and per-module rounds defer it every time.
- The repo has known god-files (over ~500 LOC) on the score-trajectory that have survived 3+ rounds.
- A multi-round arc is acceptable (typically 3-6 rounds, weeks to months).

A STRUCTURAL_SWEEP arc spans multiple rounds; each round is one phase. The arc's deliverable is "every file in
scope conforms to the structural floor," not any individual round's findings. Track arc progress in
`Docs/refactoring/arc-N/`.

If STRUCTURAL_SWEEP, jump to `structural-sweep.md` rather than continuing through Steps 2-10. The normal procedure
assumes per-module dispatch, which does not scale to thousands of files.

### 2. Determine the round number

Check existing `Docs/refactoring/round-*/` directories. The new round is N+1 (or 1 if none exist).

### 3. Create the round directory structure

```bash
mkdir -p "Docs/refactoring/round-N"
```

For each module in features-list.md that is not "Done", create a subdirectory.

### 4. Preflight scans (deterministic + LLM)

Run the full preflight wave per `references/preflight-wave.md`. Output goes to
`<refactor-docs-root>/round-N/preflight/`. The wave has four sub-phases (4a deterministic, 4b LLM, 4c dedupe +
module-tag, 4d draft per-module fix-prompts), all defined in the shared doc; do not re-implement here.
Cross-cutting V&V passes (control-plane / source-of-truth review, UI verification-and-validation) are first-class
optional subagents inside 4b, not ad hoc notes inside module reviews.

| Phase | Tier | Time | Output |
|---|---|---|---|
| 4a Deterministic | n/a | ~10 min | scanner JSONs, validate/lint/typecheck/dep posture, optional control-plane + UI scans |
| 4b deep agentic scan | Tier 2 | ~30-60 min | `vibeaudit-deep.md` |
| 4b methodology dispatch | Tier 2 | ~30-60 min | `methodology.md` |
| 4b control-plane methodology | Tier 2 | ~10-30 min | when cross-cutting architecture / source-of-truth scope exists |
| 4b UI V&V methodology | Tier 2 | ~10-45 min | when frontend / UI overhaul scope exists |
| 4c Dedupe + module-tag | Tier 1 | ~5 min | `findings.md` (merged + sorted + cross-cutting detected) |
| 4d Draft per-module fix-prompts | Tier 2 | ~30s per module, parallelizable | `preflight/<module>/draft-fix-prompt.md` |

If you would skip preflight (a follow-up round with no commits since the last round) document the decision and
rationale in the round prompt; do not silently skip.

### 4.5. Regulated-data coverage drift (only when applicable)

If the project has a subject-rights / regulated-data pipeline (a discover-and-erase orchestrator with per-subsystem
hooks that satisfies an obligation like right-to-access and right-to-erasure), every refactoring round MUST check
whether the round adds, renames, or restructures any data model that holds subject-attributable data without
updating the corresponding hook.

**Why this matters.** The orchestrator's contract is "every byte attributable to a subject can be discovered and
erased." A new model with a subject foreign key (a `userId`, `createdById`, `uploadedById`, `authorId`, etc.) that
no hook walks is a silent coverage gap. A periodic verification job will not catch it (it uses the same hook set);
only an external audit or a subject's own export request will surface it, and by then it is a regulatory finding,
not a routine follow-up.

**What to scan.** In the deterministic preflight, alongside typecheck/lint/schema, run a scan that lists data
models carrying a subject-attribution foreign key, the hooks currently registered, and a rough proxy for which
models each hook touches. Then in the 4b methodology pass, add a section that compares the model list against hook
coverage and flags any model whose subject-attribution FK is not handled by exactly one hook. Tag those findings
so 4c routing surfaces them under the owning module.

**Outputs to look for:**
- A new model with a subject FK that no hook walks → high-severity finding "add hook coverage or document an
  explicit out-of-scope reason."
- A renamed FK column on a covered model where the hook was not updated → critical; erasure now silently misses
  these rows.
- A nullability change on a previously-tombstoned FK → critical; the tombstone strategy may switch from null-out
  to hard-delete and break audit/billing aggregates.

This whole step is skipped on projects with no regulated-data obligations. It is the canonical example of a
project-specific coverage check that the overrides Learnings section can encode.

### 5. Validate draft + finalize review + fix-prompt

**Dispatch contract.** Every module agent runs in its own git worktree branch (`refactor/round-N/<module>`) so
concurrent agents do not trample each other's edits. Worktrees live under `.worktrees/round-N/<module>/`
(gitignored). Use `git worktree add` per module; the orchestrator merges branches back between waves.

**Wave sizing.** Dispatch in waves of 3-6 parallel agents (the project's concurrency budget caps real
parallelism). Within a wave, agents run independently; between waves the orchestrator merges, runs targeted
regression sweeps, then dispatches the next wave. Sequence waves using the dependency graph from
features-list.md: upstream-shared-files modules go in earlier waves.

**Wave 0: platform module (if cross-cutting findings exist).** If Step 4c produced a `platform` module with
`cross_cutting: true` findings, dispatch ONE agent against `preflight/platform/draft-fix-prompt.md` first, before
any per-module wave. Cross-cutting fixes typically modify shared helpers, base middleware, or pattern-extension
points that downstream agents depend on. Merging Wave 0 first means downstream agents pick up the fix
automatically rather than re-implementing it module by module. The canonical example: introducing a
validation helper at the shared-helper level auto-propagates to every handler that calls it, versus patching each
handler in its own module.

**Per-module agent input slice (token budget).** Do not feed each module agent the full architecture-overview doc.
Prepare a per-module input pack:

```
# Module input pack: <module-name>

## Architecture-overview slice
<the relevant module-index row + the architecture/conventions sections that mention this module>

## Architecture spec
<contents of the per-module architecture spec, if one exists>

## Prior-round delta
git log --oneline --since=<last-round-close-sha> -- <files-touched-by-this-module>
<list of commits since last round close that touched this module's files>

## Module slice from preflight/findings.md
<all findings where module == <this-module>, severity-sorted desc>

## Draft fix-prompt (from Step 4d)
<contents of preflight/<module>/draft-fix-prompt.md>

## Files
<list of files this module owns, from features-list Touches column>
```

The git-delta is high-signal: a module untouched since last round close is steady-state and only needs drift
verification; a module with 30 commits since last close is volatile and warrants deeper scrutiny. Note in
review.md whether the agent treated the module as steady-state or volatile.

**Per-module agent task.** For each module, dispatch a single agent that:

1. Reads the module's `preflight/<module>/draft-fix-prompt.md` (from Step 4d).
2. Reads the module's slice of `preflight/findings.md` (from Step 4c).
3. Reads the actual code (the module's files).
4. Validates each draft fix against code: `high`-confidence drafts get spot-checked and adopted verbatim if the
   file/line still matches; `medium` get the surrounding code read and the `Fix:` text refined; `low` get
   rewritten from scratch using code context.
5. Adds any findings the LLM wave + tools missed (genuine code-aware discovery; fresh IDs in the module-local
   namespace `M-1`, `M-2`, ...).
6. Writes `review.md` using `formats/review-format.md`, citing both preflight finding IDs and any new local IDs.
7. Writes `fix-prompt.md` (final, executable) by merging the validated draft with the new findings, re-sequenced.

Do not create an intermediate TODO file that a second agent reads; that doubles the round-trips. The draft from
Step 4d is the head-start; Step 5 collapses validation + review + finalization into one agent pass. For modules
with zero preflight findings, no draft exists; the agent runs a full review pass from scratch.

### 6. Write the round prompt

Create `Docs/refactoring/round-N/round-N-prompt.md` that sequences all work using the dependency graph:

1. **Security infrastructure first** (auth, CSRF, rate limiting reviewed before anything else).
2. **Security-critical fix-prompts next** (modules with severity score >= 8.0).
3. **Modules with cross-dependencies** (respect the graph; upstream before downstream).
4. **Remaining fixes** by severity descending.
5. **Lower-priority reviews last.**

### 7. Capture / refresh baselines

The protocol is in `references/regression-avoidance.md`, checkpoint 1. Two scenarios:

**Round 1 (first ever):** capture baselines from scratch.

**Round N (continuing):** verify baseline freshness vs HEAD. If stale, re-capture before dispatch.

```bash
BASELINE_SHA=$(cat <!-- OVERRIDE: IDENTITY.REFACTOR_DOCS_ROOT -->Docs/refactoring/<!-- /OVERRIDE -->baselines/baseline-sha.txt 2>/dev/null)
HEAD_SHA=$(git rev-parse HEAD)

if [ "$BASELINE_SHA" != "$HEAD_SHA" ] && [ -n "$BASELINE_SHA" ]; then
  COMMITS_SINCE=$(git rev-list "${BASELINE_SHA}..${HEAD_SHA}" --count 2>/dev/null || echo "?")
  echo "[!] Baseline drift: $COMMITS_SINCE commits since baseline-sha"
  echo "[!] Re-capturing baselines at $HEAD_SHA before R$N dispatches"
fi
```

Capture (or re-capture) commands:

```bash
BASELINES="<!-- OVERRIDE: IDENTITY.REFACTOR_DOCS_ROOT -->Docs/refactoring/<!-- /OVERRIDE -->baselines"
mkdir -p "$BASELINES"
<!-- OVERRIDE: COMMANDS.TEST -->npm run test:run<!-- /OVERRIDE --> > "$BASELINES/test-results.txt" 2>&1
<!-- OVERRIDE: COMMANDS.SCHEMA_VALIDATE -->(echo "no schema validate configured")<!-- /OVERRIDE --> > "$BASELINES/schema-baseline.txt" 2>&1
<!-- OVERRIDE: COMMANDS.LINT -->npm run lint<!-- /OVERRIDE --> > "$BASELINES/lint-baseline.txt" 2>&1
<!-- OVERRIDE: COMMANDS.TYPECHECK -->npx tsc --noEmit<!-- /OVERRIDE --> > "$BASELINES/tsc-baseline.txt" 2>&1
git log --oneline -20 > "$BASELINES/git-log.txt"
git rev-parse HEAD > "$BASELINES/baseline-sha.txt"
```

`baseline-sha.txt` is referenced by Step 1.5 of round-(N+1) when no `snapshot.md` exists for the prior round. For
continuing rounds, the per-round `snapshot.md` (Step 10a) takes precedence. For projects whose overrides include
additional project-specific scanners, ALSO capture each scanner's baseline output; `verify-refactor` diffs current
scanner output against these.

**If the continuing-round baseline-sha matches HEAD:** reuse the previous baselines; no re-capture needed.

**If the baseline is stale and the lint config is broken:** the lint baseline captures the broken state and lint
regression detection is degraded until the config is fixed (typically a Wave-0 platform fix in the same round).
Document this in the completion report so `verify-refactor`'s lint check is interpreted correctly.

### 8. Update features-list.md

Mark modules in-progress for this round. Update severity scores based on the union of preflight findings +
per-module review findings. Modules with high preflight finding density but a low historical score get re-flagged
for deeper review.

### 9. Report + close-checklist generation

Summarize: how many modules, how many need reviews versus prompts, the sequencing; dependency-graph constraints;
preflight stats (findings by source, top 10 by severity, count of `unrouted` findings needing manual triage,
count of `cross_cutting` platform-module findings); critical findings to address first; drift modules; deferred
ledger size for the current round.

**Auto-emit a close-checklist.** Scan every module's `fix-prompt.md` for fixes with `Schema migration: yes`. For
each, emit a row in `Docs/refactoring/round-N/close-checklist.md`:

```markdown
# Round N - Pre-merge close checklist

## Schema migrations (MUST apply post-deploy)

| Module | Fix ID | Schema change | Verification command |
|---|---|---|---|
| <module> | M-3 | Added `<table>.<column>` (FK to <ref>) | <a command that confirms the column exists in prod> |

After deploy, run the project's prod-migration command (from overrides SCHEMA.PROD_MIGRATION). Pin the migration
runner version to match the deployed runtime version, not the manifest version.

## Cross-cutting platform fixes (verify Wave 0 merged before per-module waves)

| Fix ID | Affected modules | Verification |
|---|---|---|

## Pre-deploy regression sweep

- [ ] Full test run on main HEAD vs baselines/test-results.txt
- [ ] No new lint errors
- [ ] Schema validate passes
- [ ] Drift-detected modules have a post-fix score recorded in features-list.md
```

The failure mode this checklist prevents: a schema change merged in code but never applied to the production
database, so every read against the new column throws at runtime. Schema-touching fixes get a structured prompt
that the round close cannot skip.

### 9.4. Cache-hit-rate telemetry (when the model API exposes cache stats)

If your model provider returns prompt-cache statistics per call (cache-creation tokens, cache-read tokens,
uncached input tokens), aggregate them per round at round close. Telemetry ground-truths whether tier dispatch is
paying off and surfaces prompts that are accidentally cache-busting.

```bash
# Aggregate per-tier from the project's cost ledger if it has one
<!-- OVERRIDE: TELEMETRY.COST_LEDGER_PATH -->(echo "no cost ledger configured")<!-- /OVERRIDE --> \
  > <!-- OVERRIDE: IDENTITY.REFACTOR_DOCS_ROOT -->Docs/refactoring/<!-- /OVERRIDE -->round-N/cache-telemetry.md
```

The telemetry doc captures, per tier: total input tokens, cache-read tokens, cache hit rate, cache-create tokens,
and effective cost versus no-cache. Healthy rule-of-thumb ranges: Tier 2 over 80% on volatile sections, over 95%
on stable; Tier 3 over 50%. Below those = a prompt is cache-busting (often timestamps in a system prompt, dynamic
round numbers in headers); investigate. For projects without a cost ledger, this section reads "Not configured"
and round close still passes.

### 9.5. API-surface capture + diff

Per `references/api-surface-diff.md`. Capture the current API surface (routes, exported symbols, schema), diff
against the prior round's snapshot, fail close on any unacknowledged breaking change. Tests passing alone do not
catch accidentally-changed route signatures, removed exports, or shape-narrowing type changes; the diff does.
This applies to both NORMAL and STRUCTURAL_SWEEP rounds. On round 1 (no prior snapshot) capture only; the diff
activates from round 2.

### 10. Round close (run after run-refactor + verify-refactor pass)

Several artefacts, all under `Docs/refactoring/round-N/`:

#### 10a. Snapshot for the next round's drift detection

Capture the state that round-(N+1)'s Step 1.5 will diff against:

```bash
mkdir -p Docs/refactoring/round-N
{
  echo "# Round N - End-of-round snapshot"
  echo ""
  echo "**Closed at:** $(git rev-parse HEAD) ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
  echo ""
  echo "## Module index (verbatim)"
  echo ""
  # extract the module-index table from the architecture-overview doc
  echo ""
  echo "## Architecture spec inventory"
  ls -la <!-- OVERRIDE: IDENTITY.ARCH_SPECS_GLOB -->docs/architecture/*.md<!-- /OVERRIDE --> 2>/dev/null
} > Docs/refactoring/round-N/snapshot.md
```

#### 10b. Amend the deferred-finding ledger

For every fix in this round's fix-prompts where the executor flagged `status: deferred`:

```bash
# append to Docs/refactoring/deferred.md (create if missing)
| <id> | round-N | round-(N+1) | <severity> | <module> | <reason> | round-N/<module>/fix-prompt.md#fix-<n> |
```

Single ledger across all rounds. Step 1.6 of every future round reads this. If a fix deferred in round-N is
applied in round-(N+1), the round-(N+1) close removes the row (or marks it `applied: round-(N+1)`).

#### 10c. Worktree teardown

```bash
for module in $(ls .worktrees/round-N/ 2>/dev/null); do
  branch="refactor/round-N/$module"
  if git merge-base --is-ancestor "$branch" main; then
    git worktree remove --force ".worktrees/round-N/$module"
    git branch -D "$branch"
  else
    echo "[WARN] $branch not merged to main; leaving worktree intact"
  fi
done
rmdir .worktrees/round-N 2>/dev/null
```

Teardown is best-effort. If a worktree will not release, log it and move on; the harness cleans up at session end.
The important part is that merged branches do not accumulate as garbage.

#### 10d. Update score-trajectory.md

Append a column for round N to `Docs/refactoring/score-trajectory.md`. For each module touched, record the
post-round score. For untouched modules, copy the prior round's score. Add a "Round N close summary" narrating:
severity drained, modules touched, deferred-ledger delta.

#### 10e. Retrospective synthesis (Tier 1)

Dispatch a Tier-1 agent that reads the round's completion report, cache telemetry, API-surface diff, the full
score-trajectory and deferred ledger, the current features-list, the dispatched batches' result manifests,
reviewing-agent rejection logs, and any pre-round dry-run report (for actuals-versus-projection). It produces
`round-N/retrospective.md`:

```markdown
# Round N - Retrospective

## What worked
[2-5 bullets: patterns/decisions that paid off, with evidence]

## What didn't
[2-5 bullets: friction, false starts, missed predictions, with evidence]

## Surprises
[Things we didn't expect, regardless of valence. The most useful section for future rounds.]

## Cost/projection actuals
| Metric | Projected (dry-run) | Actual | Delta | Cause |
|---|---:|---:|---:|---|
| Token cost | $X | $Y | +Z% | <reason> |
| Wall-clock | Xh | Yh | +Z% | <reason> |
| Fixes shipped | X | Y | -Z | <reason> |

## Reviewing-agent catches
[Fixes the pre-commit reviewer caught + the would-be-bug class. If 0, note it.]

## Cache hit-rate trends
[From cache-telemetry.md, R(N-1) → R(N). Flag prompts that started cache-busting.]

## Recommended overrides amendments
For each Surprise or What-didn't entry, propose a one-line update to the project's overrides Learnings section.
The user reviews these proposals; accepted ones get appended.

## Patterns to encode in CI/preflight
[If a surprise recurs across 2+ rounds, propose a deterministic check (lint rule, scanner, test) that catches it.]
```

The "Recommended overrides amendments" section is propose-only: the user explicitly accepts or rejects each
before it lands in the overrides file. The suite proposes; the human decides what becomes durable encoded
knowledge. This step closes the knowledge-management loop: without it, lessons live in handover prose nobody
re-reads.

---

## Format references

The reusable schemas live in `formats/`:

- `formats/features-list-format.md` - master inventory + scoring table + dependency graph + per-module rows.
- `formats/review-format.md` - per-module `review.md` schema.
- `formats/fix-prompt-format.md` - per-fix block schema + execution result manifest.

Every Step 4d draft and Step 5 finalization must follow these schemas. The validation logic in `run-refactor`
and `verify-refactor` parses against them.

---

## STRUCTURAL_SWEEP arc procedure

Extracted to its own skill: see `structural-sweep.md`. Invoke it when the round mode (Step 1.7) selects
STRUCTURAL_SWEEP. The structural-sweep skill is self-contained but reuses the shared infrastructure defined here:
model-tier dispatch (1.65), coordination layer (1.6.5), deferred ledger (1.6), drift detection (1.5), and
override resolution. Read those sections first if structural-sweep references them.

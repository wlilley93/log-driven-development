---
name: refactoring
description: The behaviour-preserving improvement engine - the STRUCTURE phase tool of Ledger-Driven Development. Four chained playbooks (structural-sweep, create-refactor-plan, run-refactor, verify-refactor) plus a per-project bootstrap, run as orchestrated multi-agent waves over a real codebase. Inventory every module, run a deterministic + LLM preflight, atomize findings into sequenced fix-prompts, dispatch worktree agents under a worker constitution, then prove no behaviour changed against captured baselines. Use when you want to clean up, simplify, de-slop, or structurally atomize existing code WITHOUT changing what it does, on a repeatable round-by-round cadence that is auditable by construction.
---

# Refactoring suite

> Behaviour-preserving improvement, run as a disciplined multi-round operation. You do not "tidy the code";
> you inventory it, scan it deterministically and with LLMs, atomize the findings into sequenced fix-prompts,
> dispatch worktree agents under a strict worker constitution, and then prove against captured baselines that
> nothing observable changed. Every round leaves a ledger trail: findings, plan, fixes, verification, deferrals.

This is the **STRUCTURE** phase tool of Ledger-Driven Development. LDD harvests requirements out of legacy code,
distils a minimal spec, builds a walking skeleton, then loops spec versus build to zero-gap. The refactoring
suite is how you keep the *structure* of that build honest as it grows: it improves existing code while holding
observable behaviour fixed, so the spec stays the source of truth and the code stays readable.

## The operating law

**Refactoring is behaviour-preserving improvement.** Any behavioural change must be explicitly labelled and
approved before it is implemented. A round that changes what the software does is not a refactoring round, it is
a feature round, and it does not run here.

Security review is **delegated**, not duplicated. When a round touches a security surface (auth, session,
tenant isolation, secrets, dependencies, payments, plugin or MCP boundaries, privacy or compliance), the suite
classifies and scopes that surface and hands it to a separate security suite through a dispatch contract. The
refactoring engine consumes the security findings and verification requirements; it does not reinvent security
methodology. (If you do not have a separate security suite, the preflight degrades to a neutral methodology pass,
see `references/preflight-wave.md`.)

## Invariants

1. Observable behaviour is preserved unless explicitly approved.
2. Tests are captured before and after implementation.
3. Findings are labelled confirmed / likely / hypothesis / false-positive-risk.
4. No broad rewrite without a specific, evidence-backed finding.
5. One logical change per commit.
6. Verification evidence is fresher than the completion claim.
7. Any security, tenant, authz, auth/session, secrets, dependency, payment, plugin/MCP, privacy or compliance
   change requires a security-suite dispatch and fresh verification evidence.
8. Styling-token changes are policy changes, not cosmetic changes.
9. If three fix attempts fail, stop and question the architecture.

## The five playbooks and how they chain

The suite is one bootstrap plus four lifecycle playbooks. They run in order, and each consumes the prior one's
artefacts. A "round" is one pass through plan, run, verify. Rounds accumulate; the persistent artefacts
(features-list, deferred ledger, score-trajectory, baselines) carry across all of them.

```
bootstrap-refactor-overrides   (once per project)
        │   writes refactoring-overrides.md + the helper scripts the suite expects
        ▼
┌──────────────────────────── one round ────────────────────────────┐
│                                                                    │
│  structural-sweep ──┐   (whole-codebase mode; the alternative to   │
│   (optional mode)   │    per-module planning when the goal is      │
│                     │    "make the whole codebase pass a floor")   │
│                     ▼                                               │
│  create-refactor-plan                                              │
│   inventory every module → run the preflight wave (deterministic   │
│   + LLM scanners) → dedupe + tag findings → draft per-module       │
│   fix-prompts → sequence the round → capture baselines             │
│                     │                                               │
│                     ▼                                               │
│  run-refactor                                                      │
│   dispatch worktree agents per module/wave under the worker        │
│   constitution → per-fix test + pre-commit review + atomic commit  │
│   → result manifest per module                                     │
│                     │                                               │
│                     ▼                                               │
│  verify-refactor                                                   │
│   diff current state vs baselines → detect + auto-bisect           │
│   regressions → API-surface diff → schema-migration deploy gate    │
│   → PASS / WARN / FAIL verdict                                     │
│                     │                                               │
│                     ▼                                               │
│  round close (inside create-refactor-plan Step 10):                │
│   snapshot for next round's drift detection, amend the deferred    │
│   ledger, tear down worktrees, append to score-trajectory,         │
│   write the retrospective                                          │
└────────────────────────────────────────────────────────────────────┘
```

1. **`bootstrap-refactor-overrides`** runs once per project. It detects the stack (test runner, schema engine,
   deploy target, docs layout) and writes a populated `refactoring-overrides.md`, plus the two helper scripts
   the suite expects. Everything below reads those overrides at runtime and substitutes project-specific values
   into a codebase-neutral procedure.

2. **`create-refactor-plan`** is the planning phase. It inventories every module, runs the **preflight wave**
   (`references/preflight-wave.md`: a fast deterministic scan plus a slower agentic LLM scan), dedupes and
   module-tags the findings, drafts per-module fix-prompts, sequences the round by the dependency graph, and
   captures baselines. It has a `--dry-run` that projects cost, wall-clock, and readiness without dispatching.

3. **`run-refactor`** is execution. It reads the sequenced fix-prompts and dispatches subagents in git worktrees,
   one wave at a time. Each agent runs under the **worker constitution** (`references/worker-constitution.md`):
   smallest safe diff, no invented APIs, behaviour preserved, one atomic commit per fix, with a per-fix test run
   and a Tier-2 pre-commit reviewing agent before each commit.

4. **`verify-refactor`** is the proof. It re-runs tests/lint/typecheck/schema, diffs against the captured
   baselines, auto-bisects any regression to the introducing commit, runs the API-surface diff, and enforces the
   schema-migration deploy gate. It emits a PASS / WARN / FAIL verdict. No round is "done" without it.

5. **`structural-sweep`** is an alternative round *mode* selected inside `create-refactor-plan` Step 1.7. Instead
   of per-module review with severity-budgeted fixes, it does an every-file pass against a structural floor
   (max file lines, function lines, complexity, nesting, slop ratio). It is a multi-round arc, dispatched
   per-file in batches, and it reuses the same shared infrastructure (preflight, baselines, worker constitution,
   API-surface diff, deferred ledger).

## When to use this suite

- Simplifying recent changes or a bounded surface.
- Reviewing AI-generated code for maintainability, weird abstractions, or hidden risk (the de-slop case).
- Removing dead code or duplication.
- Tightening type/runtime boundaries.
- Improving comments, tests, components, or styling-token usage while preserving behaviour.
- Atomizing a whole codebase against a structural floor (the `structural-sweep` arc).

## When NOT to use it

- Building new features (that changes behaviour by definition).
- Debugging an unknown production failure (use systematic debugging first).
- Shipping documentation-only work.
- Broad modernisation without a bounded scope and a specific finding behind each change.

## The codebase-neutral / project-specific split

The *methodology* (preflight, atomization, wave dispatch, drift detection, deferred ledger, regression
checkpoints) is portable. The *mechanics* (which test command, which deploy gate, which schema engine, which
architecture-spec directory) are project-specific. The seam between them is the **overrides file**.

The playbooks contain `<!-- OVERRIDE: KEY -->default<!-- /OVERRIDE -->` markers at every project-specific hook
point. At runtime, the suite reads `refactoring-overrides.md` and substitutes each `KEY`; if a key is absent, the
inline default applies. The full key schema lives in `references/overrides-template.md`. The defaults in the
playbooks below are written for a Node/TypeScript stack (a JS test runner, an ORM with a schema file, a typed
build), purely because *some* concrete default is needed to read; replace them for your stack via overrides.

## Shared infrastructure (read before running any playbook)

The four playbooks chain into these shared documents. Read the ones a playbook points at before running it:

- `references/preflight-wave.md`  -  the deterministic + LLM scanner wave, dedupe, module-tagging, and the
  security-suite dispatch seam. Used by `create-refactor-plan` and `structural-sweep`.
- `references/worker-constitution.md`  -  the per-fix editing discipline every dispatched agent reads before
  touching a file. Used by `run-refactor` and `structural-sweep`.
- `references/regression-avoidance.md`  -  the canonical map of regression classes, their detection mechanism,
  and the explicit gaps; the four discipline checkpoints. Used by all four playbooks.
- `references/api-surface-diff.md`  -  capture the public API surface at round close and diff against the prior
  round, so a behaviour-preserving fix cannot silently break a signature. Used at every round close.
- `references/overrides-template.md`  -  the per-project override schema and the full key table.
- `formats/features-list-format.md`, `formats/review-format.md`, `formats/fix-prompt-format.md`  -  the output
  schemas the playbooks produce and the verification logic parses against.

## Coded tools

The preflight wave dispatches external scanners by name (a CVE/secret/SAST scanner, an AST security extractor,
and a maintainability/atomization/slop scanner). Runnable cleanroom reference implementations of those scanners,
parameterised for a generic project, live under `tools/refactoring/`. The wave degrades gracefully when a tool is
absent (it writes a stub artefact and continues), so the suite is usable with or without them.

## Outputs

Every round writes its artefacts under the project's refactor-docs root (default `Docs/refactoring/`):

- `features-list.md`  -  master inventory + severity scores + dependency graph (persistent across rounds)
- `round-N/preflight/`  -  scanner output + deduped `findings.md` + per-module draft fix-prompts
- `round-N/<module>/review.md` + `fix-prompt.md`  -  validated review and executable, sequenced fixes
- `round-N/completion-report.md` + `verification-report.md`  -  what ran, what changed, the verdict
- `baselines/`  -  test/lint/typecheck/schema baselines captured before changes
- `deferred.md`  -  single persistent ledger of deferred findings across all rounds
- `score-trajectory.md`  -  per-round score history

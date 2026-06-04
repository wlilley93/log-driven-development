<!--
TEMPLATE: Closure-gate config (the continuous structural enforcement contract).
WHEN: stand this up BEFORE the walking skeleton, so "clean" is checkable from the first line of the rebuild.
      This .md is the human-readable policy; the real gates live in your tooling (linter config, pre-commit
      hook, CI job). Revisit it at every milestone's STRUCTURE phase, tightening only.
HOW: copy this file to closure-gate.config.md, delete this comment, fill every section with REAL thresholds
     and the actual command behind each gate. The load-bearing rule: the duplication ratchet is a budget you
     only ever HOLD or LOWER by folding; you NEVER raise it to make a commit pass.
-->

# Closure-gate config: <system name, e.g. Tasky rebuild>

**Status:** <active since the walking skeleton>. **Tightened, never loosened.**

The single load-bearing rule, stated once: the duplication ratchet is a budget you only ever hold or lower by
folding duplication. Raising it to pass a commit is conceding the sprawl this gate exists to delete.

## Hard gates (deny: a failing check blocks the commit)

| Gate | Threshold | Action | Why |
|---|---|---|---|
| Formatter | `<cmd, e.g. prettier --check>` clean | deny | <reason> |
| Linter | `<cmd, e.g. eslint>` zero errors | deny | <reason> |
| Type-check | `<cmd, e.g. tsc --noEmit>` clean | deny | <reason> |
| Max function length | `<N>` lines | deny | A long function hides duplication and God-objects. |
| Max file length | `<N>` lines | warn at `<N-50>`, deny at `<N>` | Forces split-by-concern before a junk drawer forms. |
| Tests | full suite green from a clean checkout | deny | "Looks done" is not done; pass from clean, not just locally. |

- Example (Tasky): max function length 40, max file length 300, `tsc --noEmit` clean (the status lattice is only
  safe if `status` is typed; an `any` re-opens the drift).

## The duplication ratchet (the load-bearing gate)

A cross-module duplication budget, measured by `<tool, e.g. jscpd, min 30 tokens, min 5 lines>`.

- **Current budget: `<X>%`** of scanned lines may be duplicated. This is the number you last closed at.
- **The rule:** you may **hold** or **lower** this number. You may **never raise it to pass a commit.** If a change
  would exceed the budget, **fold** the duplication into one shared function; do not move the line.
- **What this specifically guards:** <the duplication this project must never re-grow>.
- Example (Tasky): the ratchet is what stops a *fourth* completion path appearing. When the first cut inlined the
  `status >= done` comparison across the list, board, and shared view, the ratchet tripped and the fix was to fold
  all three into one `isDone(status)` helper. Green by folding, never by raising.

## Red-until-built tests (spec surfaces declared but not yet covered)

A spec surface that exists in the spec but is not yet built ships a **failing** placeholder test, so an unbuilt
surface is visibly red, never silently absent. A green suite over a half-built spec is not done.

| Spec surface | Test | State |
|---|---|---|
| `<invariant or surface>` | `<the test that attacks it>` | `<green | red until built (M<N>)>` |
- Example (Tasky): INV-REOPEN -> build chain A -> B -> C, reopen A, assert B and C drop to `in_progress`; build
  cycle A -> B -> A, assert reopen terminates. (green at M1.)
- Example (Tasky): blocking-edge editing -> create/remove `blockedBy` edges with the spec'd cycle policy. (red
  until built, M2.)

## Supply-chain (every commit, cheap)

- `<cmd, e.g. npm audit --omit=dev>` runs in CI; a new high or critical advisory denies. (The deep, risk-targeted
  security audit is a milestone-close concern, not a per-commit gate.)

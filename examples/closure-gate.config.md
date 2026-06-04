# Closure-gate config: Tasky rebuild

> **What this is.** The human-readable contract for Tasky's **continuous structural enforcement**: the executable
> checks that run on every commit and decide, mechanically, whether the tree is clean and complete. This `.md`
> documents the policy; the real gates live in the linter config, the pre-commit hook, and the CI job. It was
> stood up **before** the M1 walking skeleton, so "clean" was checkable from the first line of the rebuild.

**Status:** active since the M1 skeleton. **Tightened, never loosened.**

For the discipline behind this, see [`../docs/artifacts.md`](../docs/artifacts.md) ("The closure-gate config").
The single load-bearing rule: the duplication ratchet is a budget you only ever **hold or lower by folding**, never
raise to make a commit pass.

---

## Hard gates (deny: a failing check blocks the commit)

| Gate | Threshold | Action | Why |
|---|---|---|---|
| Formatter | `prettier --check` clean | deny | No formatting noise in diffs; format is not a matter of taste. |
| Linter | `eslint` zero errors (warnings allowed in dev, denied in CI) | deny | Catches the obvious class of defect before review. |
| Type-check | `tsc --noEmit` clean | deny | The status lattice is only safe if `status` is typed; an `any` here re-opens the drift. |
| Max function length | 40 lines (body, excluding signature and braces) | deny | A long function is where a God-object and hidden duplication grow. The lattice logic must stay small. |
| Max file length | 300 lines | warn at 250, deny at 300 | Forces split-by-concern before a file becomes a junk drawer. |
| Tests | full suite green from a clean checkout | deny | "Looks done" is not done; the suite must pass from clean, not just locally. |

## The duplication ratchet (the load-bearing gate)

A cross-module duplication budget, measured by the duplication scanner (`jscpd`, min 30 tokens, min 5 lines).

- **Current budget: 0.8%** of scanned lines may be duplicated. This is the number M1 closed at.
- **The rule:** you may **hold** this number or **lower** it. You may **never raise it to make a commit pass.**
  Raising the ratchet is conceding the sprawl this rebuild exists to delete. If a change would exceed the budget,
  you **fold** the duplication (extract the shared function), you do not move the line.
- **The specific thing this guards:** Tasky's whole reason for the rebuild is that completion logic existed in
  three places. The ratchet is what stops a *fourth* from appearing. During M1, the first cut inlined the
  `status >= done` comparison in the list, the board, and the shared view; the ratchet tripped, and the fix was to
  fold all three into one `isDone(status)` helper (recorded in [`M1-signoff.md`](M1-signoff.md), STRUCTURE phase).
  Ratchet green by folding, never by raising.

## Red-until-built tests (spec surfaces declared but not yet covered)

A spec surface that exists in [`spec.md`](spec.md) but is not yet built ships a **failing** placeholder test, so
an unbuilt surface is visibly red, never silently absent. A green suite over a half-built spec is not done.

| Spec surface | Test | State |
|---|---|---|
| INV-COMPLETE (one ordered field, all views agree) | list/board/shared-view agreement over random tasks | green (M1) |
| INV-REOPEN (cascade + cycle guard) | build chain A -> B -> C, reopen A, assert B and C drop to `in_progress`; build cycle A -> B -> A, assert reopen terminates | green (M1) |
| INV-MIGRATION (no work un-completed) | re-run migration on a DB copy, assert the `done = true` / `status = 'open'` cohort all land on `done` | green (M1) |
| Share-link resolve fails closed (council build action) | attack an expired token and a revoked token, assert both denied at the resolve path | green (M1) |
| Blocking-edge editing (M2 scope) | create/remove `blockedBy` edges with a spec'd cycle policy | **red until built** (M2) |

## Supply-chain (every commit, cheap)

- `npm audit --omit=dev` runs in CI; a new high or critical advisory denies. (The deep, risk-targeted security
  audit is a milestone-close concern, not a per-commit gate; see the milestone sign-off.)

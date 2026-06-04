# 0002 - Collapse completion to one ordered status

> **Beat type:** decision (a load-bearing choice; this records the choice, the alternatives, and why).
> Decision beats lead with the call, then justify it. If this is ever reversed, a later entry supersedes it; this
> one is never silently rewritten.

**Date:** 2026-06-01
**Phase:** distil (spec)
**Touches:** [`../_harvest/task-model.md`](../_harvest/task-model.md),
[`../adr/ADR-0001-one-task-status-lattice.md`](../adr/ADR-0001-one-task-status-lattice.md)
**Supersedes:** nothing. **Superseded by:** nothing (current).

---

## The decision
Replace Tasky's three completion mechanisms (`done` boolean, `status` enum, `archivedAt` timestamp) with **one
ordered status**, a small lattice with a single direction of "doneness":

```
open  ->  in_progress  ->  done  ->  archived
                                \->  deleted   (explicit terminal, was overloaded onto archivedAt)
```

"Is this task done?" becomes one question with one answer: `status >= done`. The auto-reopen rule is lifted out
of its event handler and stated as a **spec invariant** over this status (with its cycle guard kept). Promoted to
[`ADR-0001`](../adr/ADR-0001-one-task-status-lattice.md) because every later piece of work will cite it.

## Alternatives considered

**A. Keep all three, add a sync layer that keeps them in agreement.**
Rejected. This is consolidation's opposite: three sources of truth plus a fourth thing to keep them aligned. The
harvest already proved convention does not hold them together (`task.ts:18/21/24` drift in real data). More
machinery to maintain the very inconsistency we are trying to delete. One source of truth per fact: there should
be one "doneness," not three plus a referee.

**B. Keep the `status` enum, drop the other two, but leave it unordered.**
Rejected. Dropping `done` and `archivedAt` is right, but an *unordered* enum is what let `done` and `open`
coexist in the first place. Without an order, "is it done?" still needs a hand-maintained set of "which values
count as done," which drifts the same way. The **order** is the load-bearing part, not just the single field.

**C. A separate `completedAt` timestamp as the one truth (done iff non-null).**
Rejected, but it was close. It collapses to one field cleanly. It loses `in_progress` (a state the board genuinely
uses, per `Board.tsx:55`) and it cannot express `archived` vs `deleted` without re-adding fields, which is how we
got here. The lattice keeps the states the harvest proved are real and still gives one ordered answer.

## Why the lattice
- **One question, one answer.** `status >= done` is the single completion predicate. The list/board/shared-view
  disagreement (harvest section 1) cannot recur, because there is nothing to disagree with.
- **The auto-reopen rule becomes statable.** As an invariant: *if a task drops below `done`, every task it blocks
  drops to at most `in_progress`.* That is a clean rule over an ordered set; it was unstateable while "done" was
  three things. Cycle guard preserved (harvest `onTaskReopen.ts:27`).
- **`archived` and `deleted` stop being overloaded.** They are distinct terminal states, killing the
  "archived sometimes means deleted" conflation at `share.ts:88`.
- **Migration is mechanical, not lossy.** A one-time map from each legacy triple to a single status (recorded in
  the ADR), keeping the real intent of each historical state.

## Cost I am accepting
A data migration over existing rows, and every read of `done`/`archivedAt` in the codebase has to move to
`status`. That is real work, but it is *finite and one-time*, versus the *ongoing* cost of three drifting truths.

## Next
Write the spec invariant and the migration map into [`ADR-0001`](../adr/ADR-0001-one-task-status-lattice.md);
build the lattice as the M1 walking skeleton. The separate share-link security question (harvest section 4) is a
genuine hard fork and goes to a council, not a sentence.

-> [`../adr/ADR-0001-one-task-status-lattice.md`](../adr/ADR-0001-one-task-status-lattice.md)

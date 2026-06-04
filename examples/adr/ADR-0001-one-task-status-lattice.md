# ADR-0001: One ordered task-status lattice

> **What an ADR is.** A short, durable record of a load-bearing decision, promoted from a journal beat so the big
> calls are easy to find and cite. Journal entries narrate; ADRs are the citable record. This one is referenced
> by the M1 sign-off and every later piece of status-touching work.

- **Status:** Accepted
- **Date:** 2026-06-01
- **Deciders:** rebuild lead (LDD principal)
- **Reasoned in:** [`../metacognition/0002-collapse-completion-to-one-status.md`](../metacognition/0002-collapse-completion-to-one-status.md)
- **Grounded in:** [`../_harvest/task-model.md`](../_harvest/task-model.md)
- **Supersedes / superseded by:** none

---

## Context
Legacy Tasky expresses "this task is done" three different ways: a `done` boolean (`src/models/task.ts:18`), a
`status` enum (`:21`), and an `archivedAt` timestamp (`:24`). Different surfaces trust different ones (the list
trusts the boolean, the board trusts the enum, the shared view trusts the timestamp), and nothing keeps them in
agreement. The harvest found real tasks in contradictory states, so this is a confirmed defect, not a hypothetical
one. Separately, a load-bearing rule ("a task auto-reopens if a blocking task reopens") lives only in one event
handler and half-fires because of the same drift.

## Decision
Replace the three mechanisms with **one ordered status**: a small lattice with a single direction of "doneness."

```
open  ->  in_progress  ->  done  ->  archived
                                \->  deleted
```

- The single completion predicate is `status >= done`. There is no other source of "doneness."
- `archived` and `deleted` are **distinct terminal states**, ending the overloading of `archivedAt` (which today
  means both "done and old" and, at `src/api/share.ts:88`, "deleted").
- The auto-reopen rule is lifted out of the event handler and stated as a spec **invariant** over this status
  (below), with the legacy cycle guard preserved.

### The invariant (promoted from `src/events/onTaskReopen.ts`)
> **INV-REOPEN.** If a task's status drops below `done`, then every task it blocks drops to at most
> `in_progress`, applied recursively over `blockedBy`, with a visited-set cycle guard so a blocking cycle
> terminates.

This is the harvested intent made explicit and testable, instead of buried in code nobody can find.

### Migration map (one-time, lossless of intent)
Each legacy triple maps to exactly one status:

| Legacy state | New `status` |
|---|---|
| `archivedAt` set, and used as "deleted" (`share.ts:88` path) | `deleted` |
| `archivedAt` set (the archive job path) | `archived` |
| `done = true` OR `status = 'done'` (either truth) | `done` |
| `status = 'in_progress'` | `in_progress` |
| everything else | `open` |

"Either truth counts as done" is deliberate: it preserves every task a user ever completed by *any* of the three
old paths, so the migration cannot silently un-complete work.

## Consequences

**Positive**
- "Is this task done?" has one answer everywhere. The list/board/shared-view disagreement is structurally
  impossible after this, not merely fixed.
- The auto-reopen rule is now a named, testable invariant (INV-REOPEN) rather than a hidden handler.
- `archived` vs `deleted` is unambiguous.
- The model shrinks: three fields plus a graph become one ordered field plus the graph.

**Negative / cost**
- A one-time data migration over existing rows (the map above).
- Every read of `done` and `archivedAt` across `src/` must move to `status`. The harvest located these
  (`TaskList.tsx:73`, `Board.tsx:55`, `jobs/archive.ts:34`, `api/share.ts:88`), so the change set is known and
  bounded.
- The nightly archive job (`jobs/archive.ts:34`) must be re-keyed from `done` to `status >= done`.

**Neutral / follow-on**
- The shared read-only view (`src/api/share.ts`) is touched by this only at `:88` (the "deleted" conflation). Its
  *security* (no-expiry share links) is a separate decision, settled by court in
  [`../court/share-link-expiry-verdict.md`](../court/share-link-expiry-verdict.md).

## Compliance
M1 ("the task status lattice") is the build of this ADR. The M1 sign-off
([`../M1-signoff.md`](../M1-signoff.md)) verifies the lattice, the migration map, and INV-REOPEN against this
record.

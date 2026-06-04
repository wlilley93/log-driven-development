# Spec: Tasky core (the task model)

> **What this is.** The distilled, minimal spec for Tasky's task model: the smallest complete set of primitives
> and invariants that solves the domain, plus the legacy behaviour deliberately dropped (each with a reason).
> This is an excerpt: it covers the completion-and-blocking core that M1 builds, not the whole app. The spec is
> the source of truth; the code is kept in sync with it, not the other way around.

**Status:** accepted (for the M1 core)  **Last harmonized:** 2026-06-02
**Draws from:** [`_harvest/task-model.md`](_harvest/task-model.md)
**Decided in:** [`adr/ADR-0001-one-task-status-lattice.md`](adr/ADR-0001-one-task-status-lattice.md)

---

## Primitives

The minimal set of shapes the core is built on. If a shape is not needed to satisfy an invariant below, it does
not belong here.

- **Task** = `{ id, title, status, blockedBy: TaskId[], createdAt, updatedAt }`.
- **status** is a single **ordered lattice**, one direction of "doneness":

  ```
  open  ->  in_progress  ->  done  ->  archived
                                  \->  deleted   (explicit terminal)
  ```

  Completion is one question with one answer: a task is done iff `status >= done`. There is no `done` boolean and
  no `archivedAt` field; both are gone (see Deliberately dropped). `archived` and `deleted` are **distinct
  terminal states**, ending the old overloading where one nullable timestamp meant completion, age, and "deleted"
  at once.

- **blockedBy** is the set of task IDs that block this task. It is read-only in this core (M1 only consumes it via
  INV-REOPEN); editing the edges is M2's scope.

---

## Invariants (numbered, testable)

Each is a property a verifier and a test can both attack. Each is true or false, never "should".

- **INV-COMPLETE.** A task is complete if and only if `status >= done`. The list view, the board view, and the
  shared view all read this one ordered field, so they can never disagree about whether a task is done. (This is
  the structural fix for the harvested list-vs-board-vs-shared-view drift.)

- **INV-REOPEN.** If a task's `status` drops below `done`, then every task it blocks drops to at most
  `in_progress`, applied recursively over `blockedBy`, with a visited-set cycle guard so a blocking cycle
  terminates rather than looping. (This is the harvested auto-reopen rule, promoted out of
  `src/events/onTaskReopen.ts` and made explicit. The cycle guard is preserved, not reinvented.)

- **INV-MIGRATION.** Every legacy row maps to exactly one `status` by the ADR's migration map, and either old
  truth counting as done (`done = true` OR `status = 'done'`) preserves every task a user ever completed by any
  of the three old paths. The migration never silently un-completes work.

---

## Deliberately dropped

The legacy behaviour the rebuild is **not** carrying forward, each with its reason. Dropping is auditable, so
nobody re-adds a dropped thing as a "missing feature".

- DROP the **`done` boolean** (`src/models/task.ts:18`), because it duplicated the status enum and was the source
  of the list-vs-board disagreement. INV-COMPLETE replaces it with one ordered source of truth.
- DROP **`archivedAt` as a status-bearing field** (`src/models/task.ts:24`), because it was overloaded with three
  jobs (completion, age, and "deleted"). `archived` becomes a terminal status and `deleted` its own explicit
  state; age-based archiving becomes a separate concern keyed off `status >= done`.
- DROP the **auto-reopen rule's home in the event handler** (`src/events/onTaskReopen.ts` as the only record of
  the requirement). The behaviour is kept (INV-REOPEN); only its hiding place is dropped. The `visited` cycle
  guard is explicitly **not** dropped.

> Out of scope for this excerpt, handled elsewhere: the share-link security defect (no expiry, no revocation) is
> a genuine hard fork settled by council in [`council/share-link-expiry-verdict.md`](council/share-link-expiry-verdict.md),
> not in this spec.

---

## Closure sweep (definition of done)

The automated check the spec-and-build loop runs each pass. "Done" is the sweep reporting zero gaps, not "the
tests pass".

- [ ] Every invariant above has at least one test that attacks it, and it is green (including an INV-REOPEN test
      that builds a blocking cycle and confirms the cascade terminates).
- [ ] No primitive in the code is absent from this spec, and no spec primitive is unbuilt (no orphans either way).
- [ ] Every "deliberately dropped" item is actually gone from the code: the sweep greps `src/` for reads of
      `\.done` and `archivedAt` as stored state and fails if any survive outside the migration layer. This is how
      INV-COMPLETE stays true as new code lands (a re-introduced second completion path trips the sweep, and the
      duplication ratchet, before it merges).
- [ ] Duplication ratchet holds; no over-long function or leaked abstraction in the new surface (a single
      `isDone(status)` reader, not the `status >= done` comparison inlined per view).

# Intent ledger: the task model (completion + blocking)

> **What this is.** An LDD intent ledger. It harvests *what the old Tasky code meant* about marking a task done
> and about blocking relationships, with provenance for every claim. Provenance or it does not go in. This ledger
> is the input to the spec; the DROP list at the bottom is what the rebuild will deliberately leave behind.

Area: task completion and blocking
Harvested from: legacy Tasky (`src/`, commit `a3f91c2`)
Status: harvested, feeds spec for M1 (the status lattice)

---

## 1. The completion tangle: three mechanisms, all half-used

Tasky has **three** independent ways to express "this task is done." They were added at different times, never
reconciled, and different parts of the app trust different ones. This is the central mess.

### 1a. The `done` boolean
- `src/models/task.ts:18` declares `done: boolean` on the Task record, defaulting to `false`.
- `src/api/tasks.ts:142` is the original "complete" endpoint: it sets `done = true` and nothing else.
- The list view at `src/web/TaskList.tsx:73` filters open tasks with `!task.done`, so the **list trusts the
  boolean** and ignores the other two mechanisms entirely.
- **Evidence it has drifted:** `src/api/tasks.ts:201` (the newer bulk-complete path) sets `status` but never
  touches `done`, so a bulk-completed task stays visible in the list. This is a real bug users hit.

### 1b. The `status` enum
- `src/models/task.ts:21` declares `status: 'open' | 'in_progress' | 'done'`, defaulting to `'open'`.
- Added later than the boolean, for the board view. `src/web/Board.tsx:55` groups columns by `status` and is
  blind to `done`: a task with `done = true` but `status = 'open'` shows in the Open column.
- `src/api/tasks.ts:201` (bulk complete) and `src/api/tasks.ts:230` (the drag-to-column handler) write `status`.
- **No code keeps `done` and `status` in agreement.** They are two separate truths.

### 1c. The `archivedAt` timestamp
- `src/models/task.ts:24` declares `archivedAt: Date | null`, default `null`.
- Intended for "hide finished tasks after a while," set by `src/jobs/archive.ts:34` (a nightly job that archives
  tasks where `done === true` AND `updatedAt` is older than 30 days).
- `src/web/TaskList.tsx:73` also hides any task with a non-null `archivedAt`, so archiving is **a third, implicit
  completion signal** layered on the boolean.
- **Conflation:** "archived" currently means both "done and old" (the job) and, in at least one place
  (`src/api/share.ts:88`, the shared read-only view), is treated as "deleted." Two meanings, one field.

### Why this matters
The same task can read as done in the list (boolean), open on the board (enum), and present-or-gone in the shared
view (timestamp). There is no single answer to "is this task done?" That is the thing the spec has to fix.

---

## 2. The buried rule: auto-reopen on blocker reopen

This is the load-bearing rule that is written down **nowhere except one event handler**, and it is exactly the
kind of intent a naive rewrite drops.

- `src/models/task.ts:30` declares `blockedBy: string[]` (IDs of tasks that block this one).
- `src/events/onTaskReopen.ts:12` is the only place the rule lives. In prose: **when a task is reopened, every
  task it was blocking is also reopened**, recursively, following the `blockedBy` graph.
- The handler sets `done = false` on each dependent (line 19) but, tellingly, **does not reset `status` or
  `archivedAt`** (the drift from section 1 again): an auto-reopened task can have `done = false`,
  `status = 'done'`, and a stale `archivedAt`. So the rule half-fires.
- **Cycle handling:** `src/events/onTaskReopen.ts:27` has a `visited` set, so a blocking cycle terminates rather
  than looping forever. Keep this. (Confirmed by reading; there is no test for it.)
- **Provenance of intent:** there is a one-line code comment at `src/events/onTaskReopen.ts:9` reading
  `// if a blocker comes back, the thing it was blocking isn't really done`. That comment is the *only* written
  statement of this requirement anywhere in the project.

### Why this matters
People rely on this. If you finish a task, then its blocker turns out to be unfinished and reopens, your task
should not silently stay "done." The rule is correct intent trapped in code. **It must survive the rebuild as an
explicit spec invariant**, not as an event handler nobody can find.

---

## 3. The data shapes (as they exist today)

```ts
// src/models/task.ts (harvested verbatim, lines 16-31)
interface Task {
  id: string;
  title: string;
  done: boolean;                                   // :18  mechanism 1
  status: 'open' | 'in_progress' | 'done';         // :21  mechanism 2
  archivedAt: Date | null;                         // :24  mechanism 3 (and "deleted" in one place)
  blockedBy: string[];                             // :30  drives the auto-reopen rule
  createdAt: Date;
  updatedAt: Date;
}
```

Observed real states in the data (sampled, `src/scripts/audit.ts` run against the dev DB):
- `done = true`, `status = 'open'`: tasks completed via the old endpoint, never moved on the board. (~common.)
- `done = false`, `status = 'done'`: bulk-completed tasks (the boolean was never written). (~common.)
- `archivedAt` set with `done = false`: auto-reopened-but-stale tasks (section 2's half-fire). (rare, real.)

The spread of inconsistent states is the proof that three mechanisms cannot be kept in agreement by convention.

---

## 4. DROP list (deliberately left behind, with reasons)

The rebuild keeps the *intent* and drops the *mechanisms*. Each drop is a decision; the reasons are recorded so a
future reader knows it was deliberate, not forgotten.

| Drop | Reason | Replaced by |
|---|---|---|
| The `done` boolean (`task.ts:18`) | Redundant with `status`; the source of the list-vs-board disagreement. | A single ordered `status`. |
| The `status` enum *as a free string* (`task.ts:21`) | The *values* are kept, but an unordered enum let `done` and `open` coexist. | An **ordered status lattice** (one direction of "doneness"). |
| `archivedAt` as a completion signal (`task.ts:24`) | Overloaded: completion + age + "deleted." Three jobs in one nullable field. | `archived` becomes a *terminal status*, not a parallel field; "deleted" becomes its own explicit state. |
| The nightly archive job's reliance on `done` (`jobs/archive.ts:34`) | It keys off the mechanism we are dropping. | Re-key the job off the new status. |
| The auto-reopen *event handler as the home of the rule* (`onTaskReopen.ts`) | The rule must not live only in code nobody can find. | Keep the behaviour; promote the rule to a **named spec invariant**. (Do NOT drop the `visited` cycle guard.) |

**Not dropped (kept intent):**
- The auto-reopen behaviour itself (section 2): preserved as a spec invariant.
- The cycle guard (`onTaskReopen.ts:27`): preserved as part of that invariant.
- The shared read-only view's *existence* (`src/api/share.ts`): kept, but its security is a separate fork (see
  [`../court/share-link-expiry-verdict.md`](../court/share-link-expiry-verdict.md)).

---

## 5. Handoff to the spec

The spec move this ledger forces: **collapse the three completion mechanisms into one ordered status, and lift
the auto-reopen rule to an explicit invariant over that status.** The decision is reasoned in
[`../metacognition/0002-collapse-completion-to-one-status.md`](../metacognition/0002-collapse-completion-to-one-status.md)
and recorded in [`../adr/ADR-0001-one-task-status-lattice.md`](../adr/ADR-0001-one-task-status-lattice.md).

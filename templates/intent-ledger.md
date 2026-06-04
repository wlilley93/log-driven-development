<!--
TEMPLATE: Intent ledger (the harvest artefact).
WHEN: one per area of the legacy code, written during the harvest phase, before you build anything.
HOW: read the old code and write down what it MEANT, with provenance (file:line) for every claim.
     Provenance or it does not go in. If you cannot point at the evidence, you are guessing, and guesses
     do not belong in a ledger. Copy this file, rename it for the area (e.g. _harvest/task-completion.md),
     delete this comment, fill every section. Keep it free-text and short.
-->

# Intent ledger: <area name, e.g. task completion>

**Source:** <which part of the legacy tree this covers, e.g. src/tasks/, src/db/tasks.ts>
**Harvested:** <date> by <agent or person>
**Provenance convention:** every claim ends with `(file:line)` pointing at the real legacy code it came from.
A line with no citation is a guess and must be removed or marked `(UNVERIFIED)` for someone to ground-truth.
**Risk surface:** <auth | tenant | money | crypto | external | none> (one or more). This drives the SECURITY-phase
risk trigger and the Tier-2 dispatch in the ownership matrix: pick `none` only when this area touches no auth,
no multi-tenant isolation, no money, no crypto, and no externally-reachable surface. See `docs/invariants.md`
LDD-INV-15 (security and structural intent are first-class harvest registers).

---

## The precious rules

The domain logic, edge cases, and behaviour people actually rely on. One rule per bullet, each grounded.

- <rule, stated plainly> `(path/file.ts:line)`
- Example (Tasky): A task auto-reopens if a blocking task reopens. The reopen cascades through the blocks
  graph, depth-first, and is silent (no notification). `(src/tasks/reopen.ts:88)` `(src/tasks/blocks.ts:31)`
- Example (Tasky): "Completion" is read in three different places three different ways: the `done` boolean
  `(src/models/task.ts:22)`, the `status` enum value `STATUS.DONE` `(src/tasks/status.ts:14)`, and a
  non-null `archivedAt` timestamp `(src/tasks/archive.ts:47)`. The list view trusts `done`; the API trusts
  `status`; the export trusts `archivedAt`. They drift. This is the single most important thing to resolve
  in the spec. `(src/views/list.tsx:130)` `(src/api/tasks.ts:204)` `(src/export/csv.ts:60)`

## The process / procedure

REQUIRED (LDD-INV-18). The step-by-step procedure one altitude BELOW the structure: what a human or operator
actually does, in order, with the rules/arithmetic/gates/contents that govern each step. The precious-rules and
data-shapes sections above capture the SYSTEM (the enums, shapes, state-machine names); this section captures the
PROCESS (how the domain is actually driven). A ledger whose only home for the real procedure is source you did not
open is not done: an empty PROCESS section is incomplete by construction and must not be rolled up as
"well-grounded". If your area is genuinely structure-only (a pure data model with no procedure), say so
explicitly and why - do not leave this blank.

- <the procedure, as ordered steps + the rule/algorithm/deadline/gate/contents at each> `(path/file.ts:line)`
- Example (Tasky): The "archive a completed project" procedure: (1) every task must be `done` or the action is
  refused `(src/projects/archive.ts:40)`; (2) on archive, child tasks are stamped `archivedAt = now` depth-first
  `(src/projects/archive.ts:55)`; (3) a 30-day undo window is recorded, after which a nightly job hard-deletes
  `(src/jobs/purge.ts:22)`. The 30-day rule and the depth-first order are the precious procedure, not visible from
  the `Project` shape alone.
- Example (anti-pattern): writing only "Projects have an `archived` status `(src/models/project.ts:14)`" here is a
  SYSTEM claim masquerading as PROCESS; it names the enum and withholds the procedure. INV-18 fails it.

## The data shapes

The shapes the old code actually persists and passes around (not the shape you wish it had). Note the messy bits.

- <shape name>: <fields and types as they really are> `(path/file.ts:line)`
- Example (Tasky): `Task { id, title, done: boolean, status: 'open'|'doing'|'done', archivedAt: Date|null,
  blockedBy: id[] }` , three overlapping completion fields, all half-used. `(src/models/task.ts:10)`

## Security and trust notes

Anything touching auth, sharing, money, or external reach. Flag smells even if you are not fixing them yet.

- <observation> `(path/file.ts:line)`
- Example (Tasky): SECURITY SMELL: the share link has no expiry and no revocation; the token is a plain
  base64 of the task id, so links are guessable. Must be addressed in the rebuild, not carried over.
  `(src/share/link.ts:19)`

## What to DROP, and why

The sprawl you are deliberately not rebuilding. Dropping is a decision: record the reason so it is auditable.

- DROP <thing> because <reason>.
- Example (Tasky): DROP two of the three completion paths. Keep one canonical representation in the spec
  (see spec invariant on completion). Reason: the three paths are the bug, not a feature; consolidating is
  the whole point of the rebuild.
- Example (Tasky): DROP the second auth code path (the bolted-on session check in `src/api/middleware.ts`).
  Reason: duplicate of the primary auth, diverged, and is the more permissive of the two.

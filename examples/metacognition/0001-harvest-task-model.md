# 0001 - Harvest the task-completion model

> **Beat type:** action (a unit of work landed; this records what was done and what it found).
> **Template:** every journal entry is `what I did` + `what I found / decided` + `why` + `next`. Action beats
> lead with the work; decision beats (see `0002`) lead with the choice and its alternatives.

**Date:** 2026-06-01
**Phase:** harvest (pre-spec)
**Touches:** [`../_harvest/task-model.md`](../_harvest/task-model.md)

---

## What I did
Ran the harvest pass over Tasky's task-completion and blocking logic. Concretely: read `src/models/task.ts`,
greped for every read and write of `done`, `status`, and `archivedAt` across `src/`, traced the two complete
endpoints and the board drag handler, and read the one event handler that touches blocking. Wrote the findings
into the intent ledger `_harvest/task-model.md` with `src/...:line` provenance on every claim. Ran the existing
`src/scripts/audit.ts` against the dev DB to sample real task states.

This was a single harvesting agent's return, integrated by the main loop. The agent returned free text plus
provenance; I (the orchestrator) verified the line references against the tree before writing the ledger. No
claim without a cite made it in.

## What I found
1. **"Done" means three different things.** A `done` boolean, a `status` enum, and an `archivedAt` timestamp,
   each trusted by a different surface (list trusts the boolean, board trusts the enum, the shared view trusts the
   timestamp). Nothing keeps them in agreement, and the audit script found real tasks in mutually contradictory
   states (`done = true` / `status = 'open'`, and the reverse). This is the central mess, confirmed by ground
   truth, not guessed.
2. **A load-bearing rule lives only in one handler.** `src/events/onTaskReopen.ts` implements "reopening a task
   reopens everything it was blocking," recursively, with a cycle guard. The only written statement of this
   requirement is a single code comment on line 9. A naive rewrite would have dropped it silently.
3. The rule itself half-fires today (it clears `done` but not `status`/`archivedAt`), which is just the
   three-mechanism drift showing up again.

## Why this matters (and why I stopped here)
The whole point of the harvest is to surface intent that only exists as code *before* anyone designs the
replacement. I deliberately did **not** decide the fix in this beat. Harvest records what *is*; the design choice
(what to *do* about it) is its own decision with its own alternatives, so it gets its own beat. Mixing "what the
code means" with "what I'm going to build" is how provenance gets contaminated with opinion.

## Next
Decide the completion model. The harvest's DROP list already points at "collapse to one ordered status," but that
is a real design call with alternatives, so it goes to a decision beat next.

-> [`0002-collapse-completion-to-one-status.md`](0002-collapse-completion-to-one-status.md)

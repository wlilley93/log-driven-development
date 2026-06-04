<!--
TEMPLATE: Architecture Decision Record (ADR).
WHEN: a journal decision graduates to an ADR once it is load-bearing: hard to reverse, shapes other work,
      or future readers will need to find and cite it without digging through the journal. Reversible
      decisions stay as journal entries; do not promote everything (an ADR is heavier on purpose).
HOW: copy this file, number it (e.g. adr/0007-canonical-task-completion.md), delete this comment, fill it.
     Keep it to a page. Link back to the journal entry it grew from.
-->

# ADR-<0007>: <short decision title, e.g. One canonical task-completion field>

**Status:** <Proposed | Accepted | Superseded by ADR-NNNN>
**Date:** <date>
**From journal:** <seq of the metacognition entry this graduated from, e.g. 0042>

## Context

<The forces that made this a decision worth recording. State the problem and the constraints plainly. Cite
the harvest where the legacy behaviour came from.>

Example (Tasky): The legacy code represents completion three ways (`done` boolean, `status` enum,
`archivedAt` timestamp) and they drift, producing the list/API/export disagreement harvested in
_harvest/task-completion.md. The rebuild needs exactly one source of truth for "is this task complete?".

## Decision

<The decision, in one or two sentences. Unambiguous. This is the part future code is held against.>

Example (Tasky): Completion is defined solely by the `status` enum reaching `done`. The `done` boolean and
`archivedAt` are removed as stored state; any view needing a boolean or a timestamp derives it from status
and the status-change log.

## Consequences

What this buys and what it costs. Be honest about the minus column.

**Plus**
- <good consequence>
- Example: one source of truth; list, API, and export can no longer disagree.
- Example: the `doing` in-progress state people use is preserved.

**Minus**
- <cost or risk accepted>
- Example: a data migration is required to backfill `status` from the old three fields; ambiguous rows
  (done=true but status=open) need a documented tie-break rule.
- Example: any external integration reading `done` directly breaks and must move to `status`.

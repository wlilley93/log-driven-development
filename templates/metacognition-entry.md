<!--
TEMPLATE: Metacognition journal entry (one beat).
WHEN: every time a coherent unit of work lands (a decision, an action, or an event worth recording).
HOW: append a new file, newest last; one entry per beat; never rewrite an old entry. If you reverse an
     earlier decision, write a NEW entry that supersedes it and link back, so history stays honest.
     ONE WRITER: only the orchestrator (main loop) writes the journal. Spawned agents RETURN their
     what/why as text; they do not journal themselves (they would collide). Copy this file, name it by
     sequence (e.g. metacognition/0042-pick-canonical-completion.md), delete this comment, fill it in.
-->

---
seq: <0042>
date: <date>
type: <decision | action | event>
title: <short imperative title, e.g. Pick one canonical task-completion field>
supersedes: <seq of an entry this reverses, or omit>
---

## What

<Plainly, what happened this beat. For an action: what was built or changed. For an event: what occurred
and what triggered this entry.>

Example (Tasky): Chose a single canonical representation for task completion to replace the three drifting
paths harvested into _harvest/task-completion.md.

## Why

<For a DECISION, fill all three. For an action/event, a sentence or two of reasoning is enough.>

- **Chosen:** <what was decided>
  Example: completion = `status` enum reaching `done`. The `done` boolean and `archivedAt` become derived
  views, not separate sources of truth.
- **Alternatives considered:** <the real options, not strawmen>
  Example: (a) keep `done` boolean as canonical, simplest but loses the in-progress state people use;
  (b) keep `archivedAt`, but archived and done are genuinely different states.
- **Why this one:** <the deciding reason, grounded if possible>
  Example: the API and most call sites already trust `status` (src/api/tasks.ts:204); making it canonical
  moves the fewest call sites and preserves the `doing` state. The other two regenerate from it cleanly.

## Outcome and links

<What this beat produced and where to follow it.>

- Spec: <the invariant or section this touches, e.g. spec invariant INV-3 (single completion source)>
- Code: <files written/changed>
- Graduated to ADR: <ADR id, if this decision became load-bearing enough to record formally, else "no">
- Intent ledger: <_harvest/... this resolves or draws from>

<!--
TEMPLATE: Council verdict (the deliberation record).
WHEN: a high-stakes, hard-to-reverse fork, or an honest retrospective/pre-mortem. NOT for a reversible
      decision (that gets one decisive sentence, not a panel). A council must END IN A BUILD ACTION OR A
      KILL, never another doc that defers.
HOW: copy this file (e.g. councils/0003-completion-model.md), delete this comment, fill it. Each seat is a
     distinct lens and must cite real evidence from the tree, or it is ignored. Record the surviving
     dissent: it is the standing of any future appeal. See skills/council/SKILL.md for the appeal tiers.
-->

# Council: <the decision under deliberation>

**Tier:** <Council (first instance) | Appeals Council | Supreme Council>
**Convened:** <date>  **Question:** <the one hard fork being decided, stated as a question>
**Lower-court record:** <for Appeals/Supreme: link the full record being reviewed; omit for first instance>

## The seats (distinct lenses, run independently)

Each seat ground-truths first and leads with the blunt truth. Add/swap lenses to fit the question.

### Seat: <project health>
- **Verdict:** <blunt one-liner>
- **Grounded in:** `<evidence, e.g. grep/file:line/test run>`
- Example (Tasky): "Keep `status` as canonical. 70% of call sites already read it." `(grep status: 41
  hits vs done: 12)`

### Seat: <devil's advocate / pre-mortem>
- **Verdict:** <blunt one-liner>
- **Grounded in:** `<evidence>`
- Example (Tasky): "This fails if any external integration reads `done` directly. Find them before
  committing." `(src/api/webhooks.ts:55 still emits done)`

### Seat: <security lens>
- **Verdict:** <blunt one-liner>
- **Grounded in:** `<evidence>`
- Example (Tasky): "Out of scope for completion, but note the auto-reopen cascade can flip a task back to
  open silently; make sure derived `archivedAt` clears on reopen." `(src/tasks/reopen.ts:88)`

### Seat: <advocate of the named alternative>
- **Verdict:** <blunt one-liner>
- **Grounded in:** `<evidence>`

## Synthesis

<The orchestrator reconciles the seats (they will disagree), states the through-line, and converts it into
a committed change or a kill. This is the decision. It must not merely defer.>

- **Through-line:** <the reconciled position>
- **Decision (build action or kill):** <the committed action>
- Example (Tasky): BUILD. Canonical completion = `status`. First task: migrate the webhook emitter off
  `done` (the pre-mortem's failure mode) before the rest. Graduate to ADR-0007.

## Surviving dissent

<The strongest disagreement that did not win, recorded, never buried. It is the standing of any appeal.>
- <dissent> (seat: <which>)
- Example (Tasky): the project-health seat held that `archivedAt`-as-canonical would have needed fewer
  migration steps; overruled because archived and done are genuinely different states.

## Appeal path

<Standing required to escalate. "I'd have designed it differently" is not standing.>
- This verdict stands unless appealed with standing: principal disagrees, the surviving dissent is
  load-bearing and unresolved, or new ground-truth contradicts a relied-upon point.
- Next tier: <Appeals Council on the merits | Supreme Council only on a point of invariant/method law>.

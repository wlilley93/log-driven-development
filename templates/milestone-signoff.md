<!--
TEMPLATE: Milestone sign-off (the 5-phase close record).
WHEN: at the end of every milestone. The milestone is NOT done until all five phases run and this record
      exists. PLAN is mandatory: the next build does not start until the next steps are planned here.
HOW: copy this file (e.g. signoffs/M3-completion-rebuild.md), delete this comment, fill every phase with
     REPRODUCED evidence (the actual command + the actual result), not "looks fine". The verdict is the
     orchestrator's judgement after ground-truthing, never a worker's self-report.
-->

# Milestone sign-off: <M3 - task completion rebuilt>

**Verdict:** <PASS | PASS-WITH-FIXES | NEEDS-WORK>
**Date:** <date>  **Signed off by:** <orchestrator>

## BUILD

<What landed this milestone. Formatter/linter/tests green, with the evidence.>
- Scope delivered: <one line>
- Evidence: `<cmd, e.g. npm test>` -> <result, e.g. 142 passed, 0 failed>
- Example (Tasky): canonical `status` completion built; `done`/`archivedAt` now derived. Migration 0009
  backfills `status`. `npm test` -> 142 passed.

## STRUCTURE

<Structural scan of the new surface. Does the duplication ratchet hold? Any over-long function, God-object,
leaked abstraction? Escalate to a full refactor only on flagged debt.>
- Evidence: `<cmd>` -> <result>
- Flagged debt: <none, or what and the plan>
- Example (Tasky): duplication ratchet held; the three old completion read-paths are gone (one reader now).

## SECURITY

<Cheap supply-chain checks every milestone. The deep audit is risk-targeted: run it where risk lives.>
- Supply-chain: `<cmd, e.g. npm audit>` -> <result>
- Risk-targeted audit run? <yes/no + why> on <surface>
- Example (Tasky): this milestone did not touch auth or sharing, so no deep audit. The share-link-expiry
  smell (_harvest/sharing.md) is tracked for the sharing milestone, see Deferred.

## VERIFY

<An independent adversarial verifier re-ran from clean and tried to break the milestone's invariants.>
- Verifier ran from clean: `<cmd>` -> <result>
- Attacks attempted on the invariants: <what was tried>
- Example (Tasky): verifier tried a row with `done=true, status=open` post-migration; tie-break rule held,
  resolved to `done`. Tried list/API/export agreement on 1k random tasks: all three agreed.

## PLAN (mandatory)

<The next steps. The milestone does not close without this.>
- Next milestone scope: <one line>
- Sequence and risks: <ordered, with the main risk>
- The single next move: <the very next concrete action>
- Example (Tasky): next is M4 (sharing + share-link expiry), highest risk is the guessable-token smell;
  next move is to harvest _harvest/sharing.md fully before building.

## Deferred items

<Anything consciously not done this milestone, with where it is tracked. Deferring is a decision; record it.>
- <item> -> tracked in <milestone / ADR / issue>
- Example (Tasky): share-link expiry deferred to M4 (sharing milestone).

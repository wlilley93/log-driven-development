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
leaked abstraction? Escalate to a full refactor only on flagged debt. The owner at this phase is the
closure-gate (continuous) plus `vibeclean` as its structure edge; see the two-tier(+) ownership matrix in
docs/systems.md (system 7).>
- Evidence (record the ACTUAL command + its ACTUAL result, never "looks fine", LDD-INV-5):
  `<cmd, e.g. python3 tools/closure-gate/closure_gate.py --config ./tools/closure-gate/closure-gate.toml --paths .>`
  -> <result, e.g. closure-gate: clean (8 gates); vibeclean structure_scan: 0 regressions>
- Flagged debt: <none, or what and the plan>
- Example (Tasky): `closure-gate ... --paths .` -> clean, 8 gates; duplication ratchet held; the three old
  completion read-paths are gone (one reader now).

## SECURITY

<The continuous fast scan runs every milestone (it ran on every commit); the deep audit is risk-triggered:
run it where risk lives. The owners and triggers are fixed by the two-tier(+) ownership matrix in
docs/systems.md (system 7): `vibescan --fast` continuous, `vibescan .` + the security-suite methodology
(skills/security/, with `vibeaudit` as its engine) when risk-triggered.>
- Continuous fast scan (record the ACTUAL command + its ACTUAL result, LDD-INV-5):
  `<cmd, e.g. vibescan --fast .>` -> <result, e.g. 0 new findings>
- Risk-triggered deep audit run? <yes/no + why> on <surface, per the intent ledger's Risk surface field>.
  If yes, record the command + result: `<cmd, e.g. vibescan .>` -> <result>
- Example (Tasky): `vibescan --fast .` -> 0 new findings. This milestone did not touch auth or sharing
  (Risk surface: none), so no deep audit. The share-link-expiry smell (_harvest/sharing.md) is tracked for
  the sharing milestone, see Deferred.

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

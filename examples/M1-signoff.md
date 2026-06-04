# M1 sign-off: the task status lattice

> **What this is.** The LDD 5-phase milestone close, filled in. A milestone is not "done" until all five phases
> run: **BUILD, STRUCTURE, SECURITY, VERIFY, PLAN.** This is the record that they did, with the evidence, the
> verdict, what got deferred, and the mandatory next move. Copy this shape to close your own milestones.

- **Milestone:** M1, the task status lattice (the build of [`adr/ADR-0001-one-task-status-lattice.md`](adr/ADR-0001-one-task-status-lattice.md)).
- **Scope:** the single ordered `status` replacing `done`/`status`/`archivedAt`; the migration map; the
  INV-REOPEN invariant; the share-link expiry + revocation build action from the council.
- **Date closed:** 2026-06-02
- **Verdict: PASS WITH FIXES.** Two small fixes applied during close; one item deferred to M2 with rationale.

---

## Phase 1: BUILD

Built the lattice as a **walking skeleton**: one real path through every layer (model -> migration -> API ->
list view -> board view -> shared view), thin but end-to-end, before deepening any one surface.

- Replaced the three fields with one ordered `status` in the task model; values `open < in_progress < done <
  archived`, plus terminal `deleted`. Single predicate `status >= done`.
- Migration applied per the ADR map; ran against a copy of the dev DB. Row counts: 4,210 tasks migrated, 0
  errors, 0 rows landing in an unexpected state (verified by re-running the old `audit.ts` against the new column:
  zero contradictory states remain, down from 137 before).
- Re-keyed the nightly archive job off `status >= done` (was `done === true`).
- INV-REOPEN implemented over the ordered status with the cycle guard carried across from the legacy handler.
- Share model gained `expiresAt` (30-day default) and `revokedAt`; resolve path rewritten to fail closed; one
  revoke action added to the existing share list (per the council build action).

Formatter, linter, type-check, tests: **green.**

## Phase 2: STRUCTURE

A structural scan of the new surface (a scan, not a full refactor; the continuous closure-gate does the heavy
lifting).

- No function over the length budget. No God-object: the lattice logic is a small module, the invariant is one
  pure function.
- **Duplication ratchet held**, but only after a fix: the first cut had the `status >= done` comparison inlined in
  three places (list, board, shared view), which is exactly the drift this milestone exists to kill, reappearing
  in new code. **FIX APPLIED:** folded into one `isDone(status)` helper; the three call sites now share it. Ratchet
  green after the fold (budget held by folding, never by raising it).
- Migration map lives in one place and is referenced, not copy-pasted.

## Phase 3: SECURITY

- **Supply-chain (every milestone, cheap):** dependency audit run, no new advisories introduced by M1.
- **Risk-targeted deep audit:** triggered, because the share-link change is an **externally-reachable** surface.
  Findings:
  - The resolve path now checks existence AND not-expired AND not-revoked, all server-side at resolve time (not
    only at creation). Confirmed by reading the new `share.ts` resolve function.
  - **FIX APPLIED:** the first implementation compared `expiresAt` using local server time inconsistently; pinned
    both sides to UTC. (This is precisely the failure mode the council's devil's-advocate seat predicted: a fix
    that looks done but leaves the resolve path subtly wrong.)
  - Confirmed an `archived`/`deleted` task list is no longer reachable through an old token (the conflation at the
    old `share.ts:88` is gone).

## Phase 4: VERIFY

An **independent adversarial verifier** re-ran from a clean checkout and tried to break the milestone's
invariants.

- **Migration:** re-ran on a fresh DB copy; confirmed the "either old truth counts as done" rule preserved every
  historically completed task (spot-checked the `done = true` / `status = 'open'` cohort: all landed on `done`).
- **INV-REOPEN:** built a blocking chain A -> B -> C, completed all three, reopened A; B and C dropped to
  `in_progress`. Built a cycle A -> B -> A; reopen terminated (cycle guard holds). **Passed.**
- **Lattice:** attempted to construct a task that is "done in the list but open on the board" (the original bug).
  Could not: there is one field. **Passed.**
- **Share link (required council check):** attacked an **expired** token and a **revoked** token; both denied at
  the resolve path. Attacked a still-valid token: resolves. **Passed.** This is the check the council mandated.

Verifier's verdict: the milestone holds. The two issues it would have raised (inlined `isDone`, the UTC bug) were
already caught and fixed in STRUCTURE and SECURITY; the verifier confirmed the fixes from clean.

## Phase 5: PLAN (mandatory: the milestone does not close until the next move is planned)

### Deferred from M1 (carried forward, with rationale)
- **Per-link custom expiry.** M1 shipped a fixed 30-day default with no user-facing extend. This is the
  **surviving dissent** from [`council/share-link-expiry-verdict.md`](council/share-link-expiry-verdict.md) (the
  UX seat). Deferred deliberately, not forgotten: it is out of M1 scope and only justified if real support load
  shows the fixed window biting. **Trigger to revisit:** support tickets about expired links; that would be new
  ground-truth and standing to reopen the council.

### Next milestone: M2
- **Scope:** harvest and distil the *blocking graph editing* surface (creating/removing `blockedBy` edges), which
  M1 only consumed read-only via INV-REOPEN. M2 makes the edges first-class.
- **Risks:** edge creation can introduce cycles; M1 proved the *reopen* path is cycle-safe, but the *edit* path
  must reject or tolerate cycles by an explicit, spec'd rule (not an accident). This is a real fork and likely
  earns its own journal decision, possibly a council if it turns out to be hard to reverse.
- **Sequence:** harvest the edge-edit code (find where `blockedBy` is mutated today) -> decide the cycle policy ->
  walking skeleton -> loop to zero gaps -> 5-phase close.

### The single next move
Run the harvest pass over `blockedBy` mutation sites in legacy Tasky and open the M2 intent ledger. No build
starts before that ledger exists.

---

**M1 closed: PASS WITH FIXES.** Two fixes applied and verified from clean (the `isDone` fold, the UTC expiry bug),
one item deferred with a named trigger, next move planned. The lattice is the spec's source of truth for task
completion from here.

<!--
TEMPLATE: Spec skeleton (the distilled minimal spec).
WHEN: after harvesting, before/while building. The spec is the source of truth; code is kept in sync with
      it, not the other way around. Distil the SMALLEST complete set of primitives that solves the domain.
      Drop the sprawl on purpose and record why. The data structure IS the product.
HOW: copy this file (e.g. spec/SPEC.md), delete this comment, fill it. Invariants are NUMBERED and TESTABLE
      (a verifier must be able to attack them). The closure-sweep section defines "done" for the loop.
-->

# Spec: <system name, e.g. Tasky core>

**Status:** <draft | accepted>  **Last harmonized:** <date>
**Draws from:** <the intent ledgers this distils, e.g. _harvest/task-completion.md, _harvest/sharing.md>

## Primitives

The minimal set of nouns and shapes the system is built on. If a primitive is not needed to satisfy an
invariant below, it does not belong here.

- **<Primitive>**: <its shape, plainly>
- Example (Tasky): **Task** = `{ id, title, status: 'open'|'doing'|'done', blockedBy: TaskId[] }`.
  Completion is `status === 'done'`. There is no `done` boolean and no `archivedAt` as stored state;
  both are derived views. (This is the consolidation the whole rebuild exists for.)
- Example (Tasky): **ShareLink** = `{ token, taskId, expiresAt }`. A link without a future `expiresAt`
  is invalid by construction.

## Invariants (numbered, testable)

Each invariant is a property a verifier can attack. State it so it is true or false, never "should".

- **INV-1:** <a testable property>
- Example INV-1 (Tasky): A task is complete if and only if `status === 'done'`. The list view, the API,
  and the export all read this one field; they can never disagree.
- Example INV-2 (Tasky): If a blocking task reopens (`done -> open/doing`), every task it blocks
  auto-reopens, recursively through `blockedBy`. (Preserved from _harvest/task-completion.md.)
- Example INV-3 (Tasky): A share link is honoured only while `expiresAt` is in the future; an expired or
  expiry-less token is refused. (Closes the harvested share-link smell.)

## Deliberately dropped

The legacy behaviour you are NOT rebuilding, each with its reason. Dropping is auditable.

- DROP <thing> because <reason>.
- Example (Tasky): DROP the `done` boolean and `archivedAt` as stored fields, because the three-path
  completion model is the bug; INV-1 replaces it with one source of truth.
- Example (Tasky): DROP the second, bolted-on auth path, because it duplicated and diverged from the
  primary auth and was the more permissive of the two.

## Closure sweep (definition of done)

The automated check the spec/build loop runs each pass. "Done" is the sweep reporting zero gaps, not "the
tests pass". List what the sweep checks.

- [ ] Every invariant above has at least one test that attacks it, and it is green.
- [ ] No primitive in the code is absent from this spec, and no spec primitive is unbuilt (no orphans
      either way).
- [ ] Every "deliberately dropped" item is actually gone from the code (no surviving second path).
- [ ] Duplication ratchet holds; no over-long function or leaked abstraction in the new surface.
- Example (Tasky): the sweep greps for `\.done` and `archivedAt` as stored reads and fails if any remain
  outside the derivation layer; this is how INV-1 stays true as code lands.

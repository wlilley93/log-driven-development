---
name: simplify
description: The quality cleanup pass of Log-Driven Development. Review the recently changed code for reuse, simplification, efficiency, and "altitude" (right level of abstraction), then apply the fixes - while preserving observable behaviour exactly. Quality only: it folds duplication into shared helpers, removes needless complexity and dead abstraction, prefers existing helpers, and clarifies, but it does NOT hunt for bugs (use code-review for that). Use after a slice lands, in the STRUCTURE phase, or whenever a change "works but reads badly", to keep the rebuild from re-growing the sprawl it escaped.
---

# Simplify (the quality cleanup pass)

> Make the code that just landed clearer and smaller **without changing what it does.** Fold the second copy of a
> thing into one shared helper. Delete the abstraction that earns nothing. Prefer the helper that already exists.
> Then verify, by behaviour, that nothing observable moved.

This is the **quality** half of LDD's review machinery, the complement to [`code-review`](../code-review/SKILL.md).
Code-review hunts for *defects* (bugs, security holes, silent failures) and mostly advises. Simplify hunts for
*cleanups* (reuse, simplification, efficiency, altitude) and **applies them**. It is run in the STRUCTURE phase of
a milestone close, after a slice lands, and any time a change works but reads badly. It is the standing answer to
quality drift: agents and humans accrete complexity, and this pass folds it back down before it calcifies.

## The operating law (do not break)

1. **Never change observable behaviour.** Same inputs, same outputs, same side effects, same errors. Simplify
   changes *how* the code does a thing, never *what* it does. If a change would alter behaviour, it is a refactor
   or a fix, not a simplification, and it is out of scope here (label it and hand it on).
2. **Prefer what already exists.** Before writing a helper, grep for one. Reuse beats re-invent. A new utility
   that duplicates an existing one is the exact sprawl this pass exists to delete.
3. **Verify before and after.** Re-run the load-bearing checks (linter, type-check, the relevant tests) from a
   clean state before and after the change, and confirm they are identical. Behaviour-preservation is *proven*,
   not asserted. No completion claim without that evidence.
4. **Quality only, never bug-hunting.** If you spot a bug or a security hole while simplifying, **stop, do not
   bury it inside a cleanup commit**, and route it: a security issue is fixed immediately (the standing LDD rule);
   any other bug goes to [`code-review`](../code-review/SKILL.md) and a separate fix beat. Mixing a fix into a
   "no behaviour change" commit destroys the one guarantee this pass offers.
5. **Clarity over brevity.** Fewer lines is not the goal. Explicit, readable code beats a dense one-liner. Do not
   trade a clear `if/else` for a nested ternary to save two lines.

## When to invoke

- **STRUCTURE phase of a milestone close:** the structural scan flagged real debt (an over-long function, a
  God-object, a duplicated mechanism the ratchet caught). Simplify is how you pay it down.
- **After a slice lands:** a proactive cleanup of the code just written, before the commit, so the diff is clean
  on the way into history.
- **On demand:** a change "works but reads badly", or a reviewer asked for the cleanups without the bug hunt.

By default the scope is the **recently modified code** (the current diff or session), not the whole tree. Widen
only when explicitly asked.

## The four cleanup axes

Walk the changed code on these four axes, in this order. Each names what to look for and the move that fixes it.

### 1. Reuse (the load-bearing axis for LDD)

The thing this pass exists to enforce, because it is what stops the rebuild re-growing its sprawl.

- **Duplicated logic:** the same comparison, transformation, or rule inlined in two or more places. **Fold it**
  into one shared, named function and call it everywhere. (In the running task-tracker example, the `status >= done`
  comparison appearing in the list, the board, and the shared view is folded into one `isDone(status)` helper;
  that single fold is what stops a *fourth* way to complete a task from appearing.) This is the move the
  duplication ratchet in the [closure-gate](../../tools/closure-gate/README.md) mechanically demands: green by
  **folding**, never by raising the budget.
- **Re-invented helper:** a freshly written utility that an existing one already covers. Delete the new one, call
  the existing one. Grep first, always.
- **Parallel mechanism:** a second store, service, or code path doing what one already does. Consolidate to one
  source of truth; every other surface becomes a regenerable view (the *consolidation over fragmentation*
  discipline).

### 2. Simplification

- **Needless nesting and complexity:** flatten deep conditionals, replace a nested ternary with a `switch` or an
  `if/else` chain, return early instead of wrapping the body in an `else`.
- **Dead abstraction:** an indirection, wrapper, or layer that earns nothing (a one-call interface, a factory for
  a single type, a config flag that is never false). Inline it.
- **Redundant code and comments:** remove code that cannot run, and comments that merely restate the obvious. Keep
  the comments that explain *why*.

### 3. Efficiency

- **Cheap, safe wins only:** hoist an invariant computation out of a loop, drop a redundant pass over the same
  data, remove an unnecessary allocation or copy, replace a linear scan with an existing indexed lookup.
- **Stay in scope:** if a real efficiency win would change behaviour, timing, or an interface, it is not a
  simplification. Note it and hand it on. Do not silently change semantics in the name of speed.

### 4. Altitude (the right level of abstraction)

- **Too low:** code that should lean on a domain helper but open-codes the primitive. Raise it to the helper.
- **Too high:** a premature generalisation built for cases that do not exist. Bring it down to the concrete case
  actually needed. The cheapest abstraction is the one you did not build.
- **Mixed altitude in one function:** high-level orchestration tangled with low-level fiddling. Separate them so
  each function reads at one level.

## How to run it

1. **Establish scope and capture the baseline.** Identify the recently changed code. Run the linter, type-check,
   and the relevant tests from clean, and **record the results** as the before-baseline.
2. **Walk the four axes** over the changed code, gathering candidate cleanups. For each, name the axis, the
   `file:line`, and the move.
3. **Apply the safe ones.** Smallest, most mechanical first (fold a duplicate, inline a dead wrapper). Prefer the
   existing helper every time. Make each change observable-behaviour-neutral.
4. **Re-run from clean and diff the baseline.** Linter, type-check, and tests must produce results identical to
   the before-baseline. If any differ, you changed behaviour: revert and reclassify it as a refactor or a bug.
5. **Report** what you changed and why, axis by axis, with citations. For a substantive change, the orchestrator
   ground-truths and commits per beat with explicit paths; a subagent running this pass returns its diff and its
   before/after evidence and does **not** commit.

## Output format

```
## Simplify: <scope>
Baseline (before): <commands + results>
Baseline (after):  <commands + results>   # must match for behaviour preservation

### Reuse
- <file:line> - folded <duplicated thing> into <shared helper>. Behaviour: unchanged.

### Simplification
- <file:line> - <flattened / inlined / removed>. Behaviour: unchanged.

### Efficiency
- <file:line> - <cheap safe win>. Behaviour: unchanged.

### Altitude
- <file:line> - <raised / lowered / separated>. Behaviour: unchanged.

### Handed on (out of scope for a quality pass)
- <file:line> - <bug / security / behaviour-changing efficiency> -> routed to <code-review | immediate fix | refactor>.
```

If nothing needs cleaning, say so and show the baseline you captured, so the caller can see the pass was run, not
skipped.

## How this plugs into LDD

- It is the **STRUCTURE** phase tool of the [milestone close](../../docs/playbook.md#4b-the-milestone-close-five-phases),
  the scan that pays down flagged debt. Because the continuous closure-gate already enforces the structural budgets
  on every commit, this pass is usually a light net for what slipped, not a heavy ritual: escalate to a full
  [refactoring](../refactoring/SKILL.md) round only when the scan finds real debt.
- It enforces the **consolidation over fragmentation** discipline and the **duplication ratchet**: the reuse axis
  is exactly the fold the ratchet demands.
- It is the partner of [`code-review`](../code-review/SKILL.md): review finds defects (and mostly advises),
  simplify applies quality cleanups (and never hunts bugs). Run review for correctness and security; run simplify
  for clarity and reuse. Together they are the human-grade half of LDD's two-tier quality gate.

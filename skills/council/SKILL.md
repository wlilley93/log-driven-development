---
name: council
description: The adversarial deliberation court - convene N independent, named seats, each ground-truthing the real tree, each returning a blunt verdict; synthesise; act the same beat; dissolve. For high-stakes, hard-to-reverse forks, honest retrospectives, and pre-mortems. A challenged verdict escalates a three-tier court (Council → Appeals Council → Supreme Council, modelled on UK law) whose apex sets binding "spec law". Use when one perspective would rationalise, or when a decision turns on how the project's invariants were applied.
---

# The council - the adversarial deliberation court

> Convene N independent, named critical seats, each ground-truthing against the real tree, each returning a
> blunt written verdict; synthesise; **act the same beat**; dissolve the panel (the ledger keeps the verdict).
> The decision-making analogue of the builder + adversarial-verifier loop. A decision under challenge escalates
> a **three-tier court hierarchy modelled on UK law**.

## When to use
- A **high-stakes, hard-to-reverse fork** where a single perspective would rationalise (architecture,
  build-vs-consume, sequencing a whole program).
- A periodic **honest retrospective**: "is the project *actually* going well, and is the *process* working?"
- A **pre-mortem** before committing to a path ("it's N months later and this failed - why?").

Do NOT convene for a reversible/swappable decision - that gets one decisive sentence (the deliberation budget).
A court is expensive currency; spend it rarely. The appeals tiers are rarer still.

## Tier 1 - The Council (court of first instance)

### The shape (one parallel fan-out)
1. **Pick the seats - distinct lenses, not redundancy.** A typical retrospective panel:
   - **project health**: is the *artifact* on track? % to a shippable product; where the real risk is.
   - **process critic**: is the *method* working? where it's silently failing.
   - **collaboration**: is the *human↔agent* loop healthy? the deliberation-to-delivery ratio.
   - **devil's advocate / pre-mortem**: assume failure; rank causes by likelihood × lateness-of-discovery.
   Swap lenses to fit the question (security · cost · UX · a named alternative's advocate).
2. **Each seat MUST ground-truth first.** Greps, file reads, counts, test runs - the verdict cites real
   evidence from the tree, never vibes. (A seat that can't cite is ignored.)
3. **Independence.** Seats run concurrently and do not see each other mid-run; one synthesis step after.
4. **Bluntness is the deliverable.** Each seat leads with the uncomfortable truth, not a hedge.

### The discipline (non-negotiable)
- **End in a build action or a kill - never another deferring artifact.** Record the verdict, then *act on it
  the same beat*. A council whose output is "we'll look at it later" is the exact pathology it exists to catch.
- **Ephemeral.** The seats dissolve after; nothing persists but the verdict in the ledger + the **surviving
  dissent** (recorded, never buried - it is the standing of any future appeal). No standing committee.
- **Synthesise honestly.** The orchestrator reconciles the seats (they will disagree), states the through-line,
  and converts it into committed changes + tasks. A Council verdict **is the decision** unless appealed.

## The appeals hierarchy (UK-law model)

A first-instance verdict stands **by default**. Escalation is **not automatic**: it requires *standing* (a
genuine basis), and each tier has a **distinct remit**. At every tier, the higher court is handed the **full
record of every court below**: all seats' verdicts, the syntheses, the dissents, the inputs/outputs (the
appellate bundle). A higher court that ignores the lower record is improperly constituted.

| Tier | Convened when | Remit (what it argues) | Powers | Finality |
|---|---|---|---|---|
| **Council** (first instance) | A genuine high-stakes fork / retrospective | **Points of spec**: the *merits*: what is the right design given the spec, the code, the invariants | Decide (build action or kill) + record dissent | Stands unless appealed |
| **Appeals Council** | A verdict is **challenged with standing**: the principal disagrees, a load-bearing **surviving dissent** is unresolved, or **new ground-truth** contradicts a relied-upon point | **Points of spec** again - re-weighs the merits *as a review*; must engage (not re-run blind) the Council's reasoning | **Uphold or OVERTURN** | Stands unless taken to the Supreme Council |
| **Supreme Council** | The Appeals Council is challenged, **or** the question is of the highest *invariant/constitutional* significance | **Points of spec + invariant law ONLY**: does **NOT** re-litigate the merits. It assesses **how the invariant spec + the method's discipline was *applied*** below (were the invariants correctly applied? was the process sound?) | Set the controlling rule | **Becomes SPEC LAW - final, binding precedent, cannot be further overturned** |

**The merits/law split (the load-bearing distinction, faithful to UK practice).** The Council and the Appeals
Council are *trial and appeal on the merits* - they battle over **what the spec should say / what the right
decision is**. The Supreme Council is a *court of law, not of fact* - it does **not** ask "is this the best
design?"; it asks "**was the invariant spec + the method correctly *applied* in deciding it?**" That is why a
Supreme ruling can stand as **precedent**: it settles a point of *law* (how the invariants + method bind a
*class* of decisions), not a one-off design taste.

**Standing (don't appeal for free).** Appeal only on a real basis: the principal disagrees; an unresolved
load-bearing dissent; new ground-truth that falsifies a relied-upon point. The Supreme Council is reserved for
**points of invariant law**: "I'd have designed it differently" is not Supreme-Council standing; "the court
misapplied the trust-boundary invariant / violated the one-writer rule" is.

## Spec law (Supreme Council precedent)
A Supreme Council ruling is recorded as an immutable, numbered precedent (a `SPEC-LAW.md` register) and **binds
every future court**: a first-instance Council **cannot** overturn it, and a decision that collides with a
spec-law precedent is denied at the spec layer (the same fail-closed shape a trust boundary uses to deny an
unmapped capability). Spec law is cited by ID in later decisions as *controlling*. Only a later Supreme Council,
expressly distinguishing or narrowing the precedent on a point of invariant law, may refine it - never a lower
court, never the build phase. (The hierarchy itself is *constitutional* - established by the principal, the
framework within which spec law is made; it is not itself a Supreme ruling.)

## How to run it
- **Tier 1:** a single parallel fan-out - one agent per seat (told to ground-truth + be blunt), then the
  orchestrator synthesises. Cheap to run, expensive to ignore.
- **Appeal / Supreme:** the same shape, but **hand every seat the full lower-court record** and **scope the
  remit**: Appeals = re-weigh the merits engaging the Council's reasoning; Supreme = review only the
  *application of invariant + method law*, output a precedent. Fresh independent seats each tier (no carry-over
  of personnel - only of the record).

## Output
- **Council / Appeals Council:** a synthesised verdict (one ledger entry) + the **build actions / kills it
  triggered** (commits + tasks) + the surviving dissent - never a verdict that only defers.
- **Supreme Council:** a ruling appended to the spec-law register as a numbered, immutable precedent,
  cross-linked from the ledger entry and any decision it governs.

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

## When you (the agent) should convene one
Prescriptive triggers. Convene a Council when, and only when, one of these holds:
- A **genuine hard fork**: a load-bearing, hard-to-reverse choice (architecture, build-vs-consume, sequencing a
  whole program) where a single perspective would rationalise.
- An **honest "is this actually working?"**: a periodic retrospective on whether the artifact is on track AND
  whether the method itself is silently failing.
- A **pre-mortem** before committing to a path: "it is N months later and this failed, why?"

Do NOT convene one when:
- The choice is **reversible or swappable** -> one decisive sentence, then build it.
- The choice is **irreversible but buildable** (a framework, store, protocol) -> a spike or thin slice that
  exercises it, not a debate.
- It is a **principal-owner policy or domain call** (not a technical one) -> ASK the principal; do not convene a
  panel to guess on their behalf.
- It is a **security issue** -> fix it immediately; do not deliberate.

A challenged Council verdict does not get a re-run Council: it escalates the appeals hierarchy below, and only
with standing.

## How to run one, step by step
1. **Pick the seats: distinct lenses, not redundancy.** Choose seats whose viewpoints do not overlap (for a
   retrospective: project health, process critic, collaboration, devil's advocate / pre-mortem; swap in
   security, cost, UX, or a named alternative's advocate to fit the question). One agent per seat.
2. **Each seat grounds-truth FIRST.** Tell each seat to grep, read files, run counts and tests, and to cite real
   evidence from the tree. A seat that cannot cite is ignored.
3. **Run them independently.** Seats run concurrently and do not see each other mid-run. Brief each to lead with
   the uncomfortable truth, not a hedge.
4. **Synthesise honestly.** The orchestrator reconciles the seats (they will disagree), states the through-line,
   and converts it into committed changes plus tasks.
5. **Determine genuine function (REQUIRED, before resolving).** Invoke a *period of determination*: find, by
   ground-truth (a spike, a test, a demonstrated end-to-end path, a concrete mechanism), whether the decided
   thing **will genuinely function as intended** - not merely whether it is the right design on the merits. The
   merits ask "is this right?"; this asks "will it actually work?". "It looks right" / "it should work" is not a
   determination (it is the over-claim this phase exists to catch). If genuine function cannot be affirmatively
   determined, the verdict may NOT resolve to build/ratify - only to KILL or SPIKE-FIRST (exercise it, then
   re-determine). At system scale the determination is a real end-to-end run, not design-soundness alone.
6. **End in build-or-kill, the same beat.** The verdict resolves to a committed change or an explicit kill,
   never another deferring artifact. Act on it now.
7. **Record dissent + the determination.** Write the verdict to the ledger with the genuine-function
   determination and the surviving dissent verbatim (the standing of any future appeal). Then dissolve the
   panel; nothing persists but the verdict, the determination, and the dissent.

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
- **Determine genuine function before resolving (required, every tier).** A verdict may not resolve to
  build/ratify/uphold until the council has determined, *by ground-truth not assertion*, that the system will
  genuinely function as intended. If it cannot, the verdict is a kill or a spike-first. This is separate from
  the merits and governs them: a council can be right on the design and still wrong on whether it works. The
  apex court may review whether this determination was properly conducted (a point of law).
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

> **The invariant spec the Supreme Council applies is the method's own register:**
> [`docs/invariants.md`](../../docs/invariants.md) (LDD-INV-1..N). That register is the *law* the Supreme
> Council reasons from (was LDD-INV-2 one-writer kept? was LDD-INV-9 one-owner-per-concern honoured?), plus
> the project's own distilled invariants. A project layers its domain invariants on top; the LDD-INV register
> is the floor every LDD run is bound by.

**Standing (don't appeal for free).** Appeal only on a real basis: the principal disagrees; an unresolved
load-bearing dissent; new ground-truth that falsifies a relied-upon point. The Supreme Council is reserved for
**points of invariant law**: "I'd have designed it differently" is not Supreme-Council standing; "the court
misapplied the trust-boundary invariant / violated the one-writer rule" is.

## Spec law (Supreme Council precedent)
A Supreme Council ruling is recorded as an immutable, numbered precedent in the **central
[`council/SPEC-LAW.md`](../../council/SPEC-LAW.md) register that ships with the methodology** (distinct from
[`docs/invariants.md`](../../docs/invariants.md): that is the standing LDD-INV register the court *applies*;
`council/SPEC-LAW.md` is the precedent it *writes*). A ruling **binds every future court**: a first-instance
Council **cannot** overturn it, and a decision that collides with a spec-law precedent is denied at the spec layer
(the same fail-closed shape a trust boundary uses to deny an unmapped capability). Spec law is cited by ID in later
decisions as *controlling*. Only a later Supreme Council, expressly distinguishing or narrowing the precedent on a
point of invariant law, may refine it - never a lower court, never the build phase. (The hierarchy itself is
*constitutional* - established by the principal, the framework within which spec law is made; it is not itself a
Supreme ruling.)

**Spec law is project-agnostic and propagates to every project running LDD.** The register is central and travels
with the methodology: a project gets all spec law to date by installing the plugin, and new precedents by updating
it (the same way a shared linter ruleset propagates). The council skill reads `council/SPEC-LAW.md` when it
convenes and enforces it. Because the register is append-only and numbered, it distributes without conflict.
Entries must be **fact-free, universal points of law** (no project, host, or vendor specifics) so they bind a
*class* of decisions; a generally-significant ruling is contributed back as a **community pull request** against
the central register, reviewed for exactly that fact-free universality. A project MAY keep a separate local
precedent file for genuinely project-specific rulings, and promote any that prove general to the central register
by PR.

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
  cross-linked from the ledger entry and any decision it governs. **Deliver and record the Supreme judgment in
  full:** every justice's opinion, ruling, grounding (the invariants cited), and self-dissent is preserved
  verbatim, never collapsed to only a synthesis. This applies the append-only, dissent-is-never-buried discipline
  (LDD-INV-16) to the whole panel: the synthesised controlling rule is the precedent; the full panel is the record
  behind it, and both are reported to the principal, not just the verdict.

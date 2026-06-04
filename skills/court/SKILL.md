---
name: court
description: The adversarial deliberation court - a claimant and a defendant steelman the two sides first (which doubles as the ripeness filter against over-litigation); only a surviving contest reaches a neutral bench of independent justices that ground-truths both briefs and rules; synthesise; act the same beat; dissolve. For high-stakes, hard-to-reverse forks, honest retrospectives, and pre-mortems. A challenged verdict escalates a three-tier court (Court → Appeals Court → Supreme Court, modelled on UK law) whose apex sets binding "spec law". Use when one perspective would rationalise, or when a decision turns on how the project's invariants were applied.
---

# The court - the adversarial deliberation court

> A **claimant** and a **defendant** steelman the two sides first - if only one survives, decide there and convene
> nothing. A surviving contest goes to a **neutral bench** of independent justices, each ground-truthing both
> briefs against the real tree and returning a blunt written verdict; synthesise; **act the same beat**; dissolve
> the panel (the ledger keeps the verdict). The decision-making analogue of the builder + adversarial-verifier
> loop. A decision under challenge escalates a **three-tier court hierarchy modelled on UK law**.

> **The registers, and the method/justice boundary.** The authoritative *procedure* (how a case runs - the
> proceeding, the parties, pleadings, bundles, the tiers, precedent) is the **[Development Procedure Rules,
> `court/DPR.md`](../../court/DPR.md)**; this skill is the *practice direction* that runs proceedings under those
> rules. The court reads and writes three registers, all under `court/`: **[`DPR.md`](../../court/DPR.md)**
> (procedure), **[`SPEC-LAW.md`](../../court/SPEC-LAW.md)** (apex substantive law - what the Supreme Court
> writes), and **[`CASE-LAW.md`](../../court/CASE-LAW.md)** (the law reports - merits precedent, by court). These
> are **JUSTICE** facts. They are distinct from the **METHOD** floor the court *applies*, the
> **[LDD-INV register, `docs/invariants.md`](../../docs/invariants.md)**. The court *applies* `docs/invariants.md`;
> it *writes* `court/*`.

## When to use
- A **high-stakes, hard-to-reverse fork** where a single perspective would rationalise (architecture,
  build-vs-consume, sequencing a whole program).
- A periodic **honest retrospective**: "is the project *actually* going well, and is the *process* working?"
- A **pre-mortem** before committing to a path ("it's N months later and this failed - why?").

Do NOT convene for a reversible/swappable decision - that gets one decisive sentence (the deliberation budget).
A court is expensive currency; spend it rarely. The appeals tiers are rarer still.

## When you (the agent) should convene one
Prescriptive triggers. Convene a Court when, and only when, one of these holds:
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

A challenged Court verdict does not get a re-run Court: it escalates the appeals hierarchy below, and only
with standing.

## The shape: advocates steelman, a neutral bench rules
The court **strictly separates advocacy from adjudication**, exactly as a real adversarial court does. Partisanship
lives entirely in a pre-court steelman; the bench that rules is **wholly neutral**.

**Stage 0 - the steelman (the ripeness filter, and the ONLY partisan role).** Before any bench is convened,
commission two opposed advocates: a **claimant** who builds the strongest possible case FOR the proposition, and a
**defendant** who builds the strongest case AGAINST. Each grounds-truth and steelmans its side, marshalling *every*
relevant lens in its brief (security, cost, simplicity, the rejected alternative) - so multi-dimensional rigor lives
in the briefs, not in the deciders. This stage **is the filter against over-litigation**: if one side cannot be
steelmanned - it concedes, collapses, or is demolished on ground-truth - there is no genuine contest, the decision
is made here (build-or-kill), and **no bench is convened**. Only a question where *both* steelmanned cases survive -
a real fork - earns a court.

**Stage 1+ - the neutral bench.** Convene a panel of **impartial justices, with no advocate among them**. Hand them
*both* briefs. Each justice **independently ground-truths the briefs** (an advocate's brief is an argument, not
evidence - verify every load-bearing figure, cf. SPEC-LAW-1(c); this is where an overclaimed number dies), runs
**blind** to the others, weighs the two cases, and rules. Justices may differ in *judicial philosophy* (textualist,
purposive, risk-first) but never in *allegiance*. One synthesis step after. This holds at every tier: on appeal the
appellant (claimant) and respondent (defendant) re-argue and a neutral Appeals bench rules; at the apex both sides
brief the point of law and neutral Supreme justices rule on it.

This is what makes the agent's petitioner standing safe: the agent does not "decide to litigate" - it commissions
the steelman, and the steelman decides whether a court is warranted. An agent cannot over-litigate a question that
has no surviving second side.

## How to run one, step by step
*(Operationalises the two-stage shape above. Where this list says "the seats", read **the neutral bench**; the
devil's-advocate / alternative-advocate work now lives in the Stage-0 steelman, never on the bench.)*
1. **Stage 0 first - steelman both sides.** Commission a claimant and a defendant; each grounds-truth and builds the
   strongest case. If only one side survives, build-or-kill now and stop - no bench. If both survive, proceed.
2. **Pick the bench: neutral justices, diverse in philosophy not allegiance.** Choose 3-5 impartial deciders who
   weigh *both* briefs from genuinely different reasoning stances (textualist vs purposive vs risk-first; or
   project-health vs process vs pre-mortem framings, applied impartially) - never as partisans, never assigned a
   side. One agent per justice. The lenses that used to be partisan seats (devil's advocate, a named alternative's
   advocate) are now the Stage-0 claimant and defendant, not bench members.
3. **Each justice grounds-truth the briefs FIRST.** Tell each justice to grep, read files, run counts and tests,
   and to cite real evidence from the tree - a brief's load-bearing claims are verified, never trusted. A justice
   that cannot cite is ignored.
4. **Run them independently.** Justices run concurrently and do not see each other mid-run. Brief each to lead
   with the uncomfortable truth, not a hedge.
5. **Synthesise honestly.** The orchestrator reconciles the bench (justices will disagree), states the
   through-line, and converts it into committed changes plus tasks.
6. **Determine genuine function (REQUIRED, before resolving).** Invoke a *period of determination*: find, by
   ground-truth (a spike, a test, a demonstrated end-to-end path, a concrete mechanism), whether the decided
   thing **will genuinely function as intended** - not merely whether it is the right design on the merits. The
   merits ask "is this right?"; this asks "will it actually work?". "It looks right" / "it should work" is not a
   determination (it is the over-claim this phase exists to catch). If genuine function cannot be affirmatively
   determined, the verdict may NOT resolve to build/ratify - only to KILL or SPIKE-FIRST (exercise it, then
   re-determine). At system scale the determination is a real end-to-end run, not design-soundness alone.
7. **End in build-or-kill, the same beat.** The verdict resolves to a committed change or an explicit kill,
   never another deferring artifact. Act on it now.
8. **Record dissent + the determination.** Write the verdict to the ledger with the genuine-function
   determination and the surviving dissent verbatim (the standing of any future appeal). Then dissolve the
   panel; nothing persists but the verdict, the determination, and the dissent.

## Tier 1 - The Court (court of first instance)

### The shape (steelman, then a neutral bench)
1. **Stage 0 - steelman the two sides.** A fork is argued by a **claimant** (for) and a **defendant** (against). A
   retrospective is argued the same way: claimant - "the artifact and the method are on track"; defendant (the
   pre-mortem) - "here is how and why this is failing." Each advocate marshals *every* relevant angle in its brief
   (project-health, process, collaboration, security, cost, the rejected alternative), grounds-truth, and
   steelmans. If a side cannot be steelmanned, decide on the survivor and convene **no bench**.
2. **Stage 1 - a neutral bench.** Impartial justices, **no advocate among them**, each handed *both* briefs.
3. **Each justice MUST ground-truth the briefs.** Greps, file reads, counts, test runs - a brief's load-bearing
   claims are verified against the tree, never taken on trust (a brief is an argument, not evidence). A justice
   that can't cite is ignored.
4. **Independence + bluntness.** Justices run concurrently, blind to each other; each leads with the uncomfortable
   truth, not a hedge; one synthesis step after.

### The discipline (non-negotiable)
- **Determine genuine function before resolving (required, every tier).** A verdict may not resolve to
  build/ratify/uphold until the court has determined, *by ground-truth not assertion*, that the system will
  genuinely function as intended. If it cannot, the verdict is a kill or a spike-first. This is separate from
  the merits and governs them: a court can be right on the design and still wrong on whether it works. The
  apex court may review whether this determination was properly conducted (a point of law).
- **End in a build action or a kill - never another deferring artifact.** Record the verdict, then *act on it
  the same beat*. A court whose output is "we'll look at it later" is the exact pathology it exists to catch.
- **Ephemeral.** The seats dissolve after; nothing persists but the verdict in the ledger + the **surviving
  dissent** (recorded, never buried - it is the standing of any future appeal). No standing committee.
- **Synthesise honestly.** The orchestrator reconciles the seats (they will disagree), states the through-line,
  and converts it into committed changes + tasks. A Court verdict **is the decision** unless appealed.

## The appeals hierarchy (UK-law model)

A first-instance verdict stands **by default**. Escalation is **not automatic**: it requires *standing* (a
genuine basis), and each tier has a **distinct remit**. At every tier, the higher court is handed the **full
record of every court below**: all seats' verdicts, the syntheses, the dissents, the inputs/outputs (the
appellate bundle). A higher court that ignores the lower record is improperly constituted.

| Tier | Convened when | Remit (what it argues) | Powers | Finality |
|---|---|---|---|---|
| **Court** (first instance) | A genuine high-stakes fork / retrospective | **Points of spec**: the *merits*: what is the right design given the spec, the code, the invariants | Decide (build action or kill) + record dissent | Stands unless appealed |
| **Appeals Court** | A verdict is **challenged with standing**: the principal disagrees, a load-bearing **surviving dissent** is unresolved, or **new ground-truth** contradicts a relied-upon point | **Points of spec** again - re-weighs the merits *as a review*; must engage (not re-run blind) the Court's reasoning | **Uphold or OVERTURN** | Stands unless taken to the Supreme Court |
| **Supreme Court** | The Appeals Court is challenged, **or** the question is of the highest *invariant/constitutional* significance | **Points of spec + invariant law ONLY**: does **NOT** re-litigate the merits. It assesses **how the invariant spec + the method's discipline was *applied*** below (were the invariants correctly applied? was the process sound?) | Set the controlling rule | **Becomes SPEC LAW - final, binding precedent, cannot be further overturned** |

**The merits/law split (the load-bearing distinction, faithful to UK practice).** The Court and the Appeals
Court are *trial and appeal on the merits* - they battle over **what the spec should say / what the right
decision is**. The Supreme Court is a *court of law, not of fact* - it does **not** ask "is this the best
design?"; it asks "**was the invariant spec + the method correctly *applied* in deciding it?**" That is why a
Supreme ruling can stand as **precedent**: it settles a point of *law* (how the invariants + method bind a
*class* of decisions), not a one-off design taste.

> **The invariant spec the Supreme Court applies is the method's own register:**
> [`docs/invariants.md`](../../docs/invariants.md) (LDD-INV-1..N). That register is the *law* the Supreme
> Court reasons from (was LDD-INV-2 one-writer kept? was LDD-INV-9 one-owner-per-concern honoured?), plus
> the project's own distilled invariants. A project layers its domain invariants on top; the LDD-INV register
> is the floor every LDD run is bound by.

**Standing (don't appeal for free).** Appeal only on a real basis: the principal disagrees; an unresolved
load-bearing dissent; new ground-truth that falsifies a relied-upon point. The Supreme Court is reserved for
**points of invariant law**: "I'd have designed it differently" is not Supreme-Court standing; "the court
misapplied the trust-boundary invariant / violated the one-writer rule" is.

## Spec law (Supreme Court precedent)
A Supreme Court ruling is recorded as an immutable, numbered precedent in the **central
[`court/SPEC-LAW.md`](../../court/SPEC-LAW.md) register that ships with the methodology** (distinct from
[`docs/invariants.md`](../../docs/invariants.md): that is the standing LDD-INV register the court *applies*;
`court/SPEC-LAW.md` is the precedent it *writes*). A ruling **binds every future court**: a first-instance
Court **cannot** overturn it, and a decision that collides with a spec-law precedent is denied at the spec layer
(the same fail-closed shape a trust boundary uses to deny an unmapped capability). Spec law is cited by ID in later
decisions as *controlling*. Only a later Supreme Court, expressly distinguishing or narrowing the precedent on a
point of invariant law, may refine it - never a lower court, never the build phase. (The hierarchy itself is
*constitutional* - established by the principal, the framework within which spec law is made; it is not itself a
Supreme ruling.)

**Spec law is project-agnostic and propagates to every project running LDD.** The register is central and travels
with the methodology: a project gets all spec law to date by installing the plugin, and new precedents by updating
it (the same way a shared linter ruleset propagates). The court skill reads `court/SPEC-LAW.md` when it
convenes and enforces it. Because the register is append-only and numbered, it distributes without conflict.
Entries must be **fact-free, universal points of law** (no project, host, or vendor specifics) so they bind a
*class* of decisions; a generally-significant ruling is contributed back as a **community pull request** against
the central register, reviewed for exactly that fact-free universality. A project MAY keep a separate local
precedent file for genuinely project-specific rulings, and promote any that prove general to the central register
by PR.

## The agent as petitioner (self-initiated cases and agent standing)
The driving agent is not a passive clerk that only convenes a court when the principal asks. It is a first-class
**petitioner**: it may *bring* a matter, an appeal, or a reference on its own initiative (there is still no
opposing *party* - the adversarialism is supplied by the seats). This standing is **delegated by the principal**
and bounded by a real-basis test at every tier, so the court stays expensive currency.

1. **Commission the steelman, then file (first instance).** The agent must spot a genuine hard fork itself and
   *commission the Stage-0 steelman* - a claimant and a defendant - rather than deciding the case alone or framing
   it to favour an answer. The steelman is the gate: if a side collapses, the agent builds-or-kills on the
   survivor and convenes no bench; only a surviving two-sided contest is filed, captioned *In re <subject>*,
   before a neutral bench. The partisanship is the advocates'; the bench's is none.
2. **Appeal as appellant, with standing.** After a verdict the agent may bring an appeal *itself*, without waiting
   for the principal to object - but only on the unchanged standing bar: it holds a load-bearing surviving
   dissent, or it has discovered new ground-truth that falsifies a premise the verdict relied on. "I would have
   decided differently" is never standing. The agent may never appeal to defer a call it should simply make, to
   "be safe", or to launder its own preference into a re-run (SPEC-LAW-1(a)). It grounds-truth its own claim
   before filing: an appeal resting on an un-ground-truthed premise is the collapsed-fact error the court exists
   to catch (SPEC-LAW-1(c)).
3. **Petition the Supreme Court for certainty-to-proceed.** When the agent justifiably cannot proceed *with
   absolute certainty* because a point of invariant law is genuinely unsettled, it may petition the apex - but
   only when ALL THREE hold: (a) it is a true point of invariant law (how the invariants and the method's
   discipline bind a *class* of decisions), not a one-off merits call; (b) settling it is *necessary to proceed* -
   the uncertainty actually blocks safe progress, it is not curiosity or a wish to be thorough; and (c) the ruling
   would bind a class of future decisions, earning its place as spec law. Absent all three, the agent decides on
   the merits and does not spend the apex. A point of law referred this way is captioned *Reference re <point of
   law>*.

**Bounds (non-negotiable).** The court is expensive currency, spent rarely; a self-initiated case still ends in
**build-or-kill**, never in deferral - the petition is never an excuse not to decide. The principal may halt,
redirect, or override any agent-initiated case at any tier: the agent's standing is **delegated, not sovereign**,
and the hierarchy itself remains constitutional, established by the principal. Used well, this is what lets the
method run autonomously and still bind itself - the agent refers the genuinely hard, genuinely load-bearing
questions up of its own accord, and each ruling crystallises into spec law the whole method then inherits.

**The Supreme Court may dismiss, and that is the safety valve.** The apex is not obliged to rule: it
**dismisses** a petition that presents no genuine, universal point of law - a merits question dressed as law, a
one-off with no class to bind, or a point an existing precedent already settles (cite it and deny). A dismissed
petition produces **no spec law**. This filter is what keeps the register sharp as self-petitioning scales: spec
law is clarified by **coverage of the points of law that actually matter, not by volume**. Because each ruling
binds a whole class and an existing precedent denies the next collision at the spec layer with no new case, the
rate of *new* references **tapers as the register matures** - the goal is a heavily-clarified register reached by
a modest number of high-leverage rulings, never an ever-growing caseload (an agent that refers *everything* up is
the litigating-instead-of-building pathology, not the method working).

## Naming a case (the caption)
A court case has no claimant and no defendant; it is a **matter**, and the adversarial part is the seats, not
two named parties. Caption it the way real courts caption non-adversarial proceedings:
- **Court and Appeals Court (the merits): "In re <subject>"** (in the matter of ...). Name the fork by its
  subject, e.g. *In re the Court-Split*. The caption heads the ledger verdict, and an appeal carries it forward.
- **Supreme Court (a point of law): "Reference re <point of law>"**. The apex answers a *referred point of law*,
  so name it by the question, e.g. *Reference re Consolidation*. That caption **becomes the precedent's name** in
  [`court/SPEC-LAW.md`](../../court/SPEC-LAW.md) and is cited as *Reference re Consolidation (SPEC-LAW-n)*.

The two opposing views are recorded *inside* the case (the seats; and, at the apex, the rival constructions),
never in the caption - that is the whole point of "In re"/"Reference re": these are matters and references, not
party disputes.

## How to run it
- **Tier 1:** a single parallel fan-out - one agent per seat (told to ground-truth + be blunt), then the
  orchestrator synthesises. Cheap to run, expensive to ignore.
- **Appeal / Supreme:** the same shape, but **hand every seat the full lower-court record** and **scope the
  remit**: Appeals = re-weigh the merits engaging the Court's reasoning; Supreme = review only the
  *application of invariant + method law*, output a precedent. Fresh independent seats each tier (no carry-over
  of personnel - only of the record).

## Output
- **Court / Appeals Court:** a synthesised verdict (one ledger entry) + the **build actions / kills it
  triggered** (commits + tasks) + the surviving dissent - never a verdict that only defers.
- **Supreme Court:** a ruling appended to the spec-law register as a numbered, immutable precedent,
  cross-linked from the ledger entry and any decision it governs. **Deliver and record the Supreme judgment in
  full:** every justice's opinion, ruling, grounding (the invariants cited), and self-dissent is preserved
  verbatim, never collapsed to only a synthesis. This applies the append-only, dissent-is-never-buried discipline
  (LDD-INV-16) to the whole panel: the synthesised controlling rule is the precedent; the full panel is the record
  behind it, and both are reported to the principal, not just the verdict.

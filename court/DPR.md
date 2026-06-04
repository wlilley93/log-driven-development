# DPR: the Development Procedure Rules

The **Development Procedure Rules** are the procedural code of the Log-Driven Development court: *how a case runs*.
They are to the court what the Civil Procedure Rules are to a real court. They are distinct from the two
substantive registers the court reads and writes:

- **[`SPEC-LAW.md`](SPEC-LAW.md)** - the apex *substantive* law (fact-free, universal points of law; immutable;
  binds every court). What the Supreme Court *writes*.
- **[`CASE-LAW.md`](CASE-LAW.md)** - the *law reports*: the body of decided merits cases, tagged by deciding
  court, citable as precedent and open to being distinguished or overturned by a higher court.
- **DPR (this file)** - *procedure*: who may bring a case, how it is argued, who decides, how it is recorded.

> The court applies the method's own **[LDD-INV register](../docs/invariants.md)** as its floor of law. That
> register is a **METHOD** fact (it lives in `docs/` and governs every LDD run). The two registers above are
> **JUSTICE** facts (they live here in `court/`, and are produced by the court). That method/justice boundary is
> the single most useful distinction in the system: `docs/invariants.md` is the law the court *applies*;
> `court/*` is the law the court *writes*. (Per *In re the Justice-System Reorganisation*, the two domains are
> separated logically, not by relocating the method tree.)

The operational engine that runs a proceeding under these rules is the **[court skill](../skills/court/SKILL.md)**;
this file is the authoritative *rules*, the skill is the *practice direction* that cites them.

---

## Part 1 - Scope and the overriding objective

**DPR 1.1 - The overriding objective.** The court exists to settle a *rare, high-stakes, hard-to-reverse,
contested* fork as cheaply as is consistent with getting it right, and to **end in a build action or a kill**,
never in a further deferring artifact. Every rule below is read to serve that objective.

**DPR 1.2 - The court is expensive currency.** A reversible or swappable choice gets one decisive sentence, not a
case. A security issue is fixed on sight, never litigated. A principal-policy or domain call is put to the
principal, not guessed by a panel. The court is for the genuine fork that survives the steelman (DPR Part 5).

**DPR 1.3 - Proportionality.** The weight of a case scales with its stakes: a small fork gets brief pleadings and
a short judgment; a large case gets a full bundle (DPR Part 8). Ceremony is never added beyond what the stakes
earn.

---

## Part 2 - Standing: who may bring a case

**DPR 2.1 - Matters the court hears.** A genuine hard fork (architecture, build-vs-consume, sequencing a
program); an honest *"is this actually working?"* retrospective; a pre-mortem.

**DPR 2.2 - Standing to bring or appeal.** A case or appeal needs a *real basis*: the principal challenges; a
load-bearing surviving dissent is unresolved; or new ground-truth contradicts a relied-upon point. "I would have
decided differently" is not standing.

**DPR 2.3 - The agent as petitioner.** The driving agent is a first-class petitioner: it may commission the
steelman, appeal with standing, and petition the Supreme Court for certainty-to-proceed, each gated by DPR 2.2
and bounded by DPR 11. Its standing is **delegated by the principal, not sovereign**: the principal may halt,
redirect, or override any agent-initiated case at any tier.

---

## Part 3 - The parties and the bench

**DPR 3.1 - The parties persist; the bench does not.** A case has two persistent partisan parties - a
**claimant** (for the proposition) and a **defendant** (against) - who carry through *every tier*, each pushing or
resisting the appeal. The **bench** (the deciders) is *fresh at every tier*: new neutral justices each time, who
inherit only the record, never the prior bench's personnel.

**DPR 3.2 - Advocacy and adjudication are strictly separated.** Partisanship lives only in the parties. No
advocate sits on the bench. The justices are impartial; they may differ in *judicial philosophy* (textualist,
purposive, risk-first) but never in *allegiance*.

**DPR 3.3 - Objectors.** At the **Supreme Court only**, the principal agent may constitute **objectors**
(interveners) - third parties who raise a discrete objection on a point of law that neither party advances. An
objector argues law, not the merits, and is recorded as such.

**DPR 3.4 - The principal agent.** The principal agent is the orchestrator: it commissions the steelman, seats
the bench fresh at each tier, instantiates objectors at the apex, and synthesises each judgment. It must frame
neutrally and never rig a question toward a preferred answer.

---

## Part 4 - The proceeding: one extended seating

**DPR 4.1 - One proceeding, not three.** A contested fork runs as a **single extended multi-agent proceeding**,
not as separate detached cases. It enters at first instance and **pops out at whichever tier disposes of it** -
first instance if unappealed, the Appeals Court if the appeal resolves it, the Supreme Court if a point of law
must be settled.

**DPR 4.2 - The parties carry the thread.** The claimant and defendant persist across the whole proceeding; the
principal agent instantiates the per-tier actors (a fresh bench at each tier, objectors at the apex) as the case
climbs.

**DPR 4.3 - Early exit on disposition.** The proceeding terminates the moment a tier disposes of the case and no
party has standing to escalate. A case is never carried higher than the dispute requires.

**DPR 4.4 - Caption.** A case has no party-v-party title: it is a *matter*, and the adversarialism is internal
(the advocates), not in the caption. Caption it as real courts caption non-adversarial proceedings. Merits tiers:
***In re <subject>*** (e.g. *In re the Court-Split*), which heads the ledger verdict and an appeal carries
forward. A point of law referred to the apex: ***Reference re <point of law>*** (e.g. *Reference re
Consolidation*), which becomes the precedent's name in [`SPEC-LAW.md`](SPEC-LAW.md).

---

## Part 5 - Stage 0: the steelman (the ripeness filter)

**DPR 5.1 - Steelman before any bench.** Before a bench is convened, the claimant and defendant each build the
**strongest possible case** for their side, grounding-truth first, marshalling *every* relevant lens (security,
cost, simplicity, the rejected alternative) inside the brief.

**DPR 5.2 - The filter.** If one side cannot be steelmanned - it concedes, collapses, or is demolished on
ground-truth - there is **no genuine contest**: the decision is made on the survivor (build-or-kill) and **no
bench is convened**. Only a question where *both* steelmanned cases survive proceeds to court. This is the primary
guard against over-litigation (DPR 11).

**DPR 5.3 - Form of a pleading.** A pleading states the party, the plea (the disposition sought), and **numbered
grounds**, each backed by either an **authority** (a cited rule or precedent - DPR Part 9) or **evidence** (a
ground-truthed fact). **Every load-bearing figure carries the inline, re-runnable command that produced it and
its output** (the `grep`/`wc`/`du`/test that yields the number), so the bench and any later reader can re-run it;
a figure with no re-runnable command behind it is struck. Each party states its strongest point and concedes
fairly what the other side gets right.

---

## Part 6 - Stage 1: the neutral bench

**DPR 6.1 - The bench.** A panel of 3-5 impartial justices, no advocate among them, each handed *both* briefs.

**DPR 6.2 - A brief is argument, not evidence; the bench is fallible.** Each justice **independently
ground-truths** every load-bearing claim, **re-running the inline command** behind any figure (DPR 5.3) rather
than re-asserting it (cf. *In re the Court-Split*, where a pleaded "4.5M" cost was really ~20K). This catch is
**required of the bench but never guaranteed**: the bench is one more fallible agent of the same kind that wrote
the brief, so the re-runnable command is the safeguard, not the bench's word.

**DPR 6.3 - Determination of genuine function.** Before a verdict may resolve to build/ratify/uphold, the bench
must determine, *by ground-truth not assertion*, that the decided thing will genuinely function as intended
(SPEC-LAW-2). If it cannot, the verdict is a **kill** or a **spike-first**.

**DPR 6.4 - Form of a judgment.** Each justice issues a judgment in proper form: **findings of fact** (with
citations), **authorities applied**, a **holding**, the **ratio decidendi** (the binding reason), the
**disposition** (the order), and a **self-dissent** (the strongest argument against the holding, preserved as
standing for appeal - LDD-INV-16). The orchestrator synthesises the bench into one judgment of the court.

**DPR 6.5 - Build-or-kill, the same beat.** The judgment resolves to a committed change or an explicit kill, and
is acted on now. A judgment that only defers is the pathology the court exists to catch.

---

## Part 7 - The tiers and their remits

| Tier | Convened when | Remit | Powers | Finality |
|---|---|---|---|---|
| **Court of first instance** | A genuine fork / retrospective survives the steelman | the **merits** (the right design given the spec, code, invariants) | decide (build or kill) + record dissent | stands unless appealed |
| **Appeals Court** | a verdict is challenged with standing (DPR 2.2) | the **merits, as a review** - must engage the court below, not re-argue blind | uphold or **overturn** | stands unless taken to the Supreme Court |
| **Supreme Court** | the Appeals Court is challenged, or the question is of the highest invariant significance | **points of law only** - was the invariant spec + the method's discipline correctly *applied*? | set the controlling rule | becomes **spec law** - immutable precedent |

**DPR 7.1 - The merits/law split.** The first two tiers fight the merits; the Supreme Court is a court of *law,
not fact* - it does not re-decide the design, it rules on how the invariants and method bind a *class* of
decisions. Only the Supreme Court writes spec law.

**DPR 7.2 - The full record travels up.** A higher court is handed the complete record of every court below (all
pleadings, judgments, dissents, the bundle). A higher court that ignores the lower record is improperly
constituted.

---

## Part 8 - Bundles

**DPR 8.1 - When a bundle is required.** A case large enough to carry substantial record or to be appealed is
filed with a **bundle**: the compiled record below + a **table of authorities** (every case-law and spec-law
precedent relied on, by ID) + the evidence (the ground-truth cited). Small cases need no bundle (DPR 1.3).

**DPR 8.2 - References.** Every authority in the bundle is cited by ID (`SPEC-LAW-n`, or a reported case name);
every fact by `file:line` or command-output. A claim with neither is struck.

---

## Part 9 - Evidence and authority

**DPR 9.1 - Facts are proved by evidence.** A fact enters the record only on **ground-truth** - `file:line`, a
count, a command's output, a test run (LDD-INV-1). An advocate's assertion is not evidence.

**DPR 9.2 - Law is argued from authority.** A point of law is argued from **authorities**: the LDD-INV register
(the floor), spec law (`SPEC-LAW.md`), and reported case law (`CASE-LAW.md`). Authorities are cited, not proved.

**DPR 9.3 - Vacate on collapsed fact.** A holding resting on a fact later shown false is **vacated and re-decided
on re-grounded truth, never patched** (SPEC-LAW-1(c)).

---

## Part 10 - Case law and precedent

**DPR 10.1 - Standing judgments become case law.** A merits judgment that **stands** - because no appeal was
brought, or the Appeals Court/Supreme Court declined to disturb it - is recorded in
[`CASE-LAW.md`](CASE-LAW.md) as a **reported case**, citable as precedent in future cases.

**DPR 10.2 - Every report names its deciding court.** A reported case records *which court decided what* (first
instance / appeal / supreme), so that a later court can weigh it correctly.

**DPR 10.3 - The precedent hierarchy.** A Supreme Court ruling is **spec law** and binds every court absolutely. A
**Appeals Court** judgment binds the court of first instance and is strong persuasive authority on itself. A
**first-instance** judgment is persuasive, the weakest tier of authority. A court is bound by precedent from
courts above it and may follow, **distinguish** (show the instant facts differ), or - if it sits *higher* than the
court that decided the cited case - **overturn** it. A court may never overturn a precedent from a court above it;
spec law can be refined only by a later Supreme Court.

**DPR 10.4 - Citing case law.** Cite a reported case by its name and court (e.g. *In re the Court-Split* (first
instance)); cite spec law by ID (`SPEC-LAW-n`). A decision colliding with binding precedent is refused at the spec
layer, the fail-closed shape a trust boundary uses to deny an unmapped capability.

**DPR 10.5 - Provisional precedent; the court is not yet validated.** A precedent born from the method litigating
its **own** construction (a self-referential case) is **provisional**: it binds the originating project but does
**not** propagate to other projects until it has been applied and held in at least one real, external case.
Applying SPEC-LAW-2 to the court itself: the court has **not yet been exercised on a real external fork**, so its
reliability is **asserted, not demonstrated**. Treat its outputs as a fallible agent's reasoning, not a
verification guarantee; do not mark the court "works" or propagate a precedent on self-referential cases alone.

---

## Part 11 - Anti-over-litigation: the gates

**DPR 11.1 - Front gate (the steelman).** No bench is convened for a question with no surviving second side (DPR
5.2). The steelman decides ripeness, not the agent's appetite.

**DPR 11.2 - Apex gate (dismissal).** The Supreme Court may **dismiss** a petition presenting no genuine,
universal point of law (a merits question dressed as law, a one-off with no class to bind, or a point an existing
precedent already settles). A dismissed petition produces no spec law.

**DPR 11.3 - The default is consolidation.** When need is not demonstrated, the court takes the **narrowest lawful
step** and does not add structure. Spec law is clarified by *coverage of the points of law that matter, not by
volume*; the rate of new references tapers as the registers mature.

---

## Part 12 - Recording and immutability

**DPR 12.1 - Everything is recorded.** Every disposition is written to the ledger; reported cases to
`CASE-LAW.md`; Supreme rulings to `SPEC-LAW.md`. A Supreme judgment is recorded **in full** - every justice's
opinion, ratio, authorities, and self-dissent, never collapsed to only a synthesis.

**DPR 12.2 - Append-only (LDD-INV-16).** The registers are append-only. A precedent is never edited or deleted in
place; a later court supersedes it by a new entry that cites the one it narrows. The court rises and dissolves;
the *judgment* persists.

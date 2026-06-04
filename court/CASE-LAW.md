# CASE-LAW: the law reports

This is the body of **decided merits cases** - the law reports of the Log-Driven Development court. It is distinct
from the two other registers:

- **[`SPEC-LAW.md`](SPEC-LAW.md)** - apex *substantive* law (points of law; immutable; binds every court).
- **[`DPR.md`](DPR.md)** - the *procedure* (how a case runs).
- **CASE-LAW (this file)** - the *merits* precedents, by deciding court, citable and open to being distinguished
  or overturned by a higher court.

**Precedent hierarchy (DPR 10.3).** A Supreme Court ruling is **spec law** and binds absolutely. An **Appeals Court** judgment binds the court of first instance. A **first-instance** judgment is persuasive (the weakest
tier). A court may follow, **distinguish**, or - only if it sits *higher* than the deciding court - **overturn** a
reported case. A court never overturns a precedent from a court above it.

**Citing.** Cite a reported case by name and court, e.g. *In re the Court-Split* (first instance); cite spec law by
ID, e.g. SPEC-LAW-3. A decision colliding with binding precedent is refused at the spec layer.

**Immutability (LDD-INV-16).** Append-only. A report is never rewritten; a later court supersedes it by a new entry
citing the one it narrows. Each report records its **status** (stands / distinguished / overturned).

---

## CASE-1: *In re the Ledger→Log Rename* (first instance)

**Court.** First instance. **Date.** 2026-06-04. **Status.** Stands.

**Question.** On reviewer feedback that "ledger" reads as crypto, how should the methodology be renamed?

**Holding.** A *scoped, per-sense* rename, not a blind find-and-replace. The method **name** becomes
Log-Driven Development (the **LDD** acronym and every `LDD-INV` id preserved); the **artifact** vocabulary
("ledger" - intent ledgers, the twin-ledger spine) is **kept** by principal election. A blind sweep was refused:
it would corrupt downstream domain data models, break published installs, and rewrite immutable history.

**Ratio.** A rename of load-bearing terminology is a per-sense editorial act bounded by immutability (LDD-INV-16):
live methodology surface may be renamed; append-only records (journals, precedent text) are superseded going
forward, never rewritten.

**Authorities.** LDD-INV-16 (append-only history); principal election on the artifact word.

---

## CASE-2: *In re the Court-Split* (first instance → Appeals Court → Supreme Court)

**Court.** First instance (unanimous), Appeals Court (deadlocked 2-2), Supreme Court (5-0 on the point of law).
**Date.** 2026-06-04. **Status.** Stands; the point of law is reported as **SPEC-LAW-3** (*Reference re
Consolidation*), full panel at [`SPEC-LAW-3-panel.md`](SPEC-LAW-3-panel.md).

**Question (merits).** Should the deliberation court be packaged as a second installable unit, separate from the
method whose registers it reads?

**Holding (merits).** **No - keep the court in the one plugin.** First instance held unanimously to keep one unit;
the Appeals Court deadlocked 2-2; on reference, the Supreme Court settled the point of law and the merits
disposition stood.

**Ratio (as corrected by the Supreme Court).** The court is the method's judiciary, welded to it bidirectionally
(it applies `docs/invariants.md`, writes `SPEC-LAW.md`, and the method self-convenes it). The split was barred not
by an unwritten "one unit per repo" prong but by the **anti-bloat limb** of consolidation on **unmet demonstrated
need** - the pleaded cost asymmetry ("4.5M of dead weight") collapsed to ~20K on ground-truth.

**Authorities.** SPEC-LAW-3 (the point of law this case produced); SPEC-LAW-1(a),(c).

---

## CASE-3: *In re the Justice-System Reorganisation* (first instance)

**Court.** First instance (unanimous, 3-0). **Date.** 2026-06-04. **Status.** Stands; leave reserved to re-apply
for the partial gather (disposition A) on a future tree-verified consumer.

**Question.** How far should the repo be physically reorganised into subfolders separating the LDD method from the
justice system - (A) gather the justice system into one folder, (B) full method/+justice/ split, or (C)
logical-only (create the new artifacts in place, move nothing)?

**Holding.** **Disposition C (logical-only).** Author `court/DPR.md` and `court/CASE-LAW.md` in place and document
the method/justice boundary; **move no files**. Disposition B refused outright (plugin-unlawful - `skills/`,
`commands/`, `.claude-plugin/` auto-discover at root under `marketplace.json` `source: "./"` - and maximal
anti-bloat disturbance: a 498-file `tools/` subtree and 309 verified cross-links for nil function). Disposition A
refused **on this record**.

**Ratio.** Consolidation's source limb permits a justice subfolder (so A and C are both lawful), so the case turns
on the **anti-bloat limb** and its **demonstrated-need** gate. The claimant's sole need-ground - a "scattered DPR"
requiring gathering - was **falsified on ground-truth**: there is no `DPR` token in the tree (the grep hits were
`GDPR`/`DPA` privacy artifacts), and the artifacts did not yet exist. Under SPEC-LAW-3(d)/SPEC-LAW-1(c) that
collapsed premise was vacated; the genuine gap was **creation** (which C supplies), not relocation. "Cheapness is
not need." When need is not demonstrated, the default is consolidation - the narrowest lawful step.

**Authorities.** SPEC-LAW-3 (source limb (a); anti-bloat limb (b); demonstrated-need gate (2); vacate-on-collapsed-
fact (d)); SPEC-LAW-1(c); the plugin root-discovery constraint.

**Recorded dissent (standing for a future application).** The justice corpus is one concern; C risks fragmenting
it across `court/` and a new folder. The cure adopted on execution: the new artifacts live in `court/` alongside
`SPEC-LAW.md` (no new folder), keeping the corpus co-located while moving nothing. Leave is reserved to gather
into a dedicated `justice/` folder once a real consumer is demonstrated.

# Spec-law register (Supreme Council precedent)

This is the precedent register: the law the courts *write*. It is distinct from
[`docs/invariants.md`](../docs/invariants.md), the standing LDD-INV register the courts *apply*. A Supreme Council
rules only on points of law (how the invariant spec and the method's discipline were *applied*), and its ruling is
recorded here as a numbered, immutable precedent that **binds every future court**.

**Citing convention.** Cite a precedent by ID (SPEC-LAW-n) in any later decision; a decision that collides with a
precedent is refused at the spec layer, the same fail-closed shape a trust boundary uses to deny an unmapped
capability.

**Immutability (LDD-INV-16).** Entries are append-only. A precedent is never edited or deleted in place; only a
later Supreme Council, expressly narrowing it on a point of law, may refine it, by adding a new numbered entry
that cites the one it narrows.

**Propagation.** This register ships with the methodology. A project running LDD receives the current spec law by
installing or updating the plugin; the council skill reads this register when it convenes and enforces it. New,
generally-significant precedents reach every project as community pull requests against this file (see the README,
"Self-improving by construction"). A project may keep a separate local precedent file for genuinely
project-specific rulings; a local precedent shown to be general is promoted here by PR.

---

## SPEC-LAW-1: Preference is not evidence; controls are built not promised; collapsed facts are vacated not patched

**Origin.** A Supreme Council ruling on points of law arising from an appellate decision that (i) admitted a
principal's stated preference as "ground truth" and used it to overturn a reasoned security holding, (ii) relaxed
that security holding on the strength of a control that did not yet exist, and (iii) modified-in-place a lower
holding whose relied-upon fact had been falsified.

**The rule (three limbs):**

**(a) Preference is not ground truth.** A stakeholder's or principal's preference is never admissible as ground
truth (LDD-INV-1) and may not be entered as evidence to overturn a finding that rests on tree evidence. A
principal may record a policy or risk-acceptance as a *principal override of record* (an append-only superseding
entry, LDD-INV-16); such an override confers standing to appeal (LDD-INV-17) but is never itself the evidence that
decides the merits, and it may not on its own flip a fail-closed security gate.

**(b) No-IOU security control (red-until-built).** A security or trust-boundary holding may be relaxed only by a
control that is buildable and verifiable in the tree, a red-until-built check a gate can find and flip (LDD-INV-12,
LDD-INV-15). It may never be relaxed by an instrument outside the tree (a contract, a policy document, a promise, a
future signature) or by a preference. "Allowed, conditional on a control that does not yet exist" is a deferral
disguised as a control, which the build-or-kill rule forbids (LDD-INV-7, LDD-INV-8). The lawful dispositions for a
security question are a present, fail-closed, verifiable control, or a kill.

**(c) Vacate on collapsed fact.** When a relied-upon, load-bearing ground-truth is shown false (LDD-INV-1,
LDD-INV-2), the holding it carried is vacated and re-decided on re-grounded truth as a new superseding entry
(LDD-INV-16). A court may not modify such a holding in place to preserve its conclusion, even when that conclusion
is independently defensible: a right answer reached through a falsified premise still corrupts the audit trail the
method exists to keep honest.

**What it prevents.** Power laundering a decision through the court's evidentiary authority; security gates turned
green on promises rather than built controls; and falsified premises surviving under a fresh label.

**Status:** immutable; binds every Council, Appeals Council, and the spec layer. Refined only by a later Supreme
Council expressly narrowing it on a point of law.

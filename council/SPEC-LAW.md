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

---

## SPEC-LAW-2: The Determination of Genuine Function is a ground-truth gate, scoped to what the spec claims, over the layers you own

**Origin.** A Supreme Council ruling on points of law arising from a determination of whether a built system
"genuinely supports" its target use cases. The lower courts had been pressed to (i) accept design-soundness ("the
primitives exist and compose") as a discharge of the Determination of Genuine Function, (ii) re-narrow the
function claim to a sub-scope smaller than the spec's own definition-of-done, and (iii) drop the
product-facing surfaces out of the claim by reclassifying them as a consumed commodity.

**The rule (four limbs):**

**(a) Ground-truth, not assertion.** A court discharges the **Determination of Genuine Function** (the council
skill's required determination phase) only by pointing to a spike, a test, or a demonstrated end-to-end path.
"The pieces exist", "the design is sound", and "it composes by design" meet the *design-sufficiency* bar only,
which is necessary and never sufficient. A seat that asserts function without exercising it is ignored on that
point. Where function is unproven at the claimed scope, the verdict may not resolve to build / ratify / uphold; it
resolves to **spike-first** (obtain the ground-truth, then re-determine) or **kill**. A court may not ratify a
hypothesis.

**(b) Scope is what the spec claims, not what a party prefers.** Genuine function is measured at the scope the
spec itself names in its definition-of-done, not a scope a court or party finds convenient. A party may not
re-narrow the claimed scope by re-reading the spec to mean less than it says (LDD-INV-1, LDD-INV-2). Only a new
ratified decision of record (an append-only superseding entry, LDD-INV-16) may move the scope; a court's
construction of the existing spec may not.

**(c) Own/consume is a layer parse, and you cannot shrink the claim by reclassifying an owned layer as consumed.**
Where the architecture distinguishes *consumed* commodity layers (the bought/adopted engine, driver, runtime,
upstream chrome) from *owned* differentiating layers (the project's moat: its core, its governance, and its
product-facing surfaces), the genuine-function claim covers the **owned** layers proven at the spec-named scope.
Consuming a commodity *engine* is not consuming the *surfaces built over it*; the move "the upstream tool is
consumed, therefore the screens we built on it are out of the claim" conflates the two and is **barred**.

**(d) The autonomous determination instrument and the gated final run are distinct.** A spike that exercises the
owned layers *autonomously* is the strongest determination reachable without the principal and, under build-first
discipline, is sequenced **first** as the kill-or-confirm gate. A final end-to-end run that needs the principal (a
live environment, real data, a human-gated resource) is the **final** determination and stays gated. Proving the
first does not discharge the second; failing the first is the kill signal. The two must not be conflated, in
either direction.

**What it prevents.** "Looks done / composes on paper" laundered into a discharge of the function gate; the
function claim quietly shrunk below the spec's own definition-of-done; and the product-facing surfaces dropped from
the claim by relabelling them commodity. Together with SPEC-LAW-1, it keeps both the *evidence* and the *scope* of
a determination honest.

**Status:** immutable; binds every Council, Appeals Council, and the spec layer. Refined only by a later Supreme
Council expressly narrowing it on a point of law.

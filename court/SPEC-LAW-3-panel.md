# SPEC-LAW-3 (*Reference re Consolidation*): the full Supreme Court panel (the record behind the precedent)

This is the verbatim panel record for [`SPEC-LAW-3`](SPEC-LAW.md). The synthesised controlling rule is the
precedent; this file preserves every justice's opinion, ruling, grounding, and self-dissent in full, per the
deliver-and-record-in-full discipline (LDD-INV-16). The panel held **5-0** on the construction
(`SOURCE-WITH-ANTIBLOAT-LIMB`); the disposition that follows for the originating fork is that the second
installable unit is **barred** (it clears the source limb but fails the anti-bloat limb on demonstrated need, and
fails severability on a bidirectional coupling), with the lower court's outcome upheld but its reasoning corrected.

The court arc that produced it: a first-instance Court (unanimous to keep one unit) → an Appeals Court
(deadlocked 2-2) → this Supreme Court (5-0 on the point of law).

---

## Justice Textual-Limb (the plain-words-and-both-clauses justice)

**Philosophy.** Textualism: construe LDD-INV-9 from its own enacted words and enumerated objects alone. Refuse to
read in an unwritten prong ("one installable unit per repo") the text never names; equally refuse to read OUT a
written clause ("the anti-bloat veto: do not add tools") the text plainly contains. The rule is its two enacted
sentences, no more and no less.

**Construction held.** SOURCE-WITH-ANTIBLOAT-LIMB.

**Application review.** The Appeals "INV-9 construction" seat erred by reading only the first sentence and treating
its enumerated objects ("a parallel system, store, service, or enforcer") as the rule's whole reach. INV-9 enacts
TWO operative clauses in one breath: the source-of-truth clause and the express anti-bloat veto. A textualist may
not amputate the second to reach a result the first allows. So the seat is RIGHT that the count of manifests is
not itself a named prohibited object (the first limb does not bind unit-count) but WRONG that INV-9 therefore says
nothing about a second installable surface: the second limb independently restrains added machinery absent
demonstrated need. Conversely the first-instance Court erred in importing a freestanding "one installable unit
per repo" prong into the first limb. The Appeals "Wisdom" seat applied the law most faithfully (restraint located
in the anti-bloat half; SKILL.md:114-115 read as additive-over-a-mandatory-floor). Per SPEC-LAW-1(c) the pro-split
disposition rested on a collapsed fact (the "4.5M" cost), so the anti-bloat limb's demonstrated-need gate is
simply unmet on this record.

**Controlling rule (as proposed).** LDD-INV-9 binds on two independent limbs, neither of which a court may read out
or extend. LIMB ONE (source-of-truth) binds FACTS; it does NOT bind the count of installable/packaging units. A
second unit that references a single root-owned register by relative path, co-versioned, is a permitted regenerable
VIEW. LIMB TWO (anti-bloat) independently restrains added machinery and bars it absent demonstrated, tree-verified
need. The test is CONJUNCTIVE: lawful only if (1) it adds no second owner of any fact (one copy, one version, at
root; reference never vendor; fail-closed on revision skew) AND (2) the proponent demonstrates need by present tree
evidence, not assertion nor a premise later falsified (cf. SPEC-LAW-1(c)). Demonstrated bidirectional coupling
weakens the separable-module case but is not by itself dispositive. Default, when need is not demonstrated:
consolidation.

**Grounding.** LDD-INV-9, LDD-INV-10, LDD-INV-16, SPEC-LAW-1, SPEC-LAW-2.

**Self-dissent (verbatim).** "The strongest argument against my holding is that a true textualist should stop at the
first limb and let the disposition follow. INV-9's only ENUMERATED prohibited objects are 'a parallel system,
store, service, or enforcer'; a packaging manifest is none of these, and the second sentence's 'do not add tools'
is, on its face, about TOOLS and HEAVY PASSES (the closure-gate/scanner economy), not about installation manifests
at all. By stretching 'anti-bloat' from its enumerated targets (tools, heavy passes) to cover 'manifests and
parallel amendment surfaces', I have done the very thing I condemn in the first-instance Court: imported an
object the text does not name into INV-9's reach, merely relocating the unwritten prong from Limb One to Limb Two.
A disciplined textualist would hold that INV-9 simply does not reach unit-count on EITHER limb, that a co-versioned
reference-only second manifest is lawful full stop under Limb One, and that the correct ground for refusing the
split is not INV-9 at all but the ordinary build-or-kill / demonstrated-need discipline (LDD-INV-7/8) - leaving
INV-9's anti-bloat clause confined to the tool-and-pass economy its own words enumerate. On that reading my
Limb-Two 'added surfaces' gloss is itself an unwritten extension and should be struck."

---

## The Purposive Justice (the drift-failure lens)

**Philosophy.** Purposive construction: an invariant binds whatever, left unbound, would produce the FAILURE it was
written to prevent. INV-9's stated failure is "the original sin that makes a codebase (and a methodology) a mess:
three completion paths, three definitions, two duplication enforcers with no stated owner" - duplicate OWNERS of
one fact, and unowned accreted MACHINERY. Read to reach exactly that failure, no wider, no narrower; honour both
its limbs.

**Construction held.** SOURCE-WITH-ANTIBLOAT-LIMB.

**Application review.** BOTH the pro-split appeals seats AND the first-instance majority misapplied INV-9, in
opposite directions, and each rested on a collapsed fact - so under SPEC-LAW-1(c) those holdings are vacated, not
patched. (1) The Appeals "INV-9 construction" seat read INV-9 as a pure SOURCE rule with an exhaustive object list,
ignoring the anti-bloat second limb, and misread SKILL.md:114 as a "swappable default floor" when the same line
says "the floor every LDD run is bound by" (mandatory, layered-on-top). Vacated. (2) The "Mechanics" seat and the
first-instance dissents leaned on the one-directional-dependency premise as the separable-module signal; that is
FALSE on the tree (the method self-convenes the court, SKILL.md:63-69 → bidirectional). Vacated. (3) The
first-instance majority and the pro-split cost case leaned on a "4.5M dead weight" figure ground-truth falsifies
(skills ~580K; court ~20K; the 3.6M is tools/vibe, pip-installed, never copied). Re-grounded. The
correctly-reasoned seats were Appeals "Wisdom" (bidirectional coupling, mandatory floor, anti-bloat) and "Reuse
reality" (falsified cost).

**Controlling rule (as proposed).** INV-9 carries TWO limbs; test a split against BOTH. Limb one binds SOURCES OF
TRUTH, not the count of units; a single-referencing, non-vendoring unit is a regenerable VIEW. Limb two (anti-bloat)
restrains added machinery/parallel surfaces; a second installable unit IS added machinery (a second
amendment/maintenance surface) and must EARN its existence. Lawful only on three conjunctive gates: (a) single-
source integrity (one copy, one version at root, reference-not-vendor, fail-closed on revision skew); (b)
demonstrated need on ground-truth, not stated preference or speculative audience (SPEC-LAW-1(a),(c)); (c) coupling
severability (mutual referral = one concern wearing two manifests, which anti-bloat bars). Fail any gate → unlawful.
Absent a passing showing, consolidation is the default.

**Grounding.** LDD-INV-9 (both limbs) and its "Prevents" clause, LDD-INV-10, LDD-INV-16, SPEC-LAW-1(a), SPEC-LAW-1(c),
SPEC-LAW-2(a).

**Self-dissent (verbatim).** "The strongest argument against my holding: by importing the anti-bloat limb as a
SECOND binding gate, I have arguably let INV-9 reach the very thing its enumerated objects ('parallel system, store,
service, or enforcer') deliberately did NOT name - an installable unit / manifest / bundle. The Appeals 'INV-9
construction' seat is textually correct that the rule names no 'install/bundle/manifest', and a purposive court
should be slow to read an unwritten fourth object ('one installable unit per repo') into an immutable invariant;
doing so risks exactly the construction-by-court that SPEC-LAW-2(b) bars when it forbids re-reading a spec to mean
MORE (or less) than it says. On the cleanest reading, INV-9's failure mode is dual OWNERSHIP of a fact, and a second
manifest that single-sources a root register triggers no dual ownership at all - so the pure SOURCE construction (i)
is the faithful one, the count of manifests is simply outside the rule, and my anti-bloat gate (b)/(c) smuggles a
merits judgment ('was the second unit worth it?') into what should be a pure question of law, trespassing on the A/B
merits this court is forbidden to re-decide. Under that view the lawful holding is the narrow SOURCE construction
with a single closure-gate condition (a) and nothing more, leaving need and coupling to the merits courts below."

---

## Justice of Application-Review (the apex audits whether the rule below was the written rule, applied to true facts)

**Philosophy.** Application-review fidelity under SPEC-LAW-1(c): a court may only apply the invariant AS WRITTEN to
facts ground-truth bears out. A holding reached by reading an unwritten prong into an invariant, OR resting on a
collapsed fact, corrupts the audit trail even where the disposition is independently defensible. Rules on the
construction of the law and the soundness of its application, never on whether A or B is the better design.

**Construction held.** SOURCE-WITH-ANTIBLOAT-LIMB.

**Application review.** Two distinct errors below; both constructions advanced in isolation misapply INV-9. ERROR 1:
the first-instance Court held "a split would itself violate LDD-INV-9" by treating the COUNT of units as a per-se
prohibited object - reading an unwritten "one installable unit per repo" prong into the rule. INV-9's enumerated
prohibited objects are exhaustively "a parallel system, store, service, or enforcer," and a referencing,
non-vendoring second manifest is on its face a regenerable VIEW. To that extent the Court MISAPPLIED INV-9. ERROR
2: the Appeals "INV-9 construction" and "Mechanics & cost" overturns rested on TWO collapsed facts - the "separable
one-directional module" signal (false: SKILL.md:63-69 self-convenes; SKILL.md:136 reads registers at convene time →
bidirectional and live) and the "swappable default floor" reading (false: SKILL.md:114-115 = additive over a
MANDATORY floor). Under SPEC-LAW-1(c) an overturn carried by collapsed premises is VACATED, not patched. CORRECT
APPLICATION: INV-9 is two-headed; the count of manifests escapes the SOURCE head but is squarely within the
ANTI-BLOAT head. On re-grounded facts (court skill ~20K, the 3.6M is pip-installed tools/vibe, reuse audience
already served with zero in-tree consumers) the second unit is added machinery the anti-bloat limb bars absent
demonstrated need, and need is unproven. The merits outcome is left undisturbed; only the anti-bloat limb, on
re-grounded facts, lawfully carries it.

**Controlling rule (as proposed).** INV-9 is TWO-LIMBED; decide a split under BOTH. (a) SOURCE LIMB binds owners of
facts, not unit-count; a referencing, non-vendoring surface is a permitted VIEW, and voiding a split solely because
it adds a unit reads in an unwritten prong. (b) ANTI-BLOAT LIMB independently bars added machinery (a second unit
included) absent DEMONSTRATED NEED. Conjunctive three-part test: (1) single-owner integrity (one copy, one version,
reference-not-vendor, fail-closed on revision skew); (2) demonstrated need on ground-truth, against VERIFIED
figures; (3) severability (no live bidirectional coupling). Pass all three → permitted; fail any → barred. A holding
resting on a collapsed ground-truth is vacated and re-decided, never patched (SPEC-LAW-1(c)).

**Grounding.** LDD-INV-9, LDD-INV-10, LDD-INV-16, LDD-INV-1, LDD-INV-2, SPEC-LAW-1, SPEC-LAW-2.

**Self-dissent (verbatim).** "The strongest argument against this holding is that it is itself a covert merits
re-decision dressed as law. By erecting a three-part conjunctive test whose limbs (2) and (3) reach the very
'demonstrated need' and 'separability' questions the courts below fought over on the merits, the apex has not merely
stated how INV-9 binds a CLASS of decisions; it has supplied the dispositive analysis for THIS one and thereby
resolved A-vs-B under the banner of law, trespassing the merits/law split that SKILL.md:102-109 reserves to the
courts below. A purer application-review ruling would have stopped at the construction point (INV-9's SOURCE limb
does not reach unit-count; the Court read in an unwritten prong; the Appeals overturn rested on collapsed facts)
and REMANDED to a re-grounded Court to apply the anti-bloat limb to the corrected facts, rather than the apex
itself finding 'need is unproven' - a finding of fact the apex is constitutionally barred from making. The risk is
that future courts cite SPEC-LAW-3's test (2)/(3) as license for the Supreme tier to decide design questions
whenever it can characterise the fork as turning on an invariant, eroding the very trial-court primacy this method
depends on."

---

## Justice of the Anti-Bloat Limb (the severable-veto lens)

**Philosophy.** INV-9 is a two-limb invariant and the limbs are independently operative. The first (single-source)
governs FACTS: one owner per concern, every other surface a regenerable view that CITES the owner. The second (the
anti-bloat veto) governs MACHINERY: it restrains the proliferation of standing surfaces, enforcers, and amendment
points even where no fact is duplicated. A packaging change can clear the first yet be barred by the second when its
justifying consumer is hypothesised rather than demonstrated. Read against SPEC-LAW-2(a): a court may not ratify a
hypothesis; a second installable unit justified by a speculative audience is the packaging-tier instance of that.

**Construction held.** SOURCE-WITH-ANTIBLOAT-LIMB.

**Application review.** BOTH appellate OVERTURN seats erred the same way: they read only the first limb and treated
the anti-bloat veto as absent. The "INV-9 construction" seat is CORRECT that the enumerated objects don't literally
name "manifest/bundle" and that the first-instance Court over-read an unwritten "one installable unit per repo"
prong into the source limb - but it then committed the mirror error, concluding that because B clears the source
limb it is lawful, skipping the anti-bloat limb. A second manifest IS added machinery / a standing enforcer-class
surface within the plain reach of the veto. The "Mechanics & cost" seat compounded this by resolving a MERITS
question (near-zero build cost, the plugins[] array) - cost-of-implementation is design taste reserved below, and
near-zero BUILD cost does not answer the anti-bloat limb's concern, which is standing MAINTENANCE/amendment surface,
not bytes. The "Wisdom" and "Reuse reality" seats applied the law correctly (bidirectional coupling; falsified cost).
The first-instance Court reached the right disposition on a partly wrong premise (the unit-count prong); under
SPEC-LAW-1(c) that premise collapses and the holding is re-grounded on the anti-bloat limb + demonstrated-consumer
test rather than patched.

**Controlling rule (as proposed).** Two independently-operative limbs; clear BOTH. The single-source limb binds
sources of truth, not the count of units; a non-vendoring reference is a permitted VIEW and a court may not read an
unwritten "one unit per repository" prong. The anti-bloat limb binds standing machinery independently: a new
maintenance/amendment/enforcement/version-co-binding surface is restrained even where it duplicates no fact, and is
lawful only on (a) cleared source limb AND (b) demonstrated, in-tree consumer/need - a present spike, test, existing
dependent, or shipped consuming path, never hypothesised/future. A court may not ratify a packaging split on a
hypothesised consumer (SPEC-LAW-2(a)); the burden rests on the proposer. Bidirectional/live convene-time coupling is
evidence against separability and weighs the presumption toward denial. Build-cost does NOT discharge the limb.

**Grounding.** LDD-INV-9, LDD-INV-16, SPEC-LAW-1, SPEC-LAW-2.

**Self-dissent (verbatim).** "The strongest argument against my holding: by elevating the anti-bloat clause into a
second, independently-dispositive LIMB with its own demonstrated-consumer burden, I may be manufacturing the very
'unwritten prong' I fault the first-instance Court for inventing. INV-9's text presents anti-bloat as a GLOSS on
the single-source rule ('This is the load-bearing invariant of this register AND the anti-bloat veto') describing
the same concern (proliferating OWNERS of a fact), not as a free-standing veto over packaging that holds no fact. On
that reading the 'INV-9 construction' appellate seat is simply right: the enumerated prohibited objects are 'parallel
system, store, service, or enforcer' - a referencing manifest is none, B forks no register, and the matter ends
there; importing a demonstrated-consumer burden onto lawful, fact-free packaging is itself the kind of judicial
over-reach SPEC-LAW-2(b) forbids (re-reading the rule to mean MORE than it says). Further, placing the burden of a
'demonstrated consumer' on a reversible, single-sourced packaging choice inverts the method's own build-bias for
swappable choices (SKILL.md:56: reversible choice gets one sentence, bias to building), and risks freezing benign
modularity behind a litigation gate the invariant never wrote."

---

## Justice of Standing and Amendment Surfaces (Constitutional construction)

**Philosophy.** Constitutional/standing: do not ask which design is better; ask what kind of surface a proposed
second consumption unit creates, and whether the question is one of LAW (who may amend the binding registers, and
how many independent amendment surfaces the constitution tolerates) or merely of engineering (a closure-gate
forecloses drift). INV-9 is a constitutional provision governing ownership and the proliferation of governing
surfaces, not file counts. The test for a lawful split is a standing test, not a size test.

**Construction held.** SOURCE-WITH-ANTIBLOAT-LIMB.

**Application review.** Both lower courts erred in opposite directions. The Appeals "INV-9 construction" seat read
INV-9 as binding SOURCES ONLY, ignoring the second limb that sits in the same sentence; a second unit is not a new
source of truth (the source limb does not reach it) but IS added governing machinery (the anti-bloat limb does).
The first-instance Court and "Wisdom" seat reached the right disposition-zone on a partly collapsed premise (the
unwritten unit-count prong); under SPEC-LAW-1(c) the source-limb reasoning is vacated and the conclusion survives
only if re-seated on the anti-bloat limb. The appeal's ENGINE - the one-directional-dependency separable-module
signal - is FALSIFIED on the tree (SKILL.md:63-69 self-convenes; SKILL.md:136 reads registers at convene time →
bidirectional, live), and the 4.5M cost figure is collapsed (skills 580K; the 3.6M tools/vibe is pip-replaced).
CORRECT APPLICATION: INV-9 binds sources absolutely and added governing machinery presumptively; a second unit is
lawful only if it (a) creates no second owner/amendment surface for any register and (b) overcomes the anti-bloat
presumption with demonstrated, in-tree need. This is LAW because it is about who may amend the binding registers
and how many independent governing surfaces the constitution tolerates - not about whether a closure-gate could
mechanically foreclose drift (necessary, never sufficient).

**Controlling rule (as proposed).** Consolidation (INV-9) binds SOURCES OF TRUTH absolutely and ADDED GOVERNING
MACHINERY presumptively; it does not count installable units. Two limbs; a split is lawful only if it clears BOTH.
(a) Source limb (absolute): forbids a SECOND OWNER of any fact; a referencing, non-vendoring second unit is a
regenerable VIEW; a unit that copies/vendors/re-hosts a register is a parallel enforcer barred outright regardless
of file count. (b) Anti-bloat limb (presumptive): a new parallel surface adding a durable maintenance/amendment/
enforcement/version-co-binding point is presumptively barred, overcome only by demonstrated in-tree need; near-zero
cost does not discharge it. (c) Standing test (LAW not engineering): does the second unit create an independent
surface on which any binding register may be amended? If yes → fails the source limb, barred. If no → a permissible
view that must still clear the anti-bloat limb on demonstrated need. A closure-gate foreclosing revision-skew is
NECESSARY but NEVER SUFFICIENT to authorise a second governing surface. Bidirectional/live convene-time dependency
is evidence against separability. (d) Vacate-on-collapsed-fact (SPEC-LAW-1(c)): any holding resting on a one-
directional-dependency, swappable-floor, or cost/size premise is vacated when ground-truth falsifies it.

**Grounding.** LDD-INV-9, LDD-INV-16, LDD-INV-1, LDD-INV-2, SPEC-LAW-1, SPEC-LAW-2.

**Self-dissent (verbatim).** "The strongest argument against my holding is that I have smuggled an engineering
forecast into a question I claim is pure law. If, as ground-truth shows, the second unit references a single
root-owned register by relative path and a closure-gate fails-closed on register-revision skew, then NO second
amendment surface can ever come into being - the standing harm I invoke is foreclosed by construction. On that view
the anti-bloat limb collapses into ordinary engineering judgment (is the marketplace plugins[] array entry worth its
keep?), which is precisely the merits reserved to the courts below and the principal, and the apex has no business
converting a defeasible drift-risk into a constitutional bar. The honest reading of INV-9's text is that its
prohibited objects are 'a parallel system, store, service, or enforcer' - a manifest that owns no fact and enforces
nothing of its own is none of these - so a fact-free rule faithful to the text would hold that the COUNT of units is
outside INV-9 entirely and the second limb I lean on is an anti-bloat HEURISTIC, not a binding standing rule. Under
that dissent the lawful precedent is the pure SOURCE construction, and whether to ship a second manifest is a merits
call this court should have remanded, not constrained."

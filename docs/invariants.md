# LDD-INV: the method invariant register

Invariants exist at two levels in LDD, and confusing them is itself a failure mode. **PROJECT invariants** are an
OUTPUT of a run: they are the rules a rebuilt system must hold (Tasky's "a task below `done` drops everything it
blocks", a tenant-isolation rule, a money-path authz rule). They are distilled out of the harvest, written into
the project's spec, enforced by that project's tests and closure-gate, and ruled on by that project's deliberation
court. They live in the distilled spec, not here.

**METHOD invariants** are different: they are the rules any LDD run must hold to be an LDD run at all, and they are
part of LDD itself, not produced by it. This register is them. Where a project invariant answers "what must the
software do?", a method invariant answers "what must the process do, every time, or it is not LDD?". They are
numbered LDD-INV-1..N so that any surface (a skill, a doc, a tool config, a gate, a council brief) can CITE the
number instead of restating the rule (LDD-INV-9). Each entry below is a one-line statement, the failure it
prevents, and where in this repo it is enforced (file:line). The register is the single owner of "the rules of the
method"; every "rules you do not break" / "standing disciplines" / "smell test" surface should cite this register
rather than re-list a divergent subset (the divergence that this register exists to cure: see LDD-INV-12 and the
note under LDD-INV-1).

---

## LDD-INV-1: Ground-truth, no vibes

**Rule.** Every claim, finding, and "it is done" cites real tree evidence (`file:line`, command output, a count, a
test run); a claim you cannot point at, you do not know yet, and it does not enter the record.

**Prevents.** Confident fiction: an agent asserting "there is one completion path" until a grep finds three.

**Enforced at.** `skills/log-driven-development/SKILL.md:82` (rule), `:35-37`, `:114-116`;
`docs/methodology.md:178-184`; `docs/playbook.md:31-34`; `docs/systems.md:253-255`; anti-pattern #4
`docs/anti-patterns.md:94-112`; smell `docs/anti-patterns.md:376`. The coded loud-skip (a missing tool is a
reported `[warn]`, never a silent absence) is the gate-level expression of "never silently absent":
`tools/closure-gate/closure_gate.py:73-77,87-90`; `tools/closure-gate/closure-gate.toml:60-64`.

## LDD-INV-2: Provenance or it does not go in

**Rule.** Anything describing the legacy cites the exact file and line; a harvest claim with no citation is removed
or marked `(UNVERIFIED)` for someone to ground-truth. This extends to security and structural intent, not just
domain rules (see LDD-INV-15).

**Prevents.** A vibe entering the harvest record and calcifying into a false requirement the rebuild then honours.

**Enforced at.** `docs/artifacts.md:20-22` (the governing rule of every artefact), `:69-71`; named "the rule that
matters most" `docs/methodology.md:392-394`; `docs/methodology.md:140-142`;
`skills/log-driven-development/SKILL.md:91-93`; `docs/systems.md:265-266`; the harvest template
`templates/intent-ledger.md:14-15`; anti-pattern #4 `docs/anti-patterns.md:104-105`.

## LDD-INV-3: One-writer rule

**Rule.** Only the orchestrator (the main loop) writes shared state: the ledgers, the index, the spec, the task
list, the sign-offs. Spawned agents RETURN their what/why as text; the orchestrator integrates serially.

**Prevents.** Collision and lost writes when many agents append to one surface at once.

**Enforced at.** `skills/log-driven-development/SKILL.md:83` (rule), `:48-50`, `:117-119`;
`docs/methodology.md:186-192`; `docs/playbook.md:65-69,183-184`; `docs/systems.md:256-258`; anti-pattern #8
`docs/anti-patterns.md:179-197`; smell `docs/anti-patterns.md:382`.

## LDD-INV-4: File-partition (author in parallel, integrate serially)

**Rule.** Parallel authors own distinct NEW files; never two agents on one file. For a hot shared file, agents
RETURN content blocks, a coherence agent emits an integration checklist, and the orchestrator applies it serially.

**Prevents.** Two agents racing on one file and corrupting it.

**Enforced at.** `skills/log-driven-development/SKILL.md:84` (rule), `:67-68`, `:120-123`;
`docs/methodology.md:194-201`; `docs/playbook.md:120-121`; `docs/systems.md:259-261`; anti-pattern #3
`docs/anti-patterns.md:73-91`; smell `docs/anti-patterns.md:383`.

## LDD-INV-5: "Done" is the orchestrator's judgement (and the clean sweep, not "tests pass")

**Rule.** "Done" is the orchestrator's call after ground-truthing from a clean checkout, and at project level it
means the closure sweep finds zero gaps, never "the tests pass" alone and never a worker's self-report. The
closure sweep has TWO legs and "done" requires BOTH on record: (a) spec -> internal coherence (the id-graph
resolves, no cross-doc contradiction, every claim is provenanced, traceability holds) AND (b) source -> spec
coverage: a re-walk of every harvest source asking "what load-bearing detail lives here that never reached the
spec?", run as a LOOP-UNTIL-DRY whose evidence base is the source ranges plus the ledger drop-lists, NOT the
spec. An internal-coherence sweep audits the spec against itself and is structurally blind to an omission (an
omission leaves no contradiction); the source-coverage leg is the only one that can see it. A FREEZE/done
verdict with no source-coverage sweep on record is not done. (The coverage bar is "every load-bearing PROCEDURE
reached the spec", not "every source byte" - LDD-INV-13 still governs; do not let the coverage loop drag the
spec toward transcription.)

**Prevents.** A milestone marked done because a worker said so, or because the tests pass while spec surfaces remain
unbuilt; and the subtler failure this register was itself amended for: an internally-consistent spec graded
"complete" while a whole layer of the source (e.g. the step-by-step domain procedure) sits un-folded and unseen,
because no gate ever looked back at the source.

**Enforced at.** `skills/log-driven-development/SKILL.md:85` (rule), `:42-43`, `:111`, `:171-172`;
`docs/methodology.md:129-132` ("Done" = zero-gap sweep, the headline rule); `docs/playbook.md:48-52,245-275`;
`docs/systems.md:188-189,262-264`; `tools/closure-gate/closure_gate.py:7-8,30-32`;
`tools/closure-gate/README.md:9-11`; anti-pattern #2 `docs/anti-patterns.md:50-69` and (the source-coverage leg)
anti-pattern #18 `docs/anti-patterns.md:407-437`; smell `docs/anti-patterns.md:377,493`.

## LDD-INV-6: Commit per beat with explicit paths

**Rule.** Every beat ends in a commit with explicit paths (`git add <path>`), one coherent unit, plus the co-author
trailer; never a blanket `add -A` / `add .` (it sweeps build artefacts).

**Prevents.** Unattributable, unbisectable history and accidental staging of artefacts.

**Enforced at.** `skills/log-driven-development/SKILL.md:86` (rule), `:46-47`, `:165-166`;
`docs/playbook.md:60-63`; `docs/systems.md:269-270`; anti-pattern #5 `docs/anti-patterns.md:114-132`; smell
`docs/anti-patterns.md:378`.

## LDD-INV-7: Fix security the moment it is found

**Rule.** A security issue is fixed when found, before any commit, ahead of every schedule; it is never deferred
and never deliberated (a security issue is not a council question).

**Prevents.** A known hole (Tasky's no-expiry share link) surviving the rebuild because it was filed for later; a
leaked credential becoming permanent git history.

**Enforced at.** `skills/log-driven-development/SKILL.md:87` (rule), `:44-45`, `:61`;
`docs/playbook.md:54-58,97`; `docs/systems.md:267-268`; the per-commit security gate that makes "fix the moment
found" have something that FINDS: `tools/closure-gate/closure-gate.toml:18-26,69`;
`tools/closure-gate/closure_gate.py:17-18,157-162`; the hook forbids skipping it
`tools/closure-gate/pre-commit:21-27`; the security suite's fix discipline (structural fix, not a blocklist patch)
`skills/security/methodology.md:125,243-246`; anti-pattern #13 `docs/anti-patterns.md:284-303`; smell
`docs/anti-patterns.md:388`.

## LDD-INV-8: A council ends in build-or-kill

**Rule.** A panel, audit, or council always terminates in a committed change or an explicit kill the same beat,
never another doc that defers. The seats are ephemeral; only the verdict and the surviving dissent persist.

**Prevents.** Decision-theatre: a deliberation that produces a meeting and "we will look at it later" instead of a
commit. (The meta-to-build ratio is surfaced honestly: more councils than shipped milestones is itself a finding.)

**Enforced at.** `skills/log-driven-development/SKILL.md:88` (rule), `:58`, `:124-128`;
`skills/council/SKILL.md:70-76`; `docs/methodology.md:203-212,312-313`; `docs/playbook.md:93,99-102`;
`docs/systems.md:134-136,160-163,170-174`; anti-pattern #6 `docs/anti-patterns.md:135-153`; smell
`docs/anti-patterns.md:380`.

## LDD-INV-9: Consolidation over fragmentation (ONE owner per concern)

**Rule.** When a new need resembles an existing one, fold it in; never spin up a parallel system, store, service,
or enforcer. One source of truth per fact; every other surface is a regenerable view that CITES the owner. This is
the load-bearing invariant of this register and the anti-bloat veto: do not add tools, do not make heavy passes
routine, push only the cheap edge of each suite into the continuous tier and keep heavy passes risk-triggered under
one owner.

**Prevents.** The original sin that makes a codebase (and a methodology) a mess: three completion paths, three
function-length numbers, three definitions of "Tier 2", two duplication enforcers with no stated owner.

**Enforced at.** `skills/log-driven-development/SKILL.md:134-135` (rule); `docs/methodology.md:226-231`;
`docs/systems.md:271-273`; the security side ("one authoritative folder; other engines call this suite instead of
duplicating security methodology") `skills/security/README.md:11`; the refactoring side (security delegated, not
duplicated) `skills/refactoring/SKILL.md:24-29`; the continuous-tier one-security-owner declaration
`tools/closure-gate/closure-gate.toml:18-26`; `tools/closure-gate/closure_gate.py:17-18`. The canonical
one-owner-per-concern table is the **two-tier(+) ownership matrix** in `docs/systems.md` (system 7); every gate and
doc cites it rather than restating ownership.

## LDD-INV-10: The duplication ratchet is held by folding, never raised

**Rule.** The cross-module duplication budget is a number you only ever HOLD or LOWER by folding duplication into
one shared function; you never raise it to make a commit pass. If you genuinely must accept new duplication, edit
the config by hand and journal the reason so the concession is on the record, never hidden in a passing commit.

**Prevents.** Quality drift: agents accreting duplication until the rebuild is the mess being escaped.

**Enforced at.** `skills/log-driven-development/SKILL.md:129-132` (the closure-gate discipline);
`docs/methodology.md:214-224`; `docs/playbook.md:144-146`; `docs/systems.md:197-200`; code-enforced
`tools/closure-gate/duplication_ratchet.py:4-7,24-32,244-260` (`--update-budget` "REFUSES to raise");
`tools/closure-gate/closure-gate.toml:77-84`; `tools/closure-gate/README.md:68-85`; anti-pattern #1
`docs/anti-patterns.md:36-46`; smell `docs/anti-patterns.md:379`.

## LDD-INV-11: Stand up the closure-gate before the walking skeleton

**Rule.** The continuous closure-gate is stood up BEFORE the first line of the rebuild, so "clean" is checkable from
the start. It runs on every commit (Tier 1, continuous), which is exactly what lets the milestone STRUCTURE and
SECURITY phases be a proportionate scan rather than a ritual.

**Prevents.** Quality drift going unchecked through the skeleton, and the heavy refactor pass having to be the
primary enforcement instead of a net for what slipped.

**Enforced at.** `docs/playbook.md:133-135`; `docs/methodology.md:214-224`; `docs/systems.md:185-189,195-200`;
`skills/log-driven-development/SKILL.md:129-133`; `tools/closure-gate/closure_gate.py:5-8`;
`tools/closure-gate/closure-gate.toml:60-64`; `docs/artifacts.md:355-356`. The cited owner of the continuous-tier
membership is the two-tier(+) ownership matrix in `docs/systems.md` (system 7).

## LDD-INV-12: The walking skeleton is built first, one real path through every layer

**Rule.** Build the thinnest end-to-end slice that actually runs one real path through every layer (storage,
domain, API, surface) before deepening any one part; never layer-by-layer. The skeleton must run end to end from a
clean checkout with the gates green (including the security gate: an authenticated path that crosses its tenant or
trust boundary, not a no-auth happy path).

**Prevents.** Hiding integration risk until the end, and a skeleton with no security spine.

**Enforced at.** `skills/log-driven-development/SKILL.md:108-109`; `docs/methodology.md:104-118`;
`docs/systems.md:69-71` (the exit criterion this register binds to add the security spine); `README.md:69-72`;
anti-pattern #11 `docs/anti-patterns.md:243-261`; smell `docs/anti-patterns.md:386`.

## LDD-INV-13: Distil, do not transcribe

**Rule.** The spec is the smallest complete set of primitives that solves the domain, with the sprawl deliberately
dropped and each drop recorded with its reason. An empty drop-list is the tell that you transcribed instead of
distilling; if the spec is as big as the legacy, you transcribed.

The license to drop has TWO permissions that must not be conflated: dropping REDUNDANCY (verbatim or duplicate
material - legitimate distil) versus dropping UN-READ PROCEDURE (a step sequence, rule, algorithm, deadline,
eligibility gate, or document/pack content whose only home was source never opened - a coverage hole rationalized
as distil). The drop-list is therefore not write-only: distil is not done until a DROP-LIST ADVERSARY (the
decision-step analogue of builder + adversarial-verifier) re-opens the cited source and, for each drop, rules it
legitimate-redundancy vs negligently-missed-procedure; spot-checks a sample of RETAINED claims against their
`path:line` for source-fidelity (a self-consistent spec can be uniformly wrong); and forces security-COMPLETE,
not security-sampled, coverage on every external-reach / money / auth surface (sampling can skip the one file
holding a live secret).

**Prevents.** Re-importing the sprawl under a new name; a rebuild that is the legacy with a different file layout;
and the inverse failure: a coverage hole (dropped procedure), a wrong-but-internally-consistent claim, or a
skipped-file secret passing unchallenged because distil was the one major step with no adversary.

**Enforced at.** `skills/log-driven-development/SKILL.md:106-107`; `docs/methodology.md:79-99`;
`docs/systems.md:65-68`; `templates/intent-ledger.md:49-58` (the DROP-with-reason section); the distil-adversary
brief `docs/playbook.md:315-345`; anti-pattern #12 `docs/anti-patterns.md:264-281` and (the drop-list/fidelity
adversary) anti-pattern #19 `docs/anti-patterns.md:441-467`; smell `docs/anti-patterns.md:387,494`.

## LDD-INV-14: A milestone is not done until all five close phases run, in order

**Rule.** A milestone runs BUILD, STRUCTURE, SECURITY, VERIFY, PLAN, in order, each with reproduced evidence (the
actual command and the actual result). PLAN is mandatory: the next build does not start until the next milestone's
scope, sequence, risks, and the single next move are named.

**Prevents.** "Done" being a self-report and the run drifting into an unplanned next milestone.

**Enforced at.** `skills/log-driven-development/SKILL.md:149-162`; `docs/methodology.md:264-289`;
`docs/playbook.md:151-169,258-264`; `docs/systems.md:210-244`; the record artefact
`templates/milestone-signoff.md:1-61`; anti-pattern #10 (PLAN) `docs/anti-patterns.md:223-240`; smell
`docs/anti-patterns.md:385`. The five phases name their concrete tools and tiers by citing the two-tier(+)
ownership matrix in `docs/systems.md` (system 7).

## LDD-INV-15: Security and structural intent are first-class harvest registers

**Rule.** Provenance (LDD-INV-2) extends to security and structural intent: the harvest produces
`_harvest/security-invariants.md` (the security mechanisms, smells, and trust boundaries the legacy relied on) and
`_harvest/structural-debt.md` (the duplication, god-files, and over-long functions and their measured baseline) as
first-class outputs, not as optional prose buried in a domain ledger. Each intent ledger also carries a
risk-surface field. Security invariants graduate into red-until-built tests in the walking skeleton.

**Prevents.** The harvest silently dropping the two concerns the project most needs carried over, leaving security
and structural budgets as un-cited prose nobody can audit.

**Enforced at.** `skills/log-driven-development/SKILL.md:90-93` (the intent-ledger spine, to gain the two named
registers + the risk-surface field); `docs/artifacts.md:47-87` (the intent-ledger how-to); `templates/intent-ledger.md`
(to gain the risk-surface field); the security suite's own evidence discipline
`skills/security/WORKFLOW.md:48-58`; the refactoring suite's structural floor as the structural baseline
`skills/refactoring/structural-sweep.md:70-82`. (This invariant is the cure for the harvest-completeness gaps:
ldd-method GAP-5, ldd-refactoring GAP-4, ldd-security G-7.)

## LDD-INV-16: The spec is the source of truth; append-only history; supersede, never silently rewrite

**Rule.** The code is kept in sync with the spec, not the other way around: when building proves a spec line wrong,
fix the spec and journal why. History is append-only: a reversed decision is a new superseding journal entry or
ADR, never a silent edit of the old one; ADRs are append-only as a set (supersede, never edit-to-flip). A
load-bearing decision graduates to an ADR.

**Prevents.** The spec, the code, the invariants, and the backlog quietly disagreeing (the harmonize step catches
the drift), and history being rewritten so the audit trail lies.

**Enforced at.** `skills/log-driven-development/SKILL.md:96-97,173-174`; `docs/methodology.md:148-151,164-169`;
`docs/systems.md:296-299,306-312`; `docs/artifacts.md:108-112,149-150,168-169`; `docs/playbook.md:327-334`.

## LDD-INV-17: Escalation needs standing; the wrong tier is refused; spec law binds

**Rule.** The court is expensive currency spent rarely: a council fires only for a genuine hard fork or an honest
retrospective, never for a reversible/buildable/policy/security question. An appeal needs standing ("I would have
designed it differently" is not standing) and re-weighs the merits as a review; the Supreme Council hears only
points of law (was the invariant spec and the method correctly APPLIED?) and its ruling becomes spec law, an
immutable numbered precedent binding every future court. A decision colliding with spec law is refused at the spec
layer, the same fail-closed shape a trust boundary uses.

**Prevents.** The wrong question reaching the wrong court; a decided fork being re-litigated forever; a future court
silently re-fragmenting a consolidated concern (LDD-INV-9) with no precedent to deny against.

**Enforced at.** `skills/log-driven-development/SKILL.md:53-61`; `skills/council/SKILL.md:22-36,78-110`;
`commands/council.md:6-25`; `docs/methodology.md:298-339`; `docs/playbook.md:83-97`;
`docs/systems.md:119-152,376-401`; the spec-law register `skills/council/SKILL.md:104-110` and
`docs/artifacts.md:285-316`; anti-pattern #15 `docs/anti-patterns.md:326-347`; smell `docs/anti-patterns.md:390`.
(Open gap from the harvest, ldd-court G1: no `SPEC-LAW.md` register file exists yet, so a Supreme ruling about the
METHOD itself, including a ruling about this register, has no defined home. Flagged for the build step, not closed
here.)

## LDD-INV-18: Harvest at both altitudes (SYSTEM and PROCESS)

**Rule.** Every intent ledger must declare and fill BOTH altitudes for its area: SYSTEM (the shapes, enums,
state-machines, capabilities, the structure) AND PROCESS (the step-by-step procedure, the rule/algorithm, the
deadline arithmetic, the eligibility gates, the scoring rubric, the document/pack contents, the per-variant
difference - the things a human or operator actually does, one altitude below the structure). A ledger whose
PROCESS section is empty is incomplete BY CONSTRUCTION and MUST NOT be rolled up as "well-grounded", no matter how
complete its SYSTEM altitude is. This draws the line LDD-INV-13 left undrawn: INV-18 says the procedure layer must
be harvested at all; INV-13 says redundancy within it may then be dropped. The two together remove the
"structural sampling counts as done" escape hatch (a ledger that answers "the domain rule is ADGM => {SPV,TSL,OPCO}"
has captured the enum, not the procedure of incorporating an SPV).

**Prevents.** The systemic under-capture this register was amended to close: a harvest that fills every ledger
field with structure (enums, state-machine names, taxonomy) while the actual domain procedure, which lives one
altitude down in the source, is never opened, so the spec captures the SYSTEM and silently withholds the PROCESS
and the closure gate cannot see it (because nothing it checks is below the structure altitude).

**Enforced at.** `skills/log-driven-development/SKILL.md:102-107` (the intent-ledger spine, alongside
LDD-INV-15's two named registers); `templates/intent-ledger.md:36-53` (the required `## The process / procedure`
section); `docs/methodology.md:65-77,135-138`; `docs/systems.md:37-41,67-74`; the harvest brief
`docs/playbook.md:294-309`; anti-pattern #17 `docs/anti-patterns.md:377-403`; smell `docs/anti-patterns.md:492`;
and the source-coverage leg of LDD-INV-5 (an empty PROCESS altitude is exactly what the source->spec sweep
re-detects). Origin: the Clara-estate council verdict on harvest deficiency
(`_qa/_COUNCIL-harvest-deficiency.md`, BUILD-2), determined-by-ground-truth (an empty PROCESS section would have
blocked the knowledge-corpus ledger's green grade at write time).

---

## How the deliberation court enforces this register

This register is the spec of the method. The court's merits/law split (LDD-INV-17) is exactly what gives it teeth:
the Council and the Appeals Council argue the merits of a project's design and never rule on the method, but the
**Supreme Council** rules on a point of LAW: "was the invariant spec and the LDD discipline correctly APPLIED in
deciding this?" When the invariant in question is one of THESE method invariants (was LDD-INV-9 honoured, did the
court re-fragment a consolidated concern, was the one-writer rule kept, was ground-truthing real), the Supreme
Council is ruling on whether this register was applied.

A Supreme ruling about the method becomes **spec law about the method**: an immutable, numbered precedent recorded
in the spec-law register and cited by ID as controlling in every later decision. That is the fail-closed mechanism
that keeps a future court from silently re-splitting a concern this register consolidated: a decision that collides
with the precedent "one concern, one owner: function-length is owned by the closure-gate threshold; security is
owned by `vibescan --fast` at the continuous tier" is refused at the spec layer, exactly as a trust boundary
refuses an unmapped capability. Only a later Supreme Council, expressly narrowing the precedent on a point of
invariant law, may refine it: never a lower court, never the build phase, never an inline edit. When such a ruling
is made, it is recorded here (or in the spec-law register this register cites) so the method governs itself by the
same construction it imposes on the projects it rebuilds.

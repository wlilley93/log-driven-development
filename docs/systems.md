# The systems that make LDD work (and how they interlock)

This is the comprehensive systems reference. The [README](../README.md) is the pitch, the
[methodology](./methodology.md) is the long-form walkthrough of the arc, and [artifacts.md](./artifacts.md) is the
artefact-by-artefact construction manual. This document sits above all three: it names every distinct system that
makes LDD run as one operating model, and it shows how the parts feed and depend on each other. Read it when you
want to see LDD as a single machine rather than a list of practices.

Each system below gets four things, kept tight on purpose (this is a reference, not an essay): **what it is**, the
**failure it prevents**, **how it operates in practice**, and **what it feeds or depends on**. The final section,
[How it all interlocks](#how-it-all-interlocks), draws the loop so a reader sees one machine.

A note on the running example: throughout, "Tasky" is the same vibe-coded task-tracker used in the other docs (a
task with three contradictory ways to be "done", a buried auto-reopen-on-blocker rule, and a share link with no
expiry). The worked artefacts live under [`examples/`](../examples/).

---

## 1. The twin-ledger spine

**What it is.** Two append-mostly ledgers that run underneath the entire method, plus two pointers that keep them
navigable. The **intent ledgers** (`_harvest/*`) record what the old code *meant*, one domain area per file, every
claim provenance-gated to a file and line. The **metacognition journal** (`metacognition/*`) records *why* every
decision was taken, one beat per entry, append-only, supersede-never-rewrite. The **INDEX** is a one-line pointer
to every journal entry so the journal is scannable without opening each file. The **RESUME pointer** is the
always-current you-are-here: the single next move, and a paste-to-resume block a cold agent can lift to pick the
work up exactly where it was left.

**The failure it prevents.** Two failures at once. The intent ledgers prevent **lost intent**: the silent
dropping of a rule that existed only as code (Tasky's auto-reopen rule survives the rebuild only because the
ledger wrote it down). The journal prevents **no audit trail**: six weeks on, "why is the system shaped this way?"
has a written answer instead of a guess, and a settled question is not re-litigated because the superseded entry
shows it was already tried and rejected. The RESUME pointer prevents the **cold-start tax**: an agent resuming
mid-run does not have to reconstruct state by archaeology.

**How it operates in practice.** During harvest, one writer per intent file records what the legacy *does* (not
what it should do) with provenance, at both altitudes (LDD-INV-18): the SYSTEM (shapes, enums, state-machines,
capabilities) and the PROCESS one altitude down (the step-by-step procedure, the rules, the deadline arithmetic,
the eligibility gates, the scoring rubrics, the document/pack contents, the per-variant differences). An intent
file with a filled SYSTEM altitude but an empty PROCESS section has captured the enum, not the procedure, and is
incomplete by construction. A claim that cannot cite is a vibe and does not go in. Every beat, the
orchestrator appends one journal entry (the what, the how, and every decision with its reason and the alternatives
weighed), appends a one-line INDEX pointer, and rewrites the RESUME pointer to the new you-are-here plus the one
next move. A reversed decision is never edited away: a new entry supersedes the old and says so
(`supersedes 0007: building blocking revealed status needs a third value`). History is evidence.

**Feeds / depends on.** Depends on **ground-truth** and **provenance-or-it-does-not-go-in** (system 8) for its
integrity, and on the **one-writer rule** (system 8) so the ledgers stay coherent under parallel agents. Feeds
**everything**: it is the context and provenance every agent reads before acting (system 3), the grounding the
council ground-truths against (system 4), the source the spec is distilled from (system 9), and the record a cold
agent resumes from. A load-bearing journal decision graduates to an **ADR** (system 9).

---

## 2. The arc

**What it is.** The four-step spine of the method, each step with a concrete exit criterion you can point at, not
a feeling: **harvest, distil, walking skeleton, loop to zero gaps.**

**The failure it prevents.** A naive rebuild that designs from a tidy mental model and so drops real behaviour,
transcribes the sprawl instead of distilling it, hides integration risk until the end, and never has a
machine-checkable definition of "done".

**How it operates in practice.**

- **Harvest.** Read the legacy as the requirements document it secretly is; extract its meaning into intent
  ledgers with provenance, at BOTH altitudes (LDD-INV-18): the SYSTEM (shapes, enums, state-machines,
  capabilities) AND the PROCESS one altitude down (the step-by-step procedure, the rules, the deadline arithmetic,
  the eligibility gates, the scoring rubric, the document/pack contents, the per-variant differences - what a human
  actually does). The procedure usually lives one read deeper than the structure, which is exactly why a sampling
  harvest misses it; a ledger whose PROCESS section is empty is incomplete by construction and must not be rolled
  up as well-grounded. *Exit criterion:* every meaningful behaviour is captured at both altitudes with provenance,
  or explicitly noted as "looked at, nothing load-bearing here"; a reader who never saw the old code could
  reconstruct both the system and the procedure that drives it.
- **Distil.** Write the smallest complete spec: the minimal primitives that solve the domain, with the sprawl
  dropped on purpose and each drop recorded with its reason. The data structure *is* the product. Distil is the one
  major step that carries its own adversary (LDD-INV-13): before "harvest done", a **drop-list adversary** re-opens
  the cited source and, for each drop, rules it legitimate-REDUNDANCY (verbatim or duplicate material, a clean
  distil) vs negligently-missed-PROCEDURE (a step, rule, algorithm, deadline, or pack-content whose only home was
  source never opened, a coverage hole wearing distil's banner); spot-checks RETAINED claims against their
  `path:line` for source-fidelity (a self-consistent spec can be uniformly wrong); and forces security-COMPLETE,
  not sampled, coverage on every external-reach / money / auth surface (sampling can skip the one file with a live
  secret). *Exit criterion:* the spec covers every load-bearing behaviour, lists every dropped thing with a reason
  the adversary has ruled legitimate, and is small (if it is as big as the legacy, you transcribed, you did not
  distil).
- **Walking skeleton.** Build the thinnest end-to-end slice that actually runs: one real path through every layer
  (storage, domain, API, surface), before deepening any one part. *Exit criterion:* one real request runs end to
  end from a clean checkout with the gates green. The one real path is an authenticated path that crosses its
  trust/tenant boundary (it traverses one real auth check and one real tenant boundary), not a no-auth happy path,
  so the skeleton has a security spine from the first slice; "the gates green" explicitly includes the continuous
  `security_scan` gate. Thin, but whole. (LDD-INV-12, the skeleton built first through every layer; LDD-INV-11, the
  closure-gate stood up before the skeleton.)
- **Loop to zero gaps.** Each pass, build the next slice on the skeleton, run the closure sweep against the spec,
  close the gaps (amending the spec when building proves a line wrong), journal the beat. *Exit criterion (the
  headline rule):* "done" means the closure sweep finds zero gaps on BOTH legs, not "the tests pass" - the internal
  coherence leg (spec against itself) AND the source -> spec coverage leg (every harvest source re-walked for
  un-folded load-bearing detail), since the internal leg alone is blind to an omission (LDD-INV-5).

**Feeds / depends on.** Harvest depends on the **multi-author + coherence** shape (system 3) when the legacy is
large. The loop depends on the **closure-gate** (system 6) as its gap detector and on **loop-until-dry** (system 3)
to know it is finished. Each segment of the loop closes through the **milestone close** (system 7). The whole arc
writes the **twin-ledger spine** (system 1) as it runs.

---

## 3. The orchestrated agent shapes

**What it is.** The four standing fan-out shapes LDD runs work as. LDD is built for multi-agent orchestration, not
solo inline edits, so for any substantive task you reach for a shape, not a hand edit.

- **Builder + adversarial verifier.** One agent produces; at least one independent skeptic tries to *break* it,
  ground-truthing the real tree and re-running the load-bearing checks.
- **Multi-author + coherence/dedup.** N authors work in parallel, file-partitioned (one owner per file); one
  coherence agent merges, finds contradiction and duplication, and emits an integration checklist the orchestrator
  applies serially.
- **Loop-until-dry.** For unknown-size work (gap-closure, bug-finding), keep spawning rounds until K consecutive
  rounds find nothing new.
- **The council.** For high-stakes judgement calls, a fan-out of independent, named, distinct-lens critics
  (system 4).

**The failure it prevents.** A single pass rationalising away its own gaps (the verifier catches what the builder
talked itself out of seeing); collisions and lost writes when many agents author at once (file-partition plus
serial integration gives parallel throughput without races); stopping a search too early or wasting passes (the
consecutive-empty-rounds rule sizes itself to the real work); and one perspective rationalising a hard fork (the
council's independent lenses).

**How it operates in practice.** The builder + verifier pairing is the workhorse and the model for the council:
one produces, one independent adversary attacks, and the verifier's verdict is an *input* to the orchestrator, not
the final word (on Tasky, the verifier is the one that builds a blocking cycle and checks the auto-reopen cascade
terminates, a case the builder did not write). Harvest runs as multi-author + coherence (a dozen ledger areas
harvested at once). The spec-and-build loop runs as loop-until-dry. The hard forks run as the council.

**Feeds / depends on.** Depends on the **disciplines** (system 8): ground-truth (every shape cites evidence),
one-writer (agents return, the orchestrator integrates), file-partition (parallel authors own distinct files).
Reads the **twin-ledger spine** (system 1) for context and provenance. Feeds the **gates**: the builder produces
what the closure-gate (system 6) checks; the verifier is the VERIFY phase of the **milestone close** (system 7).
The council shape escalates into the **deliberation court** (system 4). At scale, these shapes are exactly what the
**ultracode posture** (system 10) fans out.

---

## 4. The deliberation court

**What it is.** A three-tier adversarial court modelled on UK law that decides the rare genuinely high-stakes,
hard-to-reverse fork: **the Council** (first instance), **the Appeals Council**, **the Supreme Council**. Each
tier is an ephemeral fan-out of fresh independent seats; each higher court is handed the full record of every
court below.

**The failure it prevents.** A single perspective rationalising an irreversible call, and a deliberation that
defers into another meeting. It also prevents the same hard question being re-fought from scratch forever: the
apex sets binding precedent.

**How it operates in practice.** The Council is a single parallel fan-out of a handful of named seats, each given a
distinct lens (project health, process critic, devil's advocate, plus a domain lens: security, cost, UX, the
advocate of a named alternative). Each seat ground-truths against the real tree first (a seat that cannot cite is
ignored); seats run independently and do not see each other mid-run, so they cannot converge into groupthink; each
leads with the blunt truth. The orchestrator synthesises, and the Council **ends in a build action or a kill, never
"we will look at it later"**. Nothing persists but the verdict and the **surviving dissent** (recorded, never
buried, because it is the standing of any future appeal).

The split that makes the hierarchy work is **merits versus law**. The Council and the Appeals Council argue
**points of spec (the merits)**: *what is the right design?* Escalation needs **standing** ("I would have designed
it differently" is not standing; the principal disagrees, a load-bearing dissent is unresolved, or new ground-truth
contradicts a relied-upon point, is). The Appeals Council re-weighs the merits as a review, engaging the Council's
actual reasoning, and may uphold or overturn. The **Supreme Council** does something different: it hears **only
points of law**: *was the invariant spec and the LDD discipline correctly applied?* Because it rules on law not
taste, its ruling becomes **spec law**: an immutable, numbered precedent that binds every future court. A decision
that collides with spec law is refused at the spec layer the same way a trust boundary refuses an unknown command;
only a later Supreme Council, narrowing the precedent on a point of law, can refine it.

**Feeds / depends on.** Is the escalation of the **council shape** (system 3). Spends from the **deliberation
budget** (system 5): it is convened only when build-first does not apply. Ground-truths against the **twin-ledger
spine** (system 1) and the spec (system 9). Feeds the spine back: a verdict graduates to an **ADR** (system 9) and
a Supreme ruling becomes spec law that constrains the spec itself. At scale, the council is the judgement valve
that keeps autonomous fan-out (system 10) from committing an irreversible mistake unexamined.

---

## 5. The deliberation budget

**What it is.** The standing rule that governs *how much deliberation a decision earns*. In the build phase the
default is **build-first**: a reversible, swappable choice gets one decisive sentence, not a panel. A panel or
council is reserved for irreversible, load-bearing forks, and **it ends in a commit or a kill**, never another
document that defers. No decision-of-record gets made by argument alone: a buildable artefact (a framework, a
store, a protocol) is chosen by a spike that exercises it, not by an ADR written from the armchair. And the
**meta-to-build ratio** is surfaced, so the project can see when it is deliberating more than it is building.

**The failure it prevents.** Analysis paralysis and decision-theatre: spending a council on whether Tasky's IDs are
UUIDs or ULIDs while a sentence would do, and the inverse, waving through a genuinely irreversible fork (collapsing
the three completion paths) with a sentence when it earns a real ADR. It also prevents the council from degrading
into a standing committee that produces meetings instead of commits.

**How it operates in practice.** Once you are building, the risk lives in the *unbuilt* surfaces, so the cheap
default is to build and journal one sentence. Escalation is deliberate and rare. Every panel, audit, or council is
required to terminate in a committed change or an explicit kill the same beat. Buildable choices are settled by a
thin slice, not by prose. Periodically (and at the retrospective council) the meta-to-build ratio is named
honestly: if the project has held more councils than it has shipped milestones, that is a finding.

**Feeds / depends on.** Governs when the **deliberation court** (system 4) is convened at all, and is itself one of
the **disciplines** (system 8, "build-first in the build phase"). Feeds the **milestone close** (system 7): the
build-first default is why STRUCTURE is a scan not a ritual and why SECURITY is risk-targeted. At scale (system 10)
it is the brake that keeps an autonomous engine biased toward shipping rather than toward perpetual deliberation.

---

## 6. The closure-gate

**What it is.** Continuous structural enforcement that runs mechanically on **every commit** and decides whether
the tree is clean and complete: a max-function-length limit that denies, a cross-module **duplication ratchet**
held by *folding* duplication and never by raising the number, formatter and linter as hard gates, and
red-until-built tests for any spec surface declared but not yet covered. Its definition of done is the headline
rule, and that rule has **two legs**: **"done" means the closure sweep is clean, not "the tests pass"** - and the
sweep is clean only when BOTH legs are on record (LDD-INV-5). Leg (a) is the **internal-coherence** sweep, spec
against itself: every id resolves, no two docs contradict, every claim is provenanced, traceability holds. Leg (b)
is the **source -> spec coverage** sweep, spec against source: a loop-until-dry re-walk of every harvest source
asking "what load-bearing detail lives here that never reached the spec?", evidenced by the source ranges plus the
ledger drop-lists, not by the spec. The two legs catch different failures, and the asymmetry is the point: leg (a)
audits the spec against itself and is **structurally blind to an omission** (a missing thing leaves no
contradiction to trip on), so leg (b) is the only one that can see un-folded detail. A done verdict carrying only
the internal leg is not done. (The coverage bar is "every load-bearing PROCEDURE reached the spec", not "every
source byte": the duplication-drop license of LDD-INV-13 still governs, so leg (b) does not drag the spec toward
transcription.)

**The failure it prevents.** Quality drift: agents (and humans) accreting duplication and sprawl until the rebuild
*is* the mess being escaped. The duplication ratchet is specifically what stops Tasky's rebuild from re-growing a
fourth way to complete a task: the second copy of the logic trips the gate and the commit is refused.

**How it operates in practice.** The `.md` config is the human-readable contract; the real gates live in the
linter config, the pre-commit hook, and the CI job. It is stood up **before the walking skeleton**, so "clean" is
checkable from the first line of the rebuild. The load-bearing rule is the ratchet: the duplication budget is a
number you only ever hold or *lower* by folding, never raise to make a commit pass (raising it concedes the sprawl
you are fighting). Because the gate runs continuously, the heavy periodic refactor pass becomes a *net for what
slipped*, not the primary enforcement.

**Feeds / depends on.** Depends on the **spec** (system 9) to know which surfaces are declared-but-unbuilt (the
red-until-built tests) and on **consolidation over fragmentation** (system 8) as the principle the ratchet
enforces (the ratchet-by-folding rule is registered as LDD-INV-10 in [docs/invariants.md](./invariants.md)). Is
the gap detector the **loop** (system 2) runs each pass. Feeds the **milestone close** (system 7): it
is the per-commit Tier 1 enforcement that makes the STRUCTURE phase a scan rather than the primary check. At scale
(system 10) it is one of the four things that keep autonomous throughput honest rather than runaway.

---

## 7. The milestone close

**What it is.** The five-phase gate every milestone must run before it is "done", in order:
**BUILD, STRUCTURE, SECURITY, VERIFY, PLAN.** PLAN is mandatory: the next build does not start unplanned. Sitting
across the close is a **two-tier quality gate**: Tier 1 is embedded per-commit (the closure-gate, always on); Tier
2 is risk-targeted (run where risk actually lives, plus periodically).

**The failure it prevents.** "Done" being a self-report, and drifting into an unplanned next milestone. It also
prevents both bureaucratic over-checking (deep-auditing a trivial surface as a ritual) and dangerous
under-checking (skipping the deep audit on a high-risk one).

**How it operates in practice.**

- **BUILD.** Implement the milestone's scope; formatter, linter, tests green from a clean checkout.
- **STRUCTURE.** A mandatory structural *scan* of the new surface (does the ratchet hold? any over-long function,
  God-object, leaked abstraction?). Escalate to a full refactor only on flagged debt, because the continuous
  closure-gate already did the heavy lifting. A scan, not a ritual.
- **SECURITY.** Cheap supply-chain checks every milestone; the **deep audit is risk-targeted**: mandatory on a
  high-risk surface (auth, money, crypto, multi-tenancy, anything externally reachable), periodic otherwise.
  Tasky's sharing milestone (the share link, its new expiry, the access check) earns it.
- **VERIFY.** An **independent adversarial verifier** re-runs from clean, attacks the milestone's invariants, and
  tries to break the new surface. This is the primary correctness-and-security net, every milestone.
- **PLAN.** **Mandatory.** The milestone does not close until the next steps are planned: the next milestone's
  scope, sequence, and risks, plus the single next move. A high-stakes next fork escalates to a planning agent or
  a council. No drifting into an unplanned next milestone.

The two-tier gate is the through-line: **Tier 1** (the closure-gate, system 6) runs on every commit so quality is
enforced continuously; **Tier 2** (the deep security audit, the full refactor pass, the adversarial verifier) is
spent where risk lives and on a periodic cadence, not uniformly; see the two-tier(+) ownership matrix below for the
single owner of each.

### The two-tier(+) ownership matrix (one owner per concern, LDD-INV-9)

This table is the single source of truth for which tool owns which concern and at which cadence. Every other doc
and every gate config CITES this matrix; none restates it. "Tier" here is the GATE-CADENCE axis (continuous
per-commit vs risk-triggered heavy pass), distinct from the court's judgement Tiers (Council / Appeals / Supreme,
owned by the council skill). The continuous tier holds only the cheap edge of each suite; every heavy pass stays
risk-triggered under one owner (the anti-bloat veto).

| Concern | Single owner | Tier / trigger |
|---|---|---|
| Structural floor (function length, duplication, formatter, linter, type-check, tests) | The closure-gate (`tools/closure-gate/closure_gate.py`, 8 gates) + `vibeclean --changed` as its `structure_scan` edge | Continuous, every commit (the per-commit gate). Function-length number is owned by `[function] max_lines` in `closure-gate.toml`; all other surfaces cite it. |
| Fast security: secrets + dependency CVEs + fast SAST | `vibescan --fast` (the closure-gate `security_scan` gate) | Continuous, every commit. The ONE security owner at this tier; subsumes the old separate supply-chain / dep-CVE gate. |
| Full SAST sweep (whole tree) | `vibescan .` (full, not `--fast`) | Push / CI, and at milestone-close SECURITY. |
| Deep security reasoning (exploitability, cross-subsystem chains, threat model, the 14-section audit) | The security suite methodology (`skills/security/methodology.md`); `vibeaudit` is its scanner engine, NOT a parallel auditor | Tier 2, risk-triggered: mandatory on auth / money / crypto / multi-tenant-isolation / any externally-reachable surface, plus periodic. Never routine. |
| Behaviour-preserving cleanup (refactor rounds, structural sweep) | The refactoring suite (`skills/refactoring/`) | Tier 2, risk-triggered: escalate from the STRUCTURE scan ONLY on a tripped debt counter (see structural-sweep). Never routine. |
| Test quality (missing tests, weak assertions, smells, coverage gaps) | `vibetest` | Milestone-close VERIFY, alongside the independent adversarial verifier. |
| Performance / deploy readiness | `viberapid` (perf) / `vibedeploy` (ship-safe gate) | Referenced, never mandatory: run as needed on a perf-budget or pre-deploy trigger. |

The method invariants this matrix anchors are registered in [docs/invariants.md](./invariants.md) (LDD-INV-9 one
owner per concern, LDD-INV-10 the duplication ratchet); cite them by ID rather than restating the rule.

**Feeds / depends on.** Depends on the **closure-gate** (system 6) as its Tier 1, on the **builder + verifier**
shape (system 3) for VERIFY, and on the **deliberation budget** (system 5) for why STRUCTURE and SECURITY are
proportionate not ritual. Its PLAN phase feeds the next turn of the **arc** (system 2) and writes the **journal**
(system 1). A high-stakes PLAN fork escalates to the **deliberation court** (system 4). The sign-off artefact is
where all five phases and their evidence are recorded.

---

## 8. The disciplines

**What it is.** The standing rules that keep every other system honest. Each one prevents a specific named failure;
drop a discipline and expect its failure.

- **Ground-truth everything.** Every claim, finding, and "it is done" cites real evidence (a grep, a read, a
  count, a test run). An agent or person that cannot cite is ignored. *Prevents:* confident fiction (the agent
  that asserts "Tasky has one completion path" until forced to grep and find three).
- **The one-writer rule.** Only the orchestrator writes shared state (the ledgers, the index, the spec, the task
  list, the sign-offs). Spawned agents *return* their what/why as text; the orchestrator integrates serially.
  *Prevents:* collision and lost writes when many agents append at once.
- **The file-partition rule.** Parallel authors own distinct *new* files; for hot shared files, agents return
  their content blocks, a coherence agent emits an integration checklist, and the orchestrator applies it
  serially. *Prevents:* two agents racing on one file and corrupting it.
- **Done is the orchestrator's judgement, never a worker self-report.** "Completed" is the orchestrator's call
  after ground-truthing (build and test from clean, the verifier, the closure sweep), never a worker's claim.
  *Prevents:* a milestone marked done because a worker said so.
- **Provenance or it does not go in.** Anything describing the legacy cites the exact file and line. *Prevents:* a
  vibe entering the record and calcifying into a false requirement.
- **Fix security the moment found.** A security issue is fixed when found, not filed for later. *Prevents:* a
  known hole (Tasky's no-expiry share link) surviving the rebuild because it was deferred.
- **Commit per beat with explicit paths.** Every beat ends in a commit with explicit paths (never a blanket
  `add -A`) and a co-author trailer. *Prevents:* unattributable, unbisectable history and accidental staging.
- **Consolidation over fragmentation.** When a new need resembles an existing one, fold it in; never spin up a
  parallel system, store, or service. One source of truth per fact; every other surface is a regenerable view.
  *Prevents:* the original sin that made Tasky a mess (three completion mechanisms).

**The failure it prevents.** Collectively: an audit trail that is incoherent, untrustworthy, or fictional, and a
rebuild that re-grows the sprawl. The disciplines are why the artefacts can be *trusted* as a record.

**How it operates in practice.** They are standing rules, not phases: every shape, every gate, every ledger write
is bound by them at all times. The one-writer and file-partition rules are what make parallel orchestration safe;
ground-truth and provenance are what make the ledgers worth reading; fix-security-now and commit-per-beat are the
per-beat hygiene.

**Feeds / depends on.** Underpins *every* system. The **twin-ledger spine** (system 1) is trustworthy only because
of ground-truth, provenance, and one-writer. The **agent shapes** (system 3) are safe only because of
file-partition and one-writer. The **court** (system 4) is credible only because seats ground-truth. The
**closure-gate** (system 6) enforces consolidation. At scale (system 10), the disciplines are the load-bearing
constraints that let the engine run autonomously without going feral.

---

## 9. Decisions of record and the spec as source of truth

**What it is.** The system that keeps the *design* coherent and citable. **ADRs** are journal decisions that
earned a promotion: a short standalone record of one load-bearing, hard-to-reverse call (context, options,
decision, consequences), pulled out where the big calls are easy to find and cite by ID. The **spec** is the
distilled minimal source of truth (primitives, invariants, deliberately-dropped-with-reason): the code is kept in
sync with the spec, not the other way around. The **harmonize step** keeps the spec, the code, the invariants, and
the backlog mutually consistent. The **closure sweep** is the mechanical gap detector, and it runs as **two
legs**: an internal-coherence leg (spec against itself: ids resolve, no contradiction, provenance, traceability)
and a source -> spec coverage leg (every harvest source re-walked for load-bearing detail that never reached the
spec). The first proves the spec is self-consistent; the second proves the build and the spec together cover the
source.

**The failure it prevents.** The big decisions getting lost in a dense chronological journal (ADRs are the citable
index of the load-bearing ones); the design fragmenting so the spec, the code, and the backlog quietly disagree
(harmonize catches the drift); and a half-built spec being mistaken for "done" because the tests are green (the
closure sweep checks coverage against the spec, not against the tests). And the subtler failure the two-legged
sweep exists to close: an internally-consistent spec graded "complete" while a whole layer of the source sits
un-folded and unseen, because the internal leg cannot see an omission and only the source-coverage leg looks back
at the source.

**How it operates in practice.** A journal decision that is load-bearing graduates to an ADR (collapsing Tasky's
three completion paths is the canonical one); a council verdict that needs a durable home becomes an ADR too. ADRs
are append-only as a set: you supersede an ADR with a new ADR, you never edit the old one to flip it. The spec is
first drafted at distil and then amended continuously through the loop: when building proves a spec line wrong, you
fix the spec (it is the source of truth) and the journal records why. The harmonize step is run when surfaces have
moved, reconciling spec, code, invariants, and backlog into one consistent picture. The closure sweep runs each
loop pass and at milestone close, running both legs: it compares build to spec and reports the internal gaps, then
re-walks every harvest source (loop-until-dry, against the source ranges and the ledger drop-lists) and reports
any load-bearing detail that never reached the spec. A FREEZE or done verdict with no source-coverage leg on
record is not done.

**Feeds / depends on.** ADRs are graduated from the **journal** (system 1) and from **council** verdicts (system
4), and a Supreme ruling can constrain the spec as spec law. The spec is distilled from the **intent ledgers**
(system 1) during the **arc** (system 2) and is what the **closure-gate** (system 6) checks declared-but-unbuilt
surfaces against. The closure sweep is the gap detector the **loop** (system 2) and the **milestone close** (system
7, VERIFY and BUILD) depend on. Harmonize keeps the spine and the build from diverging.

---

## 10. Running at scale: the ultracode posture

**What it is.** A standing goal plus always-on workflow orchestration turns LDD into heavy, long-running,
fan-out workflows. With always-on orchestration, the model authors and runs a *workflow* by default for every
substantive task rather than editing inline; with a **standing goal** ("rebuild this system to a clean, verified
state") it keeps working toward that objective across many turns, planning the next milestone and starting the next
workflow on its own. Call this the **ultracode posture**: one goal driving many workflows, each spawning many
parallel agents, mostly autonomously.

**The failure it prevents.** Hand-cranking a multi-agent process one fan-out at a time, which throttles
throughput. The posture lets a single goal drive dozens of workflows in sequence (harvesters, builders, verifiers,
whole councils) with little human input.

**How it operates in practice.** The methodology supplies the *shapes* (the harvest fan-out, builder plus verifier,
the council, loop-until-dry) and the mode makes orchestration the default *how*, so the two compose: LDD says what
to orchestrate, ultracode makes orchestration the default. Stated plainly, this is a deliberate trade. **The
power:** it can build and adversarially verify a large system largely on its own. **The honest cost:** it consumes
a lot of tokens and compute, by design; the trade is thoroughness over speed. What keeps that throughput honest
rather than runaway is the rest of LDD working as a governor: the **closure-gate** refusing drift on every commit,
the **adversarial verifier** attacking every milestone, the **council** gating the hard forks, and the
**metacognition journal** recording why each of those many agents did what it did. Turn the engine on once the
disciplines are in place, not before.

**Feeds / depends on.** Fans out the **agent shapes** (system 3) and the **arc** (system 2) at volume. Depends, for
its safety, on the four governors named above: the **closure-gate** (system 6), the **milestone-close verifier**
(system 7), the **deliberation court** (system 4), and the **twin-ledger spine** (system 1). Depends on the
**disciplines** (system 8) being in place first. This is the system that makes the others worth having at scale,
and the one that would be reckless without them.

---

## How it all interlocks

The ten systems are not a checklist. They are one machine with a single loop, and each system feeds the next.

```
                        ┌──────────────────────────────────────────────┐
                        │   THE STANDING GOAL  (ultracode posture, 10)  │
                        │   drives many workflows, mostly autonomously  │
                        └───────────────────────┬──────────────────────┘
                                                │ fans out
                                                v
   ┌───────────────────┐   context+provenance   ┌────────────────────────┐
   │  TWIN-LEDGER SPINE │ ─────────────────────> │  AGENT SHAPES (3)       │
   │  (1)               │                        │  builder | multi-author │
   │  intent + journal  │ <───── what/why ────── │  loop-until-dry | council│
   │  + INDEX + RESUME  │   (one writer: orch.)  └───────────┬────────────┘
   └─────────┬─────────┘                                     │ build then verify
             │ distilled into                                v
             v                                   ┌────────────────────────┐
   ┌───────────────────┐    checks build vs      │  THE GATES              │
   │  SPEC + ADRs (9)   │ <──────────────────────│  closure-gate (6)       │
   │  source of truth   │    spec (closure sweep)│  + 5-phase close (7)    │
   └─────────┬─────────┘                         └───────────┬────────────┘
             │ spec law constrains                           │ close ends in
             v                                                v
   ┌───────────────────┐    hard forks only      ┌────────────────────────┐
   │  DELIBERATION      │ <───────────────────────│  PLAN (mandatory, 7)   │
   │  COURT (4)         │   (budget gates it, 5)  │  → next turn of the arc │
   │  → sets spec law   │ ───────────────────────>└────────────────────────┘
   └───────────────────┘   verdict → ADR → spine            ^
             │                                               │
             └───────────── all of it journalled ───────────┘
              (a cold agent resumes from RESUME + INDEX, system 1)
```

Read as one machine, the loop runs like this:

1. **The arc (2)** is the path; the **disciplines (8)** are the standing constraints on every step of it.
2. **The ledgers (1) feed the agents (3).** Every agent reads the spine for context and the provenance it must
   honour before it acts. Nothing enters the record without ground-truth.
3. **The agents (3) feed the gates: build, then verify.** The builder produces; the closure-gate **(6)** checks
   every commit; the adversarial verifier attacks the milestone. The agents return their what/why; the orchestrator
   (the one writer) integrates serially.
4. **The gates feed the milestone close (7), which ends in PLAN.** Tier 1 (the closure-gate) ran continuously, so
   STRUCTURE is a scan and SECURITY is risk-targeted; VERIFY is the independent net; and the close cannot finish
   until PLAN names the next move. PLAN feeds the next turn of the arc.
5. **The hard forks feed the council (4), gated by the deliberation budget (5).** Most decisions are one sentence
   and a commit. Only an irreversible fork is convened, it ends in a build action or a kill, and a Supreme ruling
   sets **spec law** that constrains the spec **(9)** itself.
6. **The journal (1) records all of it.** Every beat, decision, verdict, and milestone is written down as it
   happens, with the INDEX to scan it and the RESUME pointer to lift it. A cold agent can pick the work up exactly
   where it was left, because the reasoning was recorded, not reverse-engineered.
7. **At scale (10),** the standing goal drives this loop as many parallel workflows, mostly on its own. The power
   is autonomous build-and-verify of a large system; the cost is real tokens and compute, by design. The
   closure-gate, the verifier, the council, and the journal are precisely what keep that throughput honest rather
   than runaway.

That is the whole of it. The ledgers ground the agents, the agents drive the gates, the gates close the milestone,
the milestone plans the next turn, the hard forks go to court and can make law, and the journal makes every link
recoverable. One goal, one loop, one auditable machine.

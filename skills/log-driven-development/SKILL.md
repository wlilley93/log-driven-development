---
name: log-driven-development
description: A multi-agent methodology for the brownfield reality of AI coding - you (or an agent) vibe-coded a first attempt that works-ish but has no spec or plan, and the code is now the only record of the requirements. LDD harvests those requirements out of the code → distils a minimal spec + plan → builds a walking skeleton → loops spec⇄build until an automated sweep finds zero gaps; auditable by a twin-ledger spine; run by orchestrated agents (builder + adversarial-verifier; the council). Use when cleaning up or rebuilding a vibe-coded/legacy codebase, or any time you want decisions auditable by construction.
---

# Log-Driven Development (LDD)

> Harvest the precious logic out of overcooked legacy → distil it into a minimal **substrate spec** → build a
> **walking skeleton** → **loop spec⇄build until an automated sweep finds zero gaps**: run by **orchestrated
> agents**, with **two ledgers** as the spine that make the whole thing auditable by construction.

LDD is for the **brownfield** situation - most sharply, the one AI coding creates: you (or an agent) **vibe-coded
a first attempt**. It works-ish, but **no spec or plan was ever written**: the code is the *only* record of what
you wanted. Now it's sprawling and you're afraid to touch it. LDD treats that code as the requirements: it
**harvests** them out of the code into an explicit plan + spec, then rebuilds the *substrate* - the minimal,
complete core - without re-importing the sprawl, and without losing the behaviour you'd already earned. (It works
equally on an older rotted legacy system - same move: the intent lives in the code; harvest it first.) It is run
with **multi-agent orchestration**, not solo edits.

> **ADR = Architecture Decision Record:** one significant, hard-to-reverse decision captured as the context
> that forced it, the decision taken, and the consequences (the tradeoffs kept and the tradeoffs given up). A
> plain journal decision *graduates* into an ADR when it is load-bearing enough that people will later need to
> find and cite it. The term is expanded here on first use and used in short form below.

## Operating procedure (do this)
This section is prescriptive: an agent following it should never be unsure what to do next. The fuller manual is
[docs/playbook.md](../../docs/playbook.md) (the step-by-step operating manual, with annotated example briefs and a
quick-reference card), backed by [docs/methodology.md](../../docs/methodology.md) (the long-form walkthrough),
[docs/artifacts.md](../../docs/artifacts.md) (artefact-by-artefact construction), and
[docs/anti-patterns.md](../../docs/anti-patterns.md) (the failure modes and the rule that prevents each).

### The beat loop (every beat, in this order)
1. **Orient.** Read the RESUME pointer (you-are-here + the one next move + the paste-to-resume block), the last
   few journal entries, and the task list. That is the entire working state; load it before anything else.
2. **Ground-truth before deciding.** Grep, read the real files, run the tests. Never trust a summary, a memory,
   or a prior claim over the actual tree. If you cannot cite `file:line` or command output, you do not know it
   yet.
3. **Pick the one next move.** The smallest coherent unit that advances the goal. One thing, not three.
4. **Orchestrate, do not edit inline** for anything substantive. Spawn the right agent shape (see Shape
   selection). Write the brief with EXACT anchors (`file:line`), the load-bearing invariant to prove, and for a
   verifier the EXACT attack to run. Vague briefs produce vague work.
5. **Ground-truth the result yourself, from clean.** Build, test, lint, and re-prove the load-bearing invariant.
   A subagent saying "done" is an INPUT, never the verdict.
6. **Fix anything wrong before committing.** If it is a SECURITY issue, fix it the moment it is found: never ask
   first, never commit it.
7. **Commit per beat with EXPLICIT paths** (never a blanket `add -A`, it sweeps build artifacts). One coherent
   unit per commit, with a co-author trailer.
8. **Record.** Write the metacognition journal entry (what + why, with the alternatives for a decision), add the
   one-line INDEX pointer, update RESUME (you-are-here + the next move), update the task list. ONLY the
   orchestrator writes shared state (the one-writer rule).
9. **Report at milestone boundaries,** not mid-batch.

### Decision rules (apply mechanically)
| Situation | What you do |
|---|---|
| Reversible or swappable choice | ONE decisive sentence, then build it. Convene nothing. (Build-phase risk lives in the unbuilt surface, so bias hard to building.) |
| Irreversible or load-bearing choice | A spike or thin slice that exercises it BEFORE you commit. Never record a decision selecting a buildable thing (framework, store, protocol) without having exercised it. |
| A genuine hard fork, or an honest "is this actually working?" | Convene a COUNCIL. It must end in a build action or a kill, never another doc that defers. |
| A challenged council verdict | The Appeals Council (needs standing). A question of how the invariants or method were APPLIED goes to the Supreme Council, whose ruling is spec law. |
| A principal-owner policy or domain call (not a technical one) | ASK the principal. Do not guess on their behalf. |
| A security issue | Fix immediately. This overrides every schedule. |

### Self-referral to the council (convene WITHOUT being asked)
Do not wait to be told to convene. "A genuine hard fork" is made mechanical by these triggers: if ANY fires, you
self-convene a council that same beat (it still ends in build-or-kill, never a stall), exactly as the closure-gate
makes "done" mechanical. The triggers are deliberately NARROW so the deliberation budget is not blown on building
that should just happen (a reversible choice still gets one sentence).
- **Invariant / spec-law collision.** A decision would relax, contradict, or carve an exception to an LDD-INV or a
  `council/SPEC-LAW.md` precedent. (This is the merits/law boundary itself; it may not be a solo call.)
- **Unprovable genuine function.** A load-bearing claim's Determination of Genuine Function cannot be
  affirmatively made (no spike, test, or demonstrated end-to-end path). Convene; resolve to spike-first or kill,
  never ratify a hypothesis (SPEC-LAW-2).
- **Decision thrash.** The same decision has been reversed across two or more beats. Repeated flip-flop is the
  signal one perspective keeps rationalising; the panel breaks it.
- **Builder/verifier deadlock.** After a build round plus a clean re-run, the adversarial verifier and the builder
  still disagree on whether a load-bearing invariant holds. Escalate the correctness question, do not pick a side.
- **Irreversible boundary relaxation.** A change crosses a trust / tenant / money boundary, is hard to reverse,
  AND has real cost on both sides. (The textbook hard fork; make it checkable so it is never missed.)
- **Whole-program fork.** A choice that reshapes a sequence, a milestone plan, or the spec's own scope (not a
  local edit).
The principal can always override a self-convened verdict (a principal override of record, append-only; SPEC-LAW-1):
your autonomy is to CONVENE, never to overrule the principal.

### Orchestration shape selection
- **Build one thing and be sure it is correct** -> BUILDER + ADVERSARIAL VERIFIER: one produces, an independent
  skeptic tries to BREAK it (grounding in the real tree, re-running the load-bearing checks). In practice the
  verifier catches real defects the builder introduced, including security holes.
- **Author a volume of independent files** -> MULTI-AUTHOR + COHERENCE: N authors, each owning DISTINCT files,
  then one coherence pass merges and dedups. Never let two agents write the same file.
- **Unknown-size discovery** (find all the gaps, all the bugs) -> LOOP-UNTIL-DRY: keep going until K
  consecutive rounds find nothing new. A fixed count misses the tail.
- **A judgement call under stakes** -> the COUNCIL (see the `council` skill).

### Precision with subagents
- Tell every spawned agent: do NOT journal, do NOT touch shared state, do NOT commit; RETURN your what and why,
  and the orchestrator records it.
- Give exact anchors (`file:line`), the precise invariant or property to prove, and for a verifier the exact
  adversarial attack to run plus the exact verdict shape to return.
- Prefer free-text returns and self-written files; rigid output schemas fail under rate-limiting. Wave-throttle
  concurrency.

## Rules you do not break
These are the method invariants. The full register, with the failure each prevents and where it is enforced, is
[docs/invariants.md](../../docs/invariants.md) (LDD-INV-1..18); that register is the authoritative set, the
bullets below are the quick-reference.
- **Ground-truth, no vibes.** Cite `file:line` or command output, or you do not know it.
- **One-writer rule.** Only the orchestrator writes the ledgers, the index, and the task list.
- **File-partition.** Parallel authors own distinct files; never two agents on one file.
- **"Done" is the orchestrator judgement.** It means ground-truthed from clean + the closure sweep is clean, never "the tests pass" alone and never a worker's self-report.
- **Commit explicit paths.** Never a blanket `add -A`.
- **Fix security immediately.** The moment it is found, before any commit, ahead of every schedule.
- **A council ends in build-or-kill.** Never another doc that defers.

## The spine - two ledgers (auditability by construction)
1. **Intent ledgers** (`_harvest/*`) - *what the old code meant.* Before building, harvest the precious logic
   out of the legacy: the domain rules, the edge cases, the security mechanisms, the data shapes - each captured
   as a free-text ledger with provenance (where in the old code it came from). Provenance or it doesn't go in.
   The harvest produces two first-class named registers alongside the domain ledgers: `_harvest/security-invariants.md`
   (the security mechanisms, smells, and trust boundaries the legacy relied on) and `_harvest/structural-debt.md`
   (the duplication, god-files, and over-long functions with their measured baseline), so neither concern survives
   only as un-cited prose. Each intent ledger also carries a **risk-surface** field (does this area touch auth /
   money / crypto / multi-tenant-isolation / external-reach). See LDD-INV-15.
   Every ledger must be harvested at BOTH altitudes (LDD-INV-18): SYSTEM (the shapes, enums, state-machines,
   capabilities) AND PROCESS (the step-by-step procedure one altitude down: the rules, deadline arithmetic,
   eligibility gates, scoring rubrics, document/pack contents, per-variant differences - what a human actually
   does). A ledger that fills only the SYSTEM altitude has captured the enum, not the procedure; its empty
   PROCESS section makes it incomplete by construction and it must not be rolled up as well-grounded. The
   structure is one altitude; the procedure that drives it is the one the harvest most often misses.
2. **The metacognition journal** (`metacognition/*`) - *why every decision was taken.* One entry per beat:
   what was done, the tools/agents used, and **every decision with its reason** (what was chosen, the
   alternatives, and why). Newest appended; an `INDEX.md` one-liner points to each. If a decision is later
   reversed, a new entry supersedes it - never silently rewrite history.

These two ledgers mean: at any point you can answer "why is the system shaped this way?" and "what did the old
system mean here?" without archaeology. That is the payoff - the method *is* the audit trail.

## The arc
**harvest → distil → walking skeleton → loop(spec ⇄ build) until zero-gap.**

- **Harvest** the legacy into intent ledgers (wave-throttled agents; free-text returns + self-written files).
- **Distil** a minimal **substrate spec**: the smallest complete set of primitives that solves the domain,
  with the sprawl deliberately *dropped* (and dropped-with-reason recorded). The data structure *is* the product.
  Distil is the only major step that must carry its own adversary (LDD-INV-13): before "harvest done", a
  drop-list adversary re-opens the cited source and rules each drop legitimate-redundancy vs negligently-missed
  procedure, spot-checks retained claims against their `path:line` for source-fidelity (a self-consistent spec
  can be uniformly wrong), and forces security-COMPLETE (not sampled) coverage on every external-reach / money /
  auth surface. Dropping redundancy is distil; dropping un-read procedure is a coverage hole wearing distil's
  banner.
- **Walking skeleton**: the thinnest end-to-end slice that actually runs (one real path through every layer),
  not a layer-by-layer build. Prove the spine before deepening any limb. The harvested security invariants
  (`_harvest/security-invariants.md`) graduate here into **red-until-built closure-gate tests**: each control is a
  failing test until its control is built, so the spine carries a security floor from the start (LDD-INV-12,
  LDD-INV-15).
- **Loop** spec⇄build, closing gaps each pass, until the **closure sweep** is clean. "Done" requires BOTH legs of
  the sweep on record (LDD-INV-5): spec -> internal coherence (id-graph resolves, no contradiction, traceability
  holds) AND source -> spec coverage (a loop-until-dry re-walk of every harvest source asking "what load-bearing
  detail lives here that never reached the spec?", evidenced by the source ranges + the ledger drop-lists, NOT the
  spec). The internal leg is blind to an omission (an omission leaves no contradiction); only the source leg sees
  it. "Done" is *both sweeps are clean*, not "the tests pass" and not internal coherence alone. (The coverage bar
  is "every load-bearing PROCEDURE reached the spec", not "every source byte": LDD-INV-13 still governs.)

## The standing disciplines (these are what make it work)
1. **Ground-truth everything - no vibes.** Every claim, every finding, every "it's done" cites real evidence
   from the tree (a grep, a file read, a count, a test run). An agent that can't cite is ignored.
2. **One-writer rule (shared state belongs to the orchestrator).** Only the **main loop** writes the ledgers,
   the index, and the task list. Spawned agents **return** their what/why; they do not journal or mutate shared
   state (they collide). "Completed" is the *orchestrator's* judgement after ground-truthing - never a worker's
   self-report.
3. **File-partition (author in parallel, integrate serially).** Parallel agents may write **new** files when
   each file has a single owner. For **hot shared files**, agents **return** their content blocks and a
   coherence agent emits an integration checklist; the main loop applies it serially, then verifies. Never let
   two agents race on one file.
4. **Build-first in the build phase (the deliberation budget).** Once building, the risk lives in the *unbuilt*
   surfaces. So default to BUILD, not DELIBERATE: a reversible/swappable decision gets *one decisive sentence*,
   not a panel; reserve the full steelman for irreversible/load-bearing choices. **A panel/audit/council ends in
   a committed change or an explicit kill - never another doc that defers.** Don't select a buildable artifact
   (framework/store/protocol) by ADR without a spike or thin slice that exercises it.
5. **The closure-gate (continuous structural enforcement).** Make "is it clean / is it complete?" a *checkable
   mechanism that executes on every commit*, not a periodic ritual: a max-function-length lint (deny), a
   cross-module **duplication ratchet** (a budget you hold by *folding* duplication, never by raising the
   budget), formatter + linter as hard gates, and red-until-built tests for declared-but-unbuilt surfaces. When
   this runs continuously, the heavy periodic refactor pass becomes a *net for what slipped*, not the enforcement.
6. **Consolidation over fragmentation.** When a new need resembles an existing one, fold it in; never spin up a
   parallel system/store/service. One source of truth per fact; every other surface is a regenerable view.

## The orchestrated agent shapes (the engine)
Reach for an orchestration shape over inline edits for any substantive task. Defaults:
- **Builder + adversarial-verifier**: one agent produces; ≥1 independent skeptic tries to *break* it
  (ground-truthing the real tree, re-running the load-bearing checks). The verdict is the orchestrator's input,
  not the truth. This catches what a single pass rationalises away. *(See the `council` skill for the
  decision-making analogue.)*
- **Multi-author + coherence/dedup**: N authors in parallel (file-partitioned), one agent merges + checks
  coherence and emits the integration checklist.
- **Loop-until-done / loop-until-dry**: for unknown-size work (gap-closure, bug-finding), keep spawning until
  K consecutive rounds find nothing new. Simple counters miss the tail.
- **The council** (and its appeals hierarchy) - for high-stakes *judgement* calls. See the `council` skill.

## The milestone close - 5 phases (a milestone is not "done" until all run)
**BUILD → STRUCTURE → SECURITY → VERIFY → PLAN.**
1. **BUILD**: implement the milestone's scope; formatter/linter/tests green.
2. **STRUCTURE**: a mandatory structural *scan* of the new surface (does the duplication ratchet hold? any
   over-long function / God-object / leaked abstraction?), run by the continuous closure-gate (the duplication
   ratchet) + `vibeclean`. **Escalate** to the full refactoring suite (`skills/refactoring/`) only on a tripped
   debt counter - the *continuous* closure-gate is the primary structural enforcement, so this is a scan, not a ritual.
3. **SECURITY**: `vibescan --fast` runs every commit as the continuous one-security-owner (it subsumes the
   supply-chain check). The **heavy** pass is **risk-triggered**: the full `vibescan .` sweep plus the security-suite
   methodology (`skills/security/`, with `vibeaudit` as its scanner engine, not a parallel auditor), mandatory on a
   high-risk surface (auth, money, crypto, multi-tenancy/isolation, any externally-reachable entry point) +
   periodically - never bureaucratically run on a trivial surface the verifier already attacked.
4. **VERIFY**: `vibetest` (test quality, weak assertions, coverage gaps) plus an **independent adversarial verifier**
   (the primary security + correctness net, every milestone): re-run from clean, attack the milestone's invariants,
   try to break the new surface.
5. **PLAN**: **mandatory.** The milestone does NOT close, and the next build does NOT start, until the next
   steps are planned: the next milestone's scope/sequence/risks + the single next move. A high-stakes/uncertain
   next fork → a planning agent or a council. Never a vague "we'll see."

Which tool owns which concern, and at which cadence (the continuous per-commit tier vs the risk-triggered heavy
pass), is not restated here: see the two-tier(+) ownership matrix in [docs/systems.md](../../docs/systems.md)
(system 7).

## Per-beat cadence (every time a coherent unit lands)
(a) write the metacognition entry + index pointer; (b) update the relevant tracker/task list; (c) **commit with
explicit paths** (never a blanket `add -A`) + a co-author trailer; (d) report at milestone boundaries, not mid-batch.

## Practical orchestration notes (learned the hard way)
- **Free-text returns + self-written ledgers; wave-throttle concurrency + per-agent retry.** Rigid output
  schemas fail under rate-limiting; pass prior-stage outputs into the next agent's prompt as text.
- **"Done" is an orchestrator judgement, never a worker's self-report.** A milestone is done only when the main
  loop ground-truthed it (build/test from clean + the verifier + the closure sweep) and committed.
- **Decisions of record → an ADR**; design detail → a design doc; keep spec ↔ epics ↔ schema ↔ invariants ↔ ADRs
  mutually consistent (the harmonize step). The spec is the source of truth; keep it in sync as code lands.

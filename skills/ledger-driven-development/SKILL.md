---
name: ledger-driven-development
description: A multi-agent methodology for the brownfield reality of AI coding - you (or an agent) vibe-coded a first attempt that works-ish but has no spec or plan, and the code is now the only record of the requirements. LDD harvests those requirements out of the code → distils a minimal spec + plan → builds a walking skeleton → loops spec⇄build until an automated sweep finds zero gaps; auditable by a twin-ledger spine; run by orchestrated agents (builder + adversarial-verifier; the council). Use when cleaning up or rebuilding a vibe-coded/legacy codebase, or any time you want decisions auditable by construction.
---

# Ledger-Driven Development (LDD)

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

## The spine - two ledgers (auditability by construction)
1. **Intent ledgers** (`_harvest/*`) - *what the old code meant.* Before building, harvest the precious logic
   out of the legacy: the domain rules, the edge cases, the security mechanisms, the data shapes - each captured
   as a free-text ledger with provenance (where in the old code it came from). Provenance or it doesn't go in.
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
- **Walking skeleton**: the thinnest end-to-end slice that actually runs (one real path through every layer),
  not a layer-by-layer build. Prove the spine before deepening any limb.
- **Loop** spec⇄build, closing gaps each pass, until an automated **closure sweep** reports zero gaps against
  the spec. "Done" is *the sweep is clean*, not "the tests pass."

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
   over-long function / God-object / leaked abstraction?). **Escalate** to a full refactor pass only on flagged
   debt - the *continuous* closure-gate is the primary structural enforcement, so this is a scan, not a ritual.
3. **SECURITY**: supply-chain checks every milestone (cheap); the **heavy** security audit is **risk-targeted**:
   mandatory on a high-risk surface (auth, money, crypto, multi-tenancy/isolation, any externally-reachable
   entry point) + periodically - not bureaucratically run on a trivial surface the verifier already attacked.
4. **VERIFY**: an **independent adversarial verifier** (the primary security + correctness net, every
   milestone): re-run from clean, attack the milestone's invariants, try to break the new surface.
5. **PLAN**: **mandatory.** The milestone does NOT close, and the next build does NOT start, until the next
   steps are planned: the next milestone's scope/sequence/risks + the single next move. A high-stakes/uncertain
   next fork → a planning agent or a council. Never a vague "we'll see."

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

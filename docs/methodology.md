# Ledger-Driven Development: the full method

This is the long-form walkthrough. The two `skills/*/SKILL.md` files are the compressed canon; the
[README](../README.md) is the pitch. This doc is the one you read when you actually want to understand *why* each
move exists and *how* to run it on a real project. The companion [docs/artifacts.md](./artifacts.md) is the
deepest how-to: it tells you, artefact by artefact, exactly what to write and where it lives. Read this first for
the shape, then that for the construction.

Throughout, we use one running example so the pieces cross-reference into a single picture.

> **The running example: Tasky.** Tasky is a small team task-tracker that got vibe-coded over a few weekends. It
> works. People use it daily. But it is now about 14,000 lines of tangled TypeScript with no spec, no tests worth
> the name, and the usual scars of a thing that was never designed: there are *three* different ways to mark a
> task done (a `done` boolean, a `status` enum, and an `archivedAt` timestamp, all half-used and partly
> contradictory); there is a real and load-bearing rule, buried in one event handler, that *a task auto-reopens
> if a blocking task reopens*; and there is a security smell nobody owns, the share link has no expiry. The team
> wants to rebuild the core cleanly without losing the behaviour people rely on. Everything below is shown
> against Tasky, and the worked artefacts live under [`examples/`](../examples/).

---

## 1. The problem: brownfield, and the specific way vibe-coding breaks you

Classic software advice assumes a greenfield: blank page, write the spec, then build to it. Vibe-coding (whether
you did it by hand on caffeine or an agent did it for you) inverts that order. You got a *result* first. It runs,
so it shipped, so you moved on. **The spec was never written, and now the only honest record of what the system
is supposed to do is the code itself.** That is the brownfield reality, and AI coding produces it at scale.

This breaks a naive rebuild in three specific ways, and LDD is built to prevent all three by construction:

1. **Lost intent.** The code knows things nobody wrote down: an edge case, a domain rule, a security trick, a
   default that turned out to matter. In Tasky, the auto-reopen-on-blocker rule exists *only* as a few lines in a
   handler. A clean rewrite that works from a tidy mental model will silently drop it, and three weeks later a
   user files a bug that is really a lost requirement. The first move of LDD is to *harvest* that intent out of
   the code before anyone touches it.
2. **No audit trail.** Six weeks after a rewrite, nobody can say *why* the system is shaped the way it is, or
   which decisions were deliberate and which were accidents that calcified. So the next change is a guess.
3. **Quality drift.** "Looks done" is not done. Without a continuous, executable check, agents (and humans)
   accrete duplication and sprawl until the rebuild *is* the mess you were escaping. Tasky already has three ways
   to complete a task; an undisciplined rebuild will invent a fourth.

LDD is a way of working that makes intent explicit, makes every decision auditable, and makes "clean" a thing a
machine can check on every commit.

---

## 2. The arc: harvest, distil, walking skeleton, loop

The spine of the method is a four-step arc. Each step has work to do and a concrete **exit criterion**: a
condition you can point at, not a feeling.

```
harvest  ->  distil  ->  walking skeleton  ->  loop (spec <-> build) until zero gaps
```

### Step 1: Harvest (turn the code into written intent)

**What it involves.** You read the legacy as the requirements document it secretly is, and you extract its
meaning into **intent ledgers**: plain-text files, one domain area per file, that record *what the old code
meant* (the rules, the edge cases, the data shapes, the security mechanisms). The non-negotiable rule is
**provenance**: every claim cites the exact file and line it came from. If you cannot point at the code, the
claim does not go in the ledger. Harvest is a reading-and-citing job, not a designing job; you are not deciding
what *should* be true yet, only recording what *is* true in the old code.

For Tasky, harvest produces a `task-model.md` ledger that lays out all three completion mechanisms with their
citations, notes exactly where they contradict, and captures the auto-reopen rule with the exact handler line it
lives on (`src/events/onTaskReopen.ts:12`). The security smell (share links, no expiry, no revocation) is noted in
the ledger's DROP-list section too, with its provenance, flagged as a defect whose fix is a separate fork rather
than a behaviour to preserve.

**Exit criterion.** Every meaningful behaviour and rule in the legacy is either captured in an intent ledger with
provenance, or explicitly noted as "looked at, nothing load-bearing here." A reader who never saw the old code
could reconstruct what it did from the ledgers alone.

See [docs/artifacts.md, "Intent ledger"](./artifacts.md#intent-ledger) for the exact construction, the template
at [`templates/intent-ledger.md`](../templates/intent-ledger.md), and the worked file at
[`examples/_harvest/task-model.md`](../examples/_harvest/task-model.md).

### Step 2: Distil (the smallest complete spec)

**What it involves.** From the harvested intent you distil a **minimal spec**: the smallest complete set of
primitives that solves the domain. This is the most intellectually demanding step, because it is where you
*drop the sprawl on purpose*. Tasky's three completion paths collapse into **one** in the spec: a task has a
single ordered `status` lattice (`open -> in_progress -> done -> archived`, plus a terminal `deleted`), and the
`done` boolean and `archivedAt` timestamp are dropped, with the reason recorded (the boolean duplicated the enum;
`archivedAt` was overloaded with completion, age, and "deleted", so `archived` becomes a terminal status and
`deleted` its own explicit state). The auto-reopen rule is kept, because it is real behaviour people rely on, and
it is written into the spec as a named, testable invariant, **INV-REOPEN**: *if a task drops below `done`, every
task it blocks drops to at most `in_progress`*, recursively over `blockedBy`, with the legacy cycle guard
preserved. The share-link defect the harvest surfaced is left to a council (it is a genuine hard fork), not
settled in the spec by a sentence.

The data structure *is* the product. Most of distillation is getting the core types and invariants right;
everything else is a view over them. A dropped thing is never dropped silently: it is recorded with its reason,
so a future reader sees that it was a choice, not an oversight.

**Exit criterion.** A spec exists that (a) covers every behaviour the ledgers marked as load-bearing, (b) lists
every deliberately dropped thing with a reason, and (c) is small. If the spec is as big as the legacy, you have
transcribed, not distilled.

See [docs/artifacts.md, "The spec"](./artifacts.md#the-spec), [`templates/spec-skeleton.md`](../templates/spec-skeleton.md),
and [`examples/spec.md`](../examples/spec.md).

### Step 3: Walking skeleton (the thinnest end-to-end slice that runs)

**What it involves.** Before deepening any one part, you build the thinnest slice that actually runs **one real
path through every layer**: storage, domain, API, and whatever surface the user touches. For Tasky that is:
create a task, advance its `status` to `done`, and see that single ordered field agree across the list, the board,
and the shared view, through real persistence and a real endpoint. It deepens no one surface yet. The point is to
prove the spine is wired end to end before you grow any limb, so that integration risk surfaces immediately
instead of at the end.

A walking skeleton is the opposite of a layer-by-layer build (all the storage, then all the domain, then all the
API). Layer-by-layer hides the integration until last, which is exactly where the nasty surprises live.

**Exit criterion.** One real request runs end to end through every layer and produces the right result, from a
clean checkout, with the build/lint/test gates green. It is thin, but it is *whole*.

### Step 4: Loop (spec and build, until zero gaps)

**What it involves.** Now you loop. Each pass, you pick the next slice of the spec, build it on the skeleton, and
re-run an automated **closure sweep** that compares the build against the spec and reports the gaps. You close
the gaps the sweep finds, which often means amending the spec too (building reveals that a spec line was wrong or
incomplete, and the spec is the source of truth, so you fix it there and the journal records why). Spec and build
move together. For Tasky, M1's slice lands the lattice with INV-REOPEN enforced and tested and the council's
share-link expiry plus revocation build action; later passes take up the rest of the harvested behaviour (M2 makes
the `blockedBy` edges first-class), one coherent unit at a time.

**Exit criterion (and the headline rule of LDD).** **"Done" means the closure sweep finds zero gaps, not "the
tests pass."** Tests prove the code does what the tests say; the sweep proves the code covers what the *spec*
says and that the structural budgets hold. A green test suite over a half-built spec is not done.

---

## 3. The twin-ledger spine (auditability by construction)

Two ledgers run underneath the whole arc. They are the reason LDD produces an audit trail as a *side effect of
working*, rather than as a documentation chore bolted on afterwards.

**Intent ledgers (`_harvest/*`): what the old code meant.** Covered above. One file per domain area, free text,
provenance on every claim. They are written during harvest and amended if a later read of the legacy turns up
something missed. *Provenance or it does not go in* is the whole discipline.

**The metacognition journal (`metacognition/*`): why every decision was taken.** This is the part most methods
lack, and the heart of LDD. *Metacognition* means thinking about your own thinking. As you work, you write **one
entry per beat** (a beat is a coherent unit of work that lands together), recording what you did, which
tools/agents you used, and **every decision with its reason**: what you chose, the alternatives you considered,
and why you chose what you chose. Entries are append-only; an `INDEX.md` carries a one-line pointer to each. If a
decision is later reversed, you write a **new** entry that supersedes the old one. You never silently rewrite
history, because the superseded reasoning is itself evidence (it tells a future reader the option was tried and
rejected, and why).

The payoff is that at any moment, two questions that normally require archaeology have written answers. *Why is
the system shaped this way?* Read the journal (and the ADRs it graduates). *What did the old system actually mean
here?* Read the intent ledger. An agent that picks the work up cold can reconstruct the entire line of reasoning,
because the reasoning was recorded as it happened, not reverse-engineered later.

For the exact construction of each, see [docs/artifacts.md](./artifacts.md). The journal runs as two beats: the
action beat [`examples/metacognition/0001-harvest-task-model.md`](../examples/metacognition/0001-harvest-task-model.md)
records the harvest, and the decision beat
[`examples/metacognition/0002-collapse-completion-to-one-status.md`](../examples/metacognition/0002-collapse-completion-to-one-status.md)
makes the completion-collapse call with its rejected alternatives; read it alongside the spec line it explains.

**A load-bearing decision graduates to an ADR.** When a choice is big and hard to reverse (collapsing Tasky's
three completion paths into one is the canonical example), it is promoted from a journal entry into a short
**Architecture Decision Record**, so the major calls are easy to find and cite later without scrolling the whole
journal. This graduation needs no council: the decision was clear once the harvest was in, so journal beat `0002`
graduates straight to ADR-0001. See [docs/artifacts.md, "ADR"](./artifacts.md#adr-architecture-decision-record)
and [`examples/adr/ADR-0001-one-task-status-lattice.md`](../examples/adr/ADR-0001-one-task-status-lattice.md).

---

## 4. The standing disciplines (each prevents a specific failure)

The arc tells you *what to do*. The disciplines are the standing rules that keep it honest. Each one exists to
prevent a specific, named failure mode. If you drop a discipline, expect its failure.

### Ground-truth everything (no vibes)

Every claim, every finding, every "it's done" cites real evidence from the tree: a grep, a file read, a count, a
test run. **An agent (or a person) that cannot cite is ignored.**
*Prevents:* confident fiction. An agent will happily assert "Tasky has one completion path" because that is the
tidy answer; ground-truthing forces it to grep, find three, and write down all three. Most bad rebuilds are
built on plausible claims nobody checked.

### One writer of shared state (the orchestrator)

Only the **main loop** writes the shared artefacts: the ledgers, the index, the spec, the task list. Spawned
agents **return** their findings as text; they do not journal or mutate shared state themselves.
*Prevents:* collision and lost writes. Ten harvesters all appending to one journal at once will clobber each
other and produce an incoherent record. The orchestrator integrates serially and owns the truth. A corollary:
**"completed" is the orchestrator's judgement after ground-truthing, never a worker's self-report.**

### File-partition (author in parallel, integrate serially)

Parallel agents may write **new** files when each file has a single owner (one harvester owns `completion.md`,
another owns `blocking.md`, they never touch each other's). For **hot shared files**, agents *return* their
content blocks, a coherence agent emits an integration checklist, and the main loop applies it serially, then
verifies.
*Prevents:* two agents racing on one file and corrupting it. This is the rule that lets you parallelise harvest
across a dozen areas of Tasky safely. (This whole doc set was written that way: each author owned distinct files.)

### Build-first in the build phase (the deliberation budget)

Once you are building, the risk lives in the *unbuilt* surfaces, not in over-thinking the built ones. So default
to BUILD, not DELIBERATE. A reversible, swappable decision gets *one decisive sentence*, not a panel. Reserve the
full steelman (and the council) for irreversible, load-bearing forks. And **any panel, audit, or council must end
in a committed change or an explicit kill, never another document that defers.** You do not pick a buildable
artefact (a framework, a store, a protocol) by argument alone; you spike a thin slice that exercises it.
*Prevents:* analysis paralysis and decision-theatre. Whether Tasky's task IDs are UUIDs or ULIDs is one
sentence; collapsing the three completion paths earns a real ADR. Spending a council on the former and a sentence
on the latter is the failure this prevents.

### The closure-gate (continuous structural enforcement)

Make "is it clean? is it complete?" an *executable mechanism that runs on every commit*, not a periodic ritual:
a max-function-length lint that denies, a cross-module **duplication ratchet** (a budget you hold by *folding*
duplication, never by raising the number), formatter and linter as hard gates, and red-until-built tests for any
surface the spec declares but the build has not yet covered. The same continuous gate also runs the cheap edge of
the security and refactoring suites every commit: a `security_scan` (`vibescan --fast`, the one security owner) and
a `structure_scan` (`vibeclean` on the changed surface); the function-length number is owned in one place, the
closure-gate threshold (per the ownership matrix in [systems.md](./systems.md), system 7, LDD-INV-9).
*Prevents:* quality drift, the third failure from section 1. When this runs continuously, the heavy periodic
refactor becomes a *net for what slipped*, not the enforcement itself. The duplication ratchet is specifically
what stops Tasky's rebuild from re-growing a fourth way to complete a task: the second copy of the logic trips
the gate. See [docs/artifacts.md, "The closure-gate config"](./artifacts.md#the-closure-gate-config) and
[`examples/closure-gate.config.md`](../examples/closure-gate.config.md).

### Consolidation over fragmentation

When a new need resembles an existing one, **fold it in**; never spin up a parallel system, store, or service.
One source of truth per fact; every other surface is a regenerable view.
*Prevents:* the original sin that made Tasky a mess. Three completion mechanisms is fragmentation. The whole
rebuild is an act of consolidation, and the discipline is what keeps it consolidated under pressure to ship.

---

## 5. The orchestrated agent shapes (the engine)

LDD is built for multi-agent orchestration, not solo inline edits. Reach for an orchestration *shape* over a
hand edit for any substantive task. There are four standing shapes.

**Builder + adversarial verifier.** One agent produces; at least one *independent* skeptic tries to **break** it,
ground-truthing the real tree and re-running the load-bearing checks. The verifier's verdict is an *input* to the
orchestrator, not the final word. *Why it works:* a single pass rationalises away its own gaps; an adversary
hunting for failure finds the thing the builder talked itself out of seeing. On Tasky, the verifier on the
blocking milestone is the one that constructs a blocking cycle and checks the auto-reopen invariant does not
infinite-loop, a case the builder did not think to write.

**Multi-author + coherence.** N authors work in parallel, file-partitioned (one per area), and one coherence
agent merges, checks for contradiction and duplication, and emits an integration checklist the orchestrator
applies serially. *Why it works:* it gives you the throughput of parallelism without the collisions, by separating
authoring (parallel) from integration (serial, single-writer). This is the harvest shape: a dozen ledger areas of
Tasky harvested at once.

**The council.** For high-stakes *judgement* calls (not production volume), a fan-out of independent, named,
distinct-lens critics, each ground-truthing, each blunt, synthesised into one decision the same beat. Its full
shape, and the three-tier appeals hierarchy, is in section 7 and the [`council` skill](../skills/council/SKILL.md).

**Loop-until-dry.** For unknown-size work (gap-closure, bug-finding), keep spawning rounds until **K consecutive
rounds find nothing new**. *Why it works:* a fixed number of passes either stops too early (misses the tail) or
wastes the last passes; the consecutive-empty-rounds rule sizes itself to the actual work. This is how the
spec-and-build loop in step 4 knows it is finished.

---

## 6. The milestone close: 5 phases

A milestone is a meaningful chunk of the rebuild (for Tasky: M1 "the task status lattice," then M2 "blocking-graph
editing"). A milestone is **not done** until all five phases run, in order:

```
BUILD  ->  STRUCTURE  ->  SECURITY  ->  VERIFY  ->  PLAN
```

1. **BUILD.** Implement the milestone's scope. Formatter, linter, and tests green.
2. **STRUCTURE.** A mandatory structural *scan* of the new surface (the closure-gate continuous gates plus
   `vibeclean` on the changed surface): does the duplication ratchet hold? Any over-long function, God-object, or
   leaked abstraction? You escalate to a full refactor pass (the refactoring suite) *only* if the scan flags real
   debt, because the continuous closure-gate is already doing the primary structural enforcement. This is a scan,
   not a ritual.
3. **SECURITY.** The continuous `vibescan --fast` gate (the one security owner, subsuming the supply-chain check)
   has already run on every commit; at close you run the full `vibescan .` sweep. The *heavy* deep audit (owned by
   the security suite methodology, with `vibeaudit` as its scanner engine) is **risk-targeted**: mandatory on a
   high-risk surface (auth, money, crypto, multi-tenancy, anything externally reachable) and periodic otherwise, not
   bureaucratically run on a trivial surface the verifier already attacked. Tasky's M1 includes exactly such a
   high-risk surface: the share link, its new expiry plus revocation, and the resolve-path access check all get the
   deep audit.
4. **VERIFY.** `vibetest` checks test quality (missing tests, weak assertions, coverage gaps), and an
   **independent adversarial verifier** re-runs from a clean checkout, attacks the milestone's invariants, and tries
   to break the new surface. This is the primary correctness-and-security net, every milestone.
5. **PLAN.** **Mandatory.** The milestone does not close, and the next build does not start, until the next steps
   are planned: the next milestone's scope, sequence, and risks, plus the single next move. A high-stakes or
   uncertain next fork escalates to a planning agent or a council. There is no drifting into an unplanned next
   milestone.

Which tool owns which concern and at which trigger is not restated here: see the two-tier(+) ownership matrix in
[docs/systems.md](./systems.md) (system 7), the single source of truth (LDD-INV-9).

The sign-off for a milestone records all five phases and their evidence. See
[docs/artifacts.md, "The milestone sign-off"](./artifacts.md#the-milestone-sign-off),
[`templates/milestone-signoff.md`](../templates/milestone-signoff.md), and the worked
[`examples/M1-signoff.md`](../examples/M1-signoff.md).

---

## 7. The deliberation court (how the hard forks get decided)

Most build-phase decisions are reversible and get one sentence (the deliberation budget). A few are high-stakes
and hard to reverse, and those go to the council, an adversarial deliberation court modelled on UK law. The full
treatment is in the [`council` skill](../skills/council/SKILL.md); here is the shape and when each tier fires.

**The Council (first instance).** Convened for a genuine high-stakes, hard-to-reverse fork (an architecture
choice, build-vs-consume, sequencing a whole program), or for an honest retrospective or pre-mortem. It is a
single fan-out of a handful of **independent, named seats**, each given a **distinct lens** (project health,
process critic, devil's advocate, plus a domain lens: security, cost, UX, the advocate of a named alternative).
Each seat **ground-truths against the real code first**; a seat that cannot cite is ignored. Seats run
independently and do not see each other while running, so they cannot converge into groupthink, and each leads
with the blunt, uncomfortable truth. The Council is **ephemeral**: the seats dissolve after, and nothing persists
but the verdict and the **surviving dissent** (recorded, never buried, because it is the standing of any future
appeal). The non-negotiable discipline: a Council **ends in a build action or a kill**, never in "we will look at
it later."

For Tasky, the completion collapse did **not** need a council: once the harvest was in, collapsing three
mechanisms to one ordered status was the clear call, so journal beat `0002` graduated straight to ADR-0001 with one
decisive line of reasoning. The council was reserved for the genuinely hard fork the build could not just decide:
*do we keep share links simple (permanent, unguessable tokens), or add expiry and revocation now?* It is a
security boundary, hard to reverse once links are in the wild, with real cost on both sides (UX friction vs
standing exposure), which is exactly what a council is for. Three named seats (security, UX/simplicity, a
devil's-advocate pre-mortem) ground-truth `src/api/share.ts`, and the synthesis ends in a committed build action
(add `expiresAt` and `revokedAt`, fail the resolve path closed, one revoke action, no settings surface) plus a
logged surviving dissent (the UX seat's objection to a fixed window). The worked verdict is at
[`examples/council/share-link-expiry-verdict.md`](../examples/council/share-link-expiry-verdict.md);
see [docs/artifacts.md, "The council verdict"](./artifacts.md#the-council-verdict) for how to constitute one.

**The Appeals Council.** Convened when a verdict is **challenged with standing**: the principal disagrees, a
load-bearing dissent was left unresolved, or new ground-truth contradicts a point the Council relied on. ("I
would have designed it differently" is not standing.) It re-weighs the **merits** as a *review*, with fresh
independent seats who must **engage the Council's actual reasoning** (handed the full lower-court record), and may
**uphold or overturn**.

**The Supreme Council.** The rare apex. It does *not* re-litigate the design. It hears **only points of law**:
*was the invariant spec and the LDD discipline correctly applied in reaching this decision?* (Were the invariants
honoured? Was the ground-truthing real, the one-writer rule kept?) Because it rules on law rather than taste, its
ruling becomes **spec law**: an immutable, numbered precedent that **binds every future court**. A first-instance
Council cannot overturn spec law, and a decision that collides with a precedent is refused at the spec layer the
same way a trust boundary refuses an unknown command. Only a later Supreme Council, expressly narrowing the
precedent on a point of law, can refine it.

---

## 8. Running it at scale: always-on orchestration and a standing goal

The shapes in section 5 are fan-outs of agents. In Claude Code they run as **workflows**: deterministic scripts
that spawn and coordinate many subagents. Two features turn LDD from a hand-cranked process into a continuous
engine, and you should understand the trade before switching them on.

**Always-on orchestration.** With this on, the model **authors and runs a workflow by default** for every
substantive task, instead of editing inline. LDD gives those workflows their shape (the harvest fan-out, builder
plus verifier, the council), so the two compose: the methodology says *what* to orchestrate, the mode makes
orchestration the default *how*.

**A standing goal.** Give the agent a persistent objective ("rebuild Tasky's core to a clean, verified state")
and it keeps working toward it across many turns: planning the next milestone, starting the next workflow on its
own, closing each milestone with the 5 phases.

**The trade, stated plainly.** Paired, these produce **heavy, long-running, fan-out workflows**. One standing
goal can drive dozens of workflows in sequence, each spawning many parallel agents (harvesters, builders,
verifiers, whole councils), running for a long time with little human input. That is the source of the power: it
can build and adversarially verify a large system largely autonomously. It is also the source of the cost: it
consumes a lot of tokens and compute, by design. The trade is deliberate, thoroughness over speed. What keeps
that throughput honest rather than runaway is the rest of LDD: the continuous closure-gate, the adversarial
verifier on every milestone, the council on the hard forks, and the metacognition journal recording why each of
those many agents did what it did. Turn the engine on once the disciplines are in place, not before.

---

## 9. How to start on YOUR brownfield tomorrow

A concrete checklist. Run it against your own tangled, vibe-coded project the way the example runs against Tasky.

1. **Stand up the two ledgers.** Create `_harvest/` and `metacognition/` (with `metacognition/INDEX.md`). Copy
   the templates from [`templates/`](../templates/). Nothing else is real until these exist.
2. **Pick your "three completion paths."** Find the one or two tangles you already know are there: the duplicated
   mechanism, the buried rule, the security smell you have been ignoring. Those are your first harvest targets.
3. **Harvest, with provenance.** Read the legacy and write intent ledgers, one area per file, every claim citing
   a file and line. Parallelise it (multi-author + coherence) if it is large. Stop when a reader could
   reconstruct the old behaviour from the ledgers alone.
4. **Distil the minimal spec.** Write the smallest complete spec. Drop the sprawl *with a recorded reason*. Keep
   the load-bearing rules as invariants. Add the fixes the harvest surfaced (your no-expiry share link).
5. **Wire the closure-gate before you build.** Stand up the formatter, linter, max-function-length deny, and the
   duplication ratchet as commit gates, so "clean" is checkable from the first line of the rebuild.
6. **Build the walking skeleton.** One real path through every layer, green from a clean checkout. Thin but whole.
7. **Loop spec and build to zero gaps.** Each pass: build a slice, run the closure sweep, close the gaps (amend
   the spec when building proves it wrong), journal the beat, commit with explicit paths. Use a council only for
   the genuine hard forks; build the rest.
8. **Close each milestone with the 5 phases.** BUILD, STRUCTURE, SECURITY, VERIFY, PLAN. Do not skip PLAN.
9. **Only then, if you want the engine, turn on always-on orchestration with a standing goal,** and let it run,
   knowing the cost and trusting the disciplines to keep it honest.

You do not need the plugin to do any of this; the method stands on its own. The plugin just makes the shapes the
default. Either way, the rule that matters most is the simplest one: **provenance or it does not go in, and "done"
means the sweep is clean.**

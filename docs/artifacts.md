# The artefacts, and how to constitute each one

LDD produces a small set of durable artefacts. They are not paperwork; they are the method. The ledgers make the
rebuild auditable by construction, the spec is the source of truth, and the sign-offs and verdicts are the record
of *how* "done" was decided. This document is the deepest how-to in the repo: for every artefact, it tells you
what it is, what failure it prevents, **how to constitute it step by step** (where it lives, what goes in, the
provenance rule, who writes it), when to write it, and the mistakes people actually make.

Read [docs/methodology.md](./methodology.md) first for the arc these artefacts sit in. The blank templates live
under [`templates/`](../templates/); every worked example lives under [`examples/`](../examples/) and
uses **one** running project so the artefacts cross-reference into a single real picture.

> **The running example: Tasky.** A small team task-tracker, vibe-coded over a few weekends into about 14,000
> lines of tangled TypeScript with no spec and no real tests. It has three different ways to mark a task done (a
> `done` boolean, a `status` enum, and an `archivedAt` timestamp, all half-used), a buried rule that *a task
> auto-reopens if a blocking task reopens*, and a security smell: share links have no expiry and no revocation.
> Every example below is a real artefact from rebuilding Tasky's core with LDD.

**Two rules that govern every artefact, stated once:**

- **Provenance or it does not go in.** Anything that claims to describe the legacy cites the exact file and line
  it came from. A claim you cannot point at is a vibe, and vibes do not enter the record.
- **One writer of shared state.** The orchestrator (the main loop) is the *only* thing that writes shared
  artefacts: the ledgers, the index, the spec, the task list, the sign-offs. Spawned agents **return** their
  findings as text; the orchestrator integrates them serially. This is what stops parallel agents from clobbering
  each other.

A quick map of where things live:

```
_harvest/                 intent ledgers (one file per domain area)
metacognition/            the journal (one file per beat) + INDEX.md
adr/                      ADRs (one file per load-bearing decision)
spec.md  (or spec/)       the distilled minimal spec
M<N>-signoff.md           milestone sign-offs (one per milestone)
council/                  council verdicts, one per convening (slug-named) + SPEC-LAW.md
closure-gate.config.md    the continuous structural enforcement config
```

(The worked example uses exactly this layout: see [`examples/`](../examples/). It has one milestone so far,
[`examples/M1-signoff.md`](../examples/M1-signoff.md), and one council verdict,
[`examples/council/share-link-expiry-verdict.md`](../examples/council/share-link-expiry-verdict.md); there is no
SPEC-LAW.md yet, because no Supreme Council has ruled.)

---

## Intent ledger

**What it is.** A plain-text file, one per domain area, that records *what the old code meant* in that area: the
domain rules, the edge cases, the data shapes, the security mechanisms, and the known defects. It is the harvest
of intent out of a codebase that never wrote its intent down. For Tasky, `_harvest/task-model.md` records all
three completion mechanisms and how they contradict, captures the auto-reopen-on-blocker rule with the one handler
line it lives on, and in its DROP-list section flags the share-link smell (no expiry, no revocation) as a defect
whose fix is its own fork.

**Why it exists / what failure it prevents.** It prevents **lost intent**: the silent dropping of a rule that
existed only as code. A clean rewrite working from a tidy mental model would never reinvent Tasky's auto-reopen
rule, because nobody remembers it is there. The ledger is what makes that rule survive the rebuild.

**How to constitute it, step by step.**
1. **Where it lives:** `_harvest/<area>.md`, one file per coherent domain area (the example folds completion and
   blocking into one `task-model.md` because they are one tangle; a larger harvest would split `auth.md`,
   `sharing.md`, and so on). Free text, not a rigid schema (rigid schemas fail under agent rate-limiting; prose
   does not).
2. **What goes in:** for each rule/behaviour/shape, a short statement of *what the old code does* (not what it
   should do), the **provenance** (file path + line or symbol), and a note on anything contradictory, defective,
   or surprising. Mark known defects explicitly (Tasky's no-expiry, no-revocation share link is recorded as a
   *defect whose fix is a separate fork*, not a behaviour to preserve).
3. **The provenance / citation rule:** every claim cites real evidence. `completion logic lives in three places:
   src/models/task.ts:18 (done bool), src/models/task.ts:21 (status enum), src/models/task.ts:24 (archivedAt)`.
   No citation, no entry.
4. **Who writes it:** during a parallel harvest, one agent owns one area's file (file-partition), reads the
   legacy, and *returns* its findings; the orchestrator writes them in. For a small harvest the orchestrator
   writes directly. Either way the file has a single owner.

**When to write it.** During the **harvest** step, first thing, before any spec or build. Amend a ledger only if
a later read of the legacy turns up something the first pass missed (a new beat, a new journal entry).

**Common mistakes.**
- Writing what the code *should* do instead of what it *does*. The ledger is descriptive, not aspirational; that
  is the spec's job.
- Omitting provenance because "it is obvious." It is not obvious to the agent that picks this up in six weeks.
- One giant `harvest.md`. Split by area so harvest can parallelise with one owner per file.
- Silently skipping a defect because it is embarrassing. Record it, flag it, fix it in the spec.

**See:** template [`templates/intent-ledger.md`](../templates/intent-ledger.md); worked example
[`examples/_harvest/task-model.md`](../examples/_harvest/task-model.md).

---

## Metacognition journal entry

**What it is.** One append-only entry per **beat** (a coherent unit of work that lands together) recording
*everything you thought*: what you did, the tools and agents you used, and **every decision with its reason**,
the alternatives weighed, and why you chose what you chose. The journal is the running narrative of *why the
system is the way it is*. It is the heart of LDD, the part most methods lack.

**Why it exists / what failure it prevents.** It prevents the **no-audit-trail** failure. Six weeks on, "why did
we collapse the three completion paths into one ordered status and drop `archivedAt` as a field?" has a written
answer instead of a guess (it is journal beat `0002`). It also prevents *re-litigating settled questions*: a
superseded entry shows an option was already tried and rejected, and why.

**How to constitute it, step by step.**
1. **Where it lives:** `metacognition/NNNN-short-slug.md`, zero-padded and ordered (the example runs
   `0001-harvest-task-model.md` then `0002-collapse-completion-to-one-status.md`), plus a one-line pointer
   appended to `metacognition/INDEX.md`.
2. **What goes in:** the beat's *what* (what landed), *how* (tools/agents/workflows used), and the **decisions**:
   for each, what was chosen, the alternatives, the reason, and any surviving dissent. Keep it honest and blunt;
   this is a thinking log, not a press release.
3. **The append-only rule:** never edit a past entry to change a decision. If you reverse course, write a **new**
   entry that *supersedes* the old one and says so (`supersedes 0002: building blocking revealed the lattice needs
   another state`). History is evidence; do not rewrite it.
4. **Who writes it:** the **orchestrator only** (one-writer rule). Spawned agents return their what/why as text;
   the orchestrator distils that into the single entry. Workers never journal (they would collide).

**When to write it.** Every beat, as part of the per-beat cadence: write the entry and the index pointer, update
the task list, then commit with explicit paths and a co-author trailer. One entry per beat, no more, no less.

**Common mistakes.**
- Editing history. Supersede, never overwrite.
- Letting workers journal. They return; the orchestrator writes. Otherwise the journal is an incoherent race.
- Recording *what* but not *why*. The why is the whole value; "added blocking" is useless, "kept the invariant
  as a write-time cascade rather than a read-time computation because the UI must show reopened tasks
  immediately" is the point.
- Skipping the index pointer, so nobody can scan the journal without opening every file.

**See:** template [`templates/metacognition-entry.md`](../templates/metacognition-entry.md); worked examples
[`examples/metacognition/0001-harvest-task-model.md`](../examples/metacognition/0001-harvest-task-model.md) (action
beat) and [`examples/metacognition/0002-collapse-completion-to-one-status.md`](../examples/metacognition/0002-collapse-completion-to-one-status.md)
(decision beat), and the [`INDEX.md`](../examples/metacognition/INDEX.md) they point from.

---

## ADR (Architecture Decision Record)

**What it is.** A short, standalone record of one *load-bearing, hard-to-reverse* decision: the context, the
options, the decision, and the consequences. An ADR is a journal entry that earned a promotion, pulled out where
the big calls are easy to find and cite by ID. For Tasky, `adr/ADR-0001-one-task-status-lattice.md` records the
decision to collapse three completion mechanisms into one ordered `status` lattice. It graduated from journal beat
`0002` directly, with no council: once the harvest was in, the call was clear.

**Why it exists / what failure it prevents.** It prevents **the big decisions getting lost in the journal**. The
journal is chronological and dense; a reader looking for *the* completion-model decision should find one
authoritative, citable record, not scroll a hundred beats. ADRs are also what later decisions *cite* as
controlling context.

**How to constitute it, step by step.**
1. **Where it lives:** `adr/ADR-NNNN-slug.md`, numbered, append-only as a set (you supersede an ADR with a
   new ADR, you do not edit the old one to flip the decision).
2. **What goes in:** Context (what forced the decision: Tasky's three contradictory completion paths), Options
   (keep all three plus a sync layer; keep the enum unordered; a single `completedAt` timestamp; the ordered
   lattice), Decision (collapse to one ordered `status` lattice, `open -> in_progress -> done -> archived` plus a
   terminal `deleted`, promote the auto-reopen rule to the named invariant INV-REOPEN, write a migration map, drop
   `done` and `archivedAt` as fields with reasons), Consequences (a one-time migration cost; a permanently simpler
   model; `archived` and `deleted` stop being overloaded). Link the journal beat it graduated from (and a council
   verdict only if one decided it; this one had none).
3. **The provenance rule:** an ADR about legacy behaviour cites the intent ledger (and through it the code); an
   ADR resolving a council question cites the verdict. The lattice ADR cites the harvest and journal beat `0002`,
   no council. It is grounded, like everything else.
4. **Who writes it:** the orchestrator, when a journal decision is load-bearing enough to graduate, or when a
   council verdict needs a durable home.

**When to write it.** When a choice is big and hard to reverse: an architecture fork, a data-model collapse, a
build-vs-consume call, a sequencing decision for a whole program. Reversible choices stay as one-sentence journal
notes (the deliberation budget); they do not get ADRs.

**Common mistakes.**
- ADR-ing everything. If it is reversible, it is a sentence, not an ADR. Over-producing ADRs buries the real ones
  exactly like an over-dense journal.
- Editing an ADR to reverse it. Write `ADR-0009 supersedes ADR-0001` instead.
- Omitting the dropped-with-reason consequences. The value of Tasky's lattice ADR is partly the record that
  `archivedAt` as a field was *deliberately* removed, so nobody re-adds it as a "missing feature."

**See:** template [`templates/adr.md`](../templates/adr.md); worked example
[`examples/adr/ADR-0001-one-task-status-lattice.md`](../examples/adr/ADR-0001-one-task-status-lattice.md).

---

## The spec

**What it is.** The distilled, minimal description of the system to build: the primitives (the core data
structures), the invariants (rules that must always hold), and the things deliberately dropped (each with a
reason). It is the **source of truth**: the code is kept in sync with the spec, not the other way around. For
Tasky, the spec defines a task with a single ordered `status` lattice (`open -> in_progress -> done -> archived`
plus a terminal `deleted`), the named invariant INV-REOPEN (*if a task drops below `done`, every task it blocks
drops to at most `in_progress`*, recursively, with a cycle guard), and a "deliberately dropped" section listing
the `done` boolean and `archivedAt`-as-a-field with why.

**Why it exists / what failure it prevents.** It prevents **quality drift and scope sprawl**. Without a minimal
spec to build against, a rebuild re-grows the legacy: it has no definition of "complete" and no record of what
was dropped on purpose, so every dropped thing looks like a missing feature waiting to be re-added. The spec is
also what the closure sweep checks the build against; "done" is *the build covers the spec*.

**How to constitute it, step by step.**
1. **Where it lives:** `spec.md` for a small system, or a `spec/` directory (one file per area) for a larger one,
   kept mutually consistent with the ADRs and the invariants.
2. **What goes in:** the **primitives** (the minimal data structures: the `Task`, its ordered `status` lattice,
   its `blockedBy` relation), the **invariants** (the always-true rules, written as numbered checkable statements,
   like INV-REOPEN), the **behaviours** (what each operation does), and a **deliberately dropped** section (each
   dropped legacy thing + the reason). Note where a harvested defect is being handled elsewhere (Tasky's
   share-link expiry is settled by council, not in this spec, so the spec records the pointer rather than the
   fix).
3. **The provenance rule:** every kept behaviour traces to an intent ledger; every dropped thing names what it
   dropped and why (cite the ledger and the ADR/council verdict that decided it). The spec is distilled *from*
   the harvest, so it is grounded in it.
4. **Who writes it:** the orchestrator, during **distil**, and it keeps amending the spec during the **loop** as
   building reveals a spec line was wrong or incomplete. The spec is a living source of truth, not a frozen
   up-front document.

**When to write it.** First draft during the distil step, right after harvest. Then continuously: every loop
pass that changes the truth updates the spec, with a journal entry recording why.

**Common mistakes.**
- Transcribing instead of distilling. If the spec is as big as the legacy, you copied the sprawl. The spec for
  Tasky's completion is *smaller* than the three legacy paths combined, on purpose.
- Dropping things silently. A dropped thing with no recorded reason reads as an accident and gets re-added.
- Letting the code drift ahead of the spec. The spec is the source of truth; when building proves it wrong, fix
  the spec, do not let the code quietly become the new truth.
- Writing invariants as prose nobody can check. INV-REOPEN (*if a task drops below `done`, every task it blocks
  drops to at most `in_progress`*) should be a line a verifier and a test can both target.

**See:** template [`templates/spec-skeleton.md`](../templates/spec-skeleton.md); worked example
[`examples/spec.md`](../examples/spec.md).

---

## The milestone sign-off

**What it is.** The record that a milestone ran all **five close phases** and the evidence for each. It is the
artefact that turns "looks done" into "is done, and here is the proof." For Tasky's first milestone,
`M1-signoff.md` records the BUILD (the status lattice, the migration map, INV-REOPEN, and the council's share-link
expiry plus revocation, gates green), the STRUCTURE scan (it caught an inlined `isDone` and folded it), the
SECURITY deep audit (the share-link surface; it caught a UTC expiry bug), the VERIFY result (the verifier built a
blocking cycle and confirmed the reopen cascade terminates, and attacked an expired and a revoked token), and the
PLAN (next milestone M2: blocking-graph editing).

**Why it exists / what failure it prevents.** It prevents **"done" being a self-report**. A milestone is done
only when the orchestrator ground-truthed it: built and tested from a clean checkout, ran the closure sweep, and
an independent verifier attacked it. The sign-off is where that judgement and its evidence are recorded, so
"completed" is never a worker's claim.

**How to constitute it, step by step.**
1. **Where it lives:** `M<N>-signoff.md` (or `milestones/M<N>-<slug>-signoff.md` once there are several), one per
   milestone. The example keeps its single milestone at the examples root as `M1-signoff.md`.
2. **What goes in:** a section per phase: **BUILD** (scope delivered, gates green, from clean), **STRUCTURE** (the
   scan result: ratchet held / debt found and what was done), **SECURITY** (supply-chain check + whether the deep
   audit was triggered and its finding), **VERIFY** (the independent verifier's attack and verdict, with
   evidence), **PLAN** (the next milestone's scope/sequence/risks + the single next move). Each phase cites real
   evidence (a test run, a grep, a sweep report).
3. **The provenance rule:** every "passed" cites the artefact that proves it (the verifier's returned findings,
   the sweep output, the security tool result). A sign-off with no evidence is exactly the self-report it exists
   to prevent.
4. **Who writes it:** the orchestrator, at the milestone close, synthesising the returned outputs of the
   structure scan, the security check, and the adversarial verifier into one record.

**When to write it.** At the close of each milestone, after BUILD through VERIFY have run and before the next
build starts. The **PLAN** section is mandatory and is the gate: the next milestone does not begin until it is
filled in.

**Common mistakes.**
- Skipping PLAN and drifting into the next milestone unplanned. PLAN is mandatory; the sign-off is incomplete
  without it.
- Running the deep security audit on a trivial surface as a ritual, or skipping it on a high-risk one. It is
  *risk-targeted*: Tasky's M1 carries an externally-reachable share-link surface (the link, its expiry, the
  resolve check) and earns it; a pure-refactor milestone may not.
- Letting the builder also be the verifier. VERIFY is an *independent* adversarial pass, or it is theatre.
- Recording verdicts without evidence. "Verified: pass" with nothing behind it is a vibe.

**See:** template [`templates/milestone-signoff.md`](../templates/milestone-signoff.md); worked example
[`examples/M1-signoff.md`](../examples/M1-signoff.md).

---

## The council verdict

**What it is.** The single synthesised record of one convening of the deliberation court: the question, the seats
and their distinct lenses, each seat's ground-truthed verdict, the synthesis, the decision (a build action or a
kill), and the **surviving dissent**. For Tasky, `council/share-link-expiry-verdict.md` records the council on
*keep share links simple, or add expiry plus revocation now*, and its verdict ends in a committed build action
plus one logged surviving dissent. (Note: the completion collapse did **not** go to council; it was clear enough
to graduate straight from journal beat `0002` to ADR-0001. A council is reserved for the genuinely hard fork.)

**Why it exists / what failure it prevents.** It prevents two failures at once. First, **a single perspective
rationalising a hard call**: independent, blunt, distinct-lens seats catch what one mind talks itself out of
seeing. Second, **a deliberation that defers**: the verdict *is* the decision and triggers the build action the
same beat, so the council cannot become a meeting that produces another meeting. The recorded dissent also
preserves the **standing** for any future appeal.

**How to constitute it, step by step.**
1. **Where it lives:** `council/<slug>-verdict.md`, one per convening (the example is
   `council/share-link-expiry-verdict.md`; number the slug if you prefer ordering). Supreme Council rulings
   additionally append to `council/SPEC-LAW.md` (see below).
2. **What goes in:** the **question** (a genuine high-stakes, hard-to-reverse fork), the **seats** (3 to 5
   distinct lenses: project health, process critic, devil's advocate, plus a domain lens like security or cost or
   the advocate of a named alternative), each seat's **ground-truthed verdict** (citing real evidence from the
   tree), the **synthesis** (the through-line the orchestrator reconciles from seats that disagree), the
   **decision** (build action or kill), and the **surviving dissent** (recorded, never buried).
3. **The provenance / independence rule:** each seat must ground-truth first (greps, file reads, counts, test
   runs); a seat that cannot cite is ignored. Seats run **independently** and do not see each other mid-run, so
   they cannot converge into groupthink. The orchestrator synthesises after.
4. **Who writes it:** the seats *return* their verdicts as text; the orchestrator writes the single synthesised
   verdict file and *acts on it the same beat* (commits the build action, or records the kill). The seats are
   ephemeral and dissolve; only the verdict and the dissent persist.

**When to write it.** Only for a genuine high-stakes, hard-to-reverse fork, or an honest retrospective or
pre-mortem. A reversible decision gets one sentence, not a council. A court is expensive currency; spend it
rarely.

**The appeals tiers (same artefact shape, scoped remit).** A verdict stands by default. An **Appeals Council**
(convened only with *standing*: the principal disagrees, a load-bearing dissent is unresolved, or new
ground-truth contradicts a relied-upon point) re-weighs the merits *as a review*, handed the full lower-court
record, and may uphold or overturn. A **Supreme Council** (the rare apex) reviews **only points of law**: was the
invariant spec and the LDD discipline correctly *applied*? Its ruling becomes **spec law**, an immutable numbered
precedent in `council/SPEC-LAW.md` that binds every future court; a decision that collides with it is refused at
the spec layer the same way a trust boundary refuses an unknown command. Each tier gets fresh independent seats
and the full record of every court below.

**Common mistakes.**
- Convening for a reversible decision. That is the build-first budget violation; build it instead.
- A verdict that defers ("let us revisit next sprint"). A council ends in a build action or a kill, full stop.
- Burying the dissent because it lost. The dissent is the standing of any future appeal; record it.
- Seats that did not ground-truth, or that saw each other mid-run. Either one collapses the independence the
  council exists for.
- Appealing for free. Escalation needs standing; "I would have designed it differently" is not standing.

**See:** template [`templates/council-verdict.md`](../templates/council-verdict.md); worked example
[`examples/council/share-link-expiry-verdict.md`](../examples/council/share-link-expiry-verdict.md);
the full court treatment in the [`council` skill](../skills/council/SKILL.md).

---

## The closure-gate config

**What it is.** The configuration of the **continuous structural enforcement**: the executable checks that run on
every commit and decide, mechanically, whether the tree is clean and complete. For Tasky,
`closure-gate.config.md` defines the formatter and linter as hard gates, a max-function-length deny, the
cross-module **duplication ratchet**, and red-until-built tests for spec surfaces not yet covered.

**Why it exists / what failure it prevents.** It prevents **quality drift** by making "clean" a thing a machine
checks continuously, not a thing humans audit occasionally. It is the discipline that stops Tasky's rebuild from
re-growing a fourth way to complete a task: the second copy of completion logic trips the duplication ratchet and
the commit is refused. When this runs on every commit, the heavy periodic refactor becomes a *net for what
slipped*, not the primary enforcement.

**How to constitute it, step by step.**
1. **Where it lives:** `closure-gate.config.md` documents the policy; the actual gates live in your real tooling
   (the linter config, the pre-commit hook, the CI job). The `.md` is the human-readable contract; the tooling is
   the enforcement.
2. **What goes in:** each check, its threshold, and whether it **denies** (blocks the commit) or **warns**. The
   standing set: formatter + linter as hard gates; a max-function-length deny; the **duplication ratchet** (a
   cross-module duplication budget); red-until-built tests for any spec surface declared but not yet covered.
3. **The ratchet rule (the load-bearing one):** the duplication budget is a number you only ever hold or *lower*,
   by folding duplication. You **never raise it to make a commit pass.** Raising the ratchet is conceding the
   sprawl you are fighting. If a change would exceed the budget, you fold the duplication, you do not move the
   line.
4. **Who writes it:** the orchestrator, ideally **before the walking skeleton** so "clean" is checkable from the
   first line of the rebuild. It is amended as new structural risks appear, only ever tightening.

**When to write it.** Early: stand up the closure-gate before you build the walking skeleton, so the first commit
is already gated. Revisit it at the STRUCTURE phase of each milestone close, tightening if the scan found a class
of debt the gate should now catch.

**Common mistakes.**
- Raising the duplication ratchet to get a commit through. This is the single most corrosive mistake; it converts
  the gate from enforcement into decoration.
- Treating the closure-gate as a periodic audit instead of a per-commit mechanism. If it does not run on every
  commit, drift accumulates between runs.
- Configuring warns where you need denies. A warn nobody reads is not a gate.
- Standing it up *after* the build. Then the first thousand lines were never gated, and you are auditing instead
  of enforcing.

**See:** template [`templates/closure-gate.config.md`](../templates/closure-gate.config.md); worked example
[`examples/closure-gate.config.md`](../examples/closure-gate.config.md).

---

## How the artefacts cross-reference (one picture)

The artefacts are not independent; they form a chain of grounding. The Tasky example threads one tangle (task
completion) through most of them, and routes the one genuinely hard fork (share-link security) through the council,
so you can see both the no-council path and the council path end to end:

The completion chain (no council, because the call was clear once harvested):

- `_harvest/task-model.md` records the **three** legacy completion paths and the buried auto-reopen rule, each
  with provenance.
- The journal runs two beats: `metacognition/0001-harvest-task-model.md` (the action beat that ran the harvest)
  then `metacognition/0002-collapse-completion-to-one-status.md` (the decision beat that picks the ordered
  lattice, listing the rejected alternatives).
- Beat `0002` graduates straight to `adr/ADR-0001-one-task-status-lattice.md` (no council), which records the
  lattice, the migration map, and promotes the auto-reopen rule to the named invariant INV-REOPEN.
- `spec.md` defines the single ordered `status` lattice primitive and INV-REOPEN, and lists the `done` boolean
  and `archivedAt`-as-a-field as deliberately dropped, citing the ADR.
- `closure-gate.config.md`'s duplication ratchet is what stops a *fourth* completion path from sneaking back in.

The share-link fork (the one decision that earned a court):

- The same harvest flags share links as a security defect (no expiry, no revocation) in its DROP-list section.
- `council/share-link-expiry-verdict.md` weighs keep-simple vs add-expiry-plus-revocation, three named seats each
  ground-truthing `src/api/share.ts`, ending in a committed build action plus one logged surviving dissent.

Both lines land in one milestone close: `M1-signoff.md` records that the status lattice, INV-REOPEN, and the
council's share-link build action all passed all five phases with evidence (PASS WITH FIXES), and plans M2
(blocking-graph editing).

Follow that chain in [`examples/`](../examples/) and you have read LDD working on one real problem from legacy
tangle to verified, auditable rebuild.

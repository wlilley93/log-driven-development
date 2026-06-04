# Worked example: rebuilding Tasky with LDD

This folder is one continuous, filled-in run of Log-Driven Development on a single fictional project. Every
file here describes the *same* project and cross-references the same handful of concrete details, so you can see
what each LDD artefact looks like in practice and how they fit together. Read it top to bottom and you will watch
a real mess turn into a small clean spec, with the reasoning recorded at every step.

If you want the method itself, read [`../skills/log-driven-development/SKILL.md`](../skills/log-driven-development/SKILL.md)
and [`../skills/court/SKILL.md`](../skills/court/SKILL.md). This folder is the *applied* version: copy the
shapes here for your own project.

---

## The scenario: Tasky

**Tasky** is a small team task-tracker. It was vibe-coded over a few weekends. It works, a handful of teams
actually use it, and nobody wants to lose it. But it is now about 14,000 lines of tangled TypeScript with:

- **no spec** (the code is the only record of what anyone intended),
- **no tests worth the name**,
- **three different ways to mark a task done** that have drifted apart,
- **auth bolted on twice** (an early session check and a later token middleware, both still live).

The team wants to rebuild the *core* cleanly with LDD, without losing the behaviour people quietly rely on. Three
concrete knots show up again and again across the artefacts below, and they are the spine of the whole example:

1. **The task-completion tangle.** There are three half-used code paths for "is this task done?": a `done`
   boolean, a `status` enum, and an `archivedAt` timestamp. Different parts of the app trust different ones, so
   the same task can look done in one view and open in another.
2. **A buried rule.** Somewhere in the depths, "a task auto-reopens if a blocking task reopens." It is real,
   people depend on it, and it is written down nowhere except one event handler.
3. **A security smell.** Share links have no expiry and no revocation. Anyone who ever had a link still has access.

LDD's first job is to *find* all three (harvest), then collapse the mess into the smallest correct spec (distil),
record why (journal + ADR), settle the genuinely hard fork by deliberation (court), and ship the first
milestone with a real sign-off (the 5-phase close).

---

## The guided tour: read in this order

Read the files in this sequence. Each one hands off to the next, and the whole set tells a single story.

### 1. The harvest, [`_harvest/task-model.md`](_harvest/task-model.md)
*What the old code actually meant.* This is an **intent ledger**: it harvests Tasky's task-completion logic and
the auto-reopen rule out of the legacy code, with `src/...:line` **provenance** for every claim (provenance or it
does not go in). It records the three completion mechanisms, exactly where each is trusted, the data shapes, and a
**DROP list**: the things the rebuild will deliberately leave behind, each with a reason. The harvest is where the
example discovers the completion tangle.

### 2. The reasoning, [`metacognition/0001-harvest-task-model.md`](metacognition/0001-harvest-task-model.md) then [`metacognition/0002-collapse-completion-to-one-status.md`](metacognition/0002-collapse-completion-to-one-status.md)
*Why each move was made.* Two **metacognition journal** beats. `0001` is the action beat: it ran the harvest and
records what it found. `0002` is the decision beat: it takes the harvest's finding and decides to collapse three
completion mechanisms into one ordered **status lattice**, listing the alternatives it rejected and why. This is
the heart of LDD: one entry per beat, every decision with its reason, so an agent picking the work up cold can
reconstruct the entire line of thinking.

### 3. The decision of record, [`adr/ADR-0001-one-task-status-lattice.md`](adr/ADR-0001-one-task-status-lattice.md)
*The load-bearing call, promoted so it is easy to cite.* When a journal decision is big enough that future work
will keep referring back to it, it graduates into a short **ADR**. ADR-0001 records the choice the journal made
in `0002`: replace `done` / `status` / `archivedAt` with a single ordered status, and what follows from that.

### 4. The hard fork, [`court/share-link-expiry-verdict.md`](court/share-link-expiry-verdict.md)
*The decision that needed a court, not a sentence.* Most decisions in LDD just get built. But the share-link
security smell is a genuine high-stakes fork (keep it simple vs add expiry and revocation, with real cost on both
sides), so it is settled by a **court**: three independent named seats, each with a distinct lens, each citing
the harvested code, a synthesis that ends in a *build action* (not a "we'll look at it later"), and a recorded
surviving dissent. This shows what a real LDD deliberation reads like.

### 5. The milestone close, [`M1-signoff.md`](M1-signoff.md)
*Shipping the first slice, properly.* M1 is "the task status lattice" from steps 1 to 4, built as a walking
skeleton. This is the **5-phase milestone close** (BUILD, STRUCTURE, SECURITY, VERIFY, PLAN) with a real verdict
(PASS WITH FIXES), the evidence behind it, one deferred item carried forward with its rationale, and the mandatory
next-steps plan. A milestone is not done until all five phases run and the next move is planned.

---

## The story these artefacts tell

Read in order, the thread is:

> The **harvest** found that "done" meant three contradictory things and uncovered a load-bearing auto-reopen
> rule nobody had written down. The **spec** collapsed all three into one ordered status lattice, with the
> auto-reopen rule preserved as an explicit invariant. An **ADR** recorded that choice so it can be cited later.
> A **court** settled the one fork the build could not just decide (share-link expiry), ending in a committed
> build action plus a logged dissent. Then **M1** shipped the lattice as a walking skeleton and was signed off
> through all five close phases, passing with two small fixes and one honest deferral.

That is LDD in one project: nothing dropped by accident, every decision recoverable, the hard call deliberated,
the milestone closed for real.

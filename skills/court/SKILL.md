---
name: court
description: The adversarial deliberation court - a claimant and a defendant steelman the two sides first (which doubles as the ripeness filter against over-litigation); only a surviving contest reaches a neutral bench of independent justices that ground-truths both briefs and rules; synthesise; act the same beat; dissolve. For high-stakes, hard-to-reverse forks, honest retrospectives, and pre-mortems. A challenged verdict escalates a three-tier court (Court -> Appeals Court -> Supreme Court, modelled on UK law) whose apex sets binding "spec law". Use when one perspective would rationalise, or when a decision turns on how the project's invariants were applied.
---

# The court - the adversarial deliberation court

> A **claimant** and a **defendant** steelman the two sides first - if only one survives, decide there and convene
> nothing. A surviving contest goes to a **neutral bench** of independent justices, each ground-truthing both
> briefs against the real tree and ruling; synthesise; **act the same beat**; dissolve (the ledger keeps the
> verdict). The decision-making analogue of the builder + adversarial-verifier loop. A challenged verdict
> escalates a three-tier court modelled on UK law.

> **This skill is the practice direction; the rules live in the DPR.** The authoritative *procedure* - how a case
> runs, in 12 Parts and 38 numbered rules - is the **[Development Procedure Rules, `court/DPR.md`](../../court/DPR.md)**.
> This file is only the *operating* guide: how to run a proceeding as agents. **For any rule, the DPR is
> controlling** (cited inline as "DPR Part N" / "DPR N.M"). The court also reads and writes
> **[`SPEC-LAW.md`](../../court/SPEC-LAW.md)** (apex law it writes) and **[`CASE-LAW.md`](../../court/CASE-LAW.md)**
> (the law reports), and *applies* the method floor **[`docs/invariants.md`](../../docs/invariants.md)** (the
> LDD-INV register). It applies `docs/invariants.md`; it writes `court/*`.

## When to convene (DPR Parts 1-2)

Convene **only** for a genuine high-stakes, hard-to-reverse, **contested** fork; an honest *"is this actually
working?"* retrospective; or a pre-mortem. Do **not** convene for a reversible choice (one decisive sentence), a
buildable unknown (spike it), a principal-policy or domain call (ask the principal), or a security issue (fix it
now). The court is expensive currency, spent rarely; the appeals tiers rarer still. The full triggers and the
standing test are **DPR Part 2**.

## How to run a proceeding (the practice direction)

A proceeding is **one extended fan-out** that pops out at whichever tier disposes of it (DPR Part 4). The
orchestrator runs it as parallel sub-agents:

1. **Stage 0 - the steelman (DPR Part 5).** Spawn **two** agents in parallel: a **claimant** (the strongest case
   *for* the proposition) and a **defendant** (the strongest case *against*). Brief each to ground-truth first and
   to carry, for **every load-bearing figure, the re-runnable command that produced it** (DPR 5.3). **This is the
   ripeness gate:** if a side collapses on ground-truth, build-or-kill on the survivor and convene **no bench**.
   Only a surviving two-sided contest proceeds. Caption it per DPR 4.4 (*In re <subject>*).

2. **Stage 1 - the neutral bench (DPR Part 6).** Spawn **3-5 impartial justice** agents in parallel, **no advocate
   among them**, each handed *both* briefs. Brief each to **independently ground-truth the briefs - re-running
   every figure** (a brief is an argument, not evidence; the bench is one more fallible agent, so the re-run is
   the safeguard, not its word, DPR 6.2), run **blind** to the others, and rule. Justices differ in *philosophy*
   (textualist, purposive, risk-first), never in *allegiance*.

3. **Synthesise, determine, resolve.** The orchestrator reconciles the bench, runs the **determination of genuine
   function** (DPR 6.3: prove it works by ground-truth, never ratify a hypothesis), **ends in build-or-kill the
   same beat** (DPR 6.5), and records the verdict, the determination, and the surviving dissent verbatim (DPR Part
   12, LDD-INV-16).

4. **Escalation (DPR Part 7).** A verdict stands unless **challenged with standing** (DPR 2.2). The same shape
   repeats with **fresh justice agents** each tier and the **full lower-court record** handed up, scoped: the
   **Appeals** bench re-weighs the merits, engaging the court below; the **Supreme** bench rules **only on the
   point of invariant law** and writes spec law. The same **claimant and defendant persist** across tiers (DPR
   3.1); **objectors** may be constituted at the apex only (DPR 3.3).

## The agent as petitioner (DPR 2.3, Part 11)

The driving agent is a first-class **petitioner**: it **commissions the steelman itself** (the steelman, not the
agent's appetite, decides ripeness), and with **genuine standing** it brings an appeal or refers a point of law
up of its own accord. This is **delegated, not sovereign** - the principal may halt any case - and always ends in
build-or-kill, never deferral. Two guards keep self-petitioning honest: the **steelman** at the front (no
surviving second side, no court) and the Supreme Court's power to **dismiss** a petition that is not a genuine,
universal point of law at the apex. So spec law grows by **coverage, not volume**. Full rules: DPR 2.2-2.3, 11.

## Output

- **First-instance / Appeals:** a synthesised verdict (one ledger entry) + the build actions or kills it
  triggered (commits + tasks) + the surviving dissent. Never a verdict that only defers.
- **Supreme:** a numbered, immutable precedent appended to [`SPEC-LAW.md`](../../court/SPEC-LAW.md), and the
  decided merits case reported in [`CASE-LAW.md`](../../court/CASE-LAW.md). **Deliver and record the Supreme
  judgment in full** - every justice's opinion, ruling, grounding (the invariants cited), and self-dissent,
  verbatim, never collapsed to only a synthesis (DPR 12.1, LDD-INV-16).

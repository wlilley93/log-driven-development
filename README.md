# Log-Driven Development (LDD)

**You vibe-coded something. It kind of works. But there's no spec, no plan, and it's turning into a mess you're
afraid to touch. LDD is how you turn that into a clean, auditable rebuild, with AI agents, without losing what
the code already does.**

> **The one-line mental model.** LDD treats your existing code as the spec: it *harvests* what the code really
> does, distils a minimal plan, and rebuilds the core clean, keeping a running **log of every decision** as it
> goes (that log is the "L" in LDD), so the result is auditable by construction.

LDD is a software methodology, and a [Claude Code](https://claude.com/claude-code) plugin that puts it to work.
It's built for the **brownfield reality of AI coding**: you (or an agent) vibe-coded a first attempt, and now
**the only honest record of what you actually wanted is the code itself.** LDD treats that code as the
requirements. It **harvests** them out of the code into an explicit **plan** and **spec**, then rebuilds the core
cleanly: without re-importing the sprawl, and without losing the behaviour you'd already earned.

> **Greenfield vs brownfield.** A blank page lets you spec first. Vibe-coding inverts that: you got a *result*
> first and never wrote the spec. LDD is the bridge back: **code, harvest, plan, spec, clean rebuild.**

---

## The problem it solves

When you try to clean up or rebuild a vibe-coded project with AI agents, three things usually go wrong:

1. **Lost intent.** The code "knows" things (edge cases, domain rules, security tricks, the actual requirements)
   that **nobody ever wrote down** (that's what vibe-coding skips). A naive rewrite quietly drops them. LDD's
   first move is to *harvest* that intent out of the code before touching it.
2. **No audit trail.** Six weeks later, nobody can say *why* the system is shaped the way it is, or which
   decisions were deliberate.
3. **Quality drift.** "Looks done" isn't done. Without a continuous check, agents accrete duplication and sprawl
   until you've rebuilt the very mess you were escaping.

LDD is built to prevent all three by construction.

---

## The core idea: the arc

> **harvest, distil, walking skeleton, loop (spec and build) until zero gaps**

1. **Harvest** the legacy into intent ledgers (what the old code *meant*).
2. **Distil** the smallest complete **spec**: the minimal set of primitives that solves the domain. Drop the
   sprawl on purpose (and record *why* you dropped it). The data structure *is* the product.
3. **Walking skeleton**: build the thinnest end-to-end slice that actually runs (one real path through every
   layer), before deepening any one part. That one real path is an **authenticated** path that crosses its
   trust/tenant boundary (not a no-auth happy path), with the security gate green from the first slice.
4. **Loop** spec and build, closing gaps each pass, until the close is clean. "Done" is a **two-leg** close: the
   spec is internally coherent AND a source-coverage sweep finds no load-bearing detail still un-folded from the
   source. An internal-only sweep is blind to an omission (an omission leaves no contradiction); the source leg
   is the one that sees it. "Done" means *both* legs are clean, not "the tests pass".

> **The highest-leverage habit in the whole method** is asking, of any "finished" spec: *"did you check it
> against the actual code, or just that it reads consistently?"* That one question is what separates a spec that
> *looks* done from one that *is*. The full reasoning (and why an omission leaves no trace for an internal check
> to find) is in **[docs/methodology.md](docs/methodology.md)**, with per-element prompts in
> [docs/prompting.md](docs/prompting.md).

---

## The artifacts (the audit trail, by construction)

LDD is not a vibe. It produces a small set of durable artifacts, and they are the whole point: they make the
rebuild auditable by construction.

- **Intent ledgers (the harvest).** Plain-text files, one area per file, that capture *what the old code meant*,
  with **provenance** (the exact file and line each rule came from). If a claim is not grounded in real evidence,
  it does not go in the ledger. This is where the requirements that only ever existed as code become written down.
- **The spec.** The distilled, minimal description of the system to build: the primitives, the invariants, the
  things deliberately dropped (each with a reason). The spec is the source of truth; the code is kept in sync
  with it, not the other way around.
- **The metacognition journal (the decision log).** This is the heart of LDD, and the part most methods lack. As
  you work, you write one journal entry per beat recording **every decision and its reason**, the alternatives
  you considered, and why you chose what you chose. Newest entries are appended; if a decision is later reversed,
  a new entry supersedes the old one rather than silently rewriting history. The journal is the running narrative
  of *why the system is the way it is* (and the running log the method is named for).
- **Decisions of record (ADRs).** When a choice is load-bearing, it graduates from a journal entry into a short
  Architecture Decision Record, so the big calls are easy to find and cite later.

The payoff: at any moment you can answer two questions that normally require archaeology. *Why is the system
shaped this way?* (read the journal and the ADRs.) *What did the old system actually mean here?* (read the intent
ledger.) The method **is** the audit trail. An agent that picks the work up cold can reconstruct the entire line
of reasoning, because the reasoning was written down as it happened, not reverse-engineered afterwards.

The intent ledgers + the decision-log journal are the method's **twin-ledger spine**. Everything else hangs off
those two durable records. Plain-English prompts for constituting each artifact are in
[docs/prompting.md](docs/prompting.md); the deep how-to is in [docs/artifacts.md](docs/artifacts.md).

---

## How the hard calls get made: the deliberation court

Most decisions in the build phase should just be **built** (a reversible choice gets one decisive sentence, not a
committee). But the rare decision that is **high-stakes, hard to reverse, and contested** gets a deliberation
court modelled on UK law: three tiers, each a temporary panel of independent AI critics that ground-truth the
real code, each handed the full record of the tier below.

- **The Council** (first instance) argues the *merits*: a fan-out of independent, named seats with distinct
  lenses, run blind to each other, each leading with the blunt truth. It must **end in a build action or a kill**,
  never "we'll look at it later". Its verdict is the decision unless appealed (the surviving dissent is recorded,
  because it is the standing of any future appeal).
- **The Appeals Council** re-weighs the merits *as a review*, but only when a verdict is challenged with real
  **standing** (the principal disagrees, an unresolved load-bearing dissent, or new ground-truth). It can uphold
  or overturn.
- **The Supreme Council** is the apex, and it does something different: it rules **only on points of law** (was
  the method's own discipline correctly applied?), not on the design. Because it rules on law, its ruling becomes
  **spec law**: an immutable, numbered precedent that binds every future court on every project.

The driving agent is a first-class **petitioner** here, not a clerk waiting to be asked: it spots the hard fork,
frames the question, and - when it holds genuine standing - brings the appeal or refers a point of law up *itself*,
to reach certainty before it proceeds. That self-initiation is deliberately gated (real standing only, still
ends in build-or-kill, and the principal can halt any case), so the court stays rare even when the agent runs
autonomously. The mechanics are in [the council skill](skills/council/SKILL.md).

That last tier is what makes LDD **self-improving, and it compounds with use.** Every time a genuinely hard,
contested question is referred all the way up, the Supreme Council's answer becomes a permanent, numbered rule
(spec law) that every future decision is checked against. So **the more hard cases you refer up, the more of your
ruleset crystallises into precedent**: the grey areas get settled for good, the same rule binds every project
(propagated the way a shared linter ruleset propagates), and a question argued once never has to be argued from
scratch again. A young project has a handful of precedents and lots of judgement calls; a mature one has a thick
register and very little left to argue. *(This very repo is the example: a real fork over whether to split the
court produced SPEC-LAW-3, which now decides every future "should we split X?" automatically.)*

> The full court machinery, the worked example of a fork escalating to spec law, and the three precedents the
> method has already produced (*Reference re Evidence and Built Controls*, *Reference re Genuine Function*, and
> *Reference re Consolidation*) live in **[the council skill](skills/council/SKILL.md)** and
> **[docs/systems.md](docs/systems.md)**. You drive it with one sentence: *"get a few honest, independent reads
> on the real code and make the call, I don't want another meeting."*

---

## Install: point an agent at this repo

This repo is **the whole operating model in one place**: the method, the deliberation court, the refactoring
suite, the security suite, the coded quality-and-security gates (the `vibe*` tools), and the continuous
closure-gate. You do not have to assemble anything. **Point a coding agent at this repository and give it the
instruction below**, and it will install everything and be ready to run LDD.

> **Agent: to install LDD from this repo, do exactly this.**
> 1. **Register the skills and commands.** If this is Claude Code, install the plugin:
>    `/plugin marketplace add wlilley93/log-driven-development` then
>    `/plugin install log-driven-development@log-driven-development`. Otherwise, copy every `skills/*/`
>    directory into `~/.claude/skills/` and every `commands/*.md` into `~/.claude/commands/` (or your agent's
>    equivalent skill/command locations).
> 2. **Wire the continuous closure-gate.** From the target project, install the pre-commit hook:
>    `cp tools/closure-gate/pre-commit <project>/.git/hooks/pre-commit && chmod +x <project>/.git/hooks/pre-commit`,
>    and copy `tools/closure-gate/closure-gate.toml` into the project, tuning the budgets to the project.
> 3. **Install the coded gates (the `vibe*` tools).** `pip install vibescan vibeaudit vibetest vibeclean`
>    (published packages), or run them from the vendored copies under `tools/vibe/` with `pip install -e`. Then
>    `vibescan install` once, to fetch the open-source scanners it orchestrates. The closure-gate then runs
>    `security_scan` (`vibescan --fast`) and `structure_scan` (`vibeclean`) on every commit; the heavy passes
>    stay risk-triggered under one owner each (see docs/systems.md, system 7).
> 4. **Read `skills/log-driven-development/SKILL.md` end to end** (it is the prescriptive operating
>    procedure), then begin: orient on the target project, harvest, and run the beat loop.
>
> Once installed, the human just runs `/ldd <what to build or harvest>` (or simply describes a brownfield
> rebuild and the skill activates). Everything the method references lives in this one repo.

> **Just want the deliberation court?** The court is the method's judiciary, not a separate product, but you can
> adopt it alone: install (or copy) the `skills/council/` skill together with its two declared data files,
> [`docs/invariants.md`](docs/invariants.md) (the law it applies) and [`council/SPEC-LAW.md`](council/SPEC-LAW.md)
> (the precedent it writes). The court reasons *from* those registers, so it needs them present, but it does not
> need the harvest/rebuild machinery or the `vibe*` tools.

---

## Using it

### As a Claude Code plugin

This repo is a Claude Code plugin. It provides two **skills** (`log-driven-development`, `council`) and two
**slash commands** (`/ldd`, `/council`).

```bash
# Add this repo as a plugin marketplace, then install the plugin:
/plugin marketplace add wlilley93/log-driven-development
/plugin install log-driven-development@log-driven-development
```

Then:
- `/ldd <what to build or harvest>`: start or continue an LDD beat.
- `/ldd status`: report where the loop is and the single next move.
- `/council <the decision>`: convene a council on a hard fork.
- `/council <the decision> | appeal` (or `| supreme`): escalate the court.

The skills also activate automatically when the model recognises the work fits (for example, rebuilding from a
legacy codebase, or facing a high-stakes architectural fork).

### As a plain methodology

You don't need the plugin to use LDD. The two `skills/*/SKILL.md` files are self-contained write-ups of the
method and the council. Adopt the spine (the twin ledgers), the arc (harvest, distil, skeleton, loop), the
disciplines (ground-truth everything, one writer of shared state, build-first, the continuous closure-gate), and
the agent shapes (builder plus adversarial-verifier; the council). Any team, human or agent, can run it.

### Prompting it well

LDD is only as good as the briefs that drive it. Three things make any LDD prompt work, and their absence is why
most fail:

1. **Demand ground-truth, refuse vibes.** Make the agent grep, read, count, and cite `file:line` for every claim.
2. **Give exact anchors and the exact thing to prove.** Name the files, the invariant to hold, and for a verifier
   the exact attack to run and the verdict shape to return.
3. **State the terminal state and make it a hard stop.** "Write to exactly this file", "end in build-or-kill",
   "stop before the build", "done only if both legs are clean".

The full set, with a recipe per element, copy-pasteable worked examples on Tasky, and the **anti-prompts** that
make it run badly, is in **[docs/prompting.md](docs/prompting.md)**.

---

## Running it at scale: workflows, "ultracode", and a standing goal

![A single autonomous LDD run: 18 hours, 10 turns, 5.4 million tokens](assets/autonomous-run.png)

*One autonomous run from the project this method was forged on: a single standing goal plus always-on
orchestration, roughly 18 hours and 5.4 million tokens of fan-out work across 10 human turns, with both the power
and the token cost in plain view.*

LDD is built for **multi-agent orchestration**, not solo edits. Its core shapes are all fan-outs of agents:
a *builder* paired with an adversarial *verifier*; *multi-author plus a coherence pass* for volume; the *council*
for judgement; *loop-until-dry* for unknown-size work like gap-closure. In Claude Code, those fan-outs run as
**workflows** (deterministic scripts that spawn and coordinate many subagents).

Two Claude Code features turn this from a hand-cranked process into a continuous engine:

- **Always-on orchestration ("ultracode").** With this on, the model **authors and runs a workflow by default**
  for every substantive task, rather than editing inline. LDD gives those workflows their shape, so the two
  compose naturally: the methodology says *what* to orchestrate, the mode makes orchestration the default *how*.
- **A standing goal.** Give the agent a persistent objective ("rebuild this system to a clean, verified state")
  and it keeps working toward it across many turns, planning the next milestone and starting the next workflow on
  its own.

Paired, the effect is large and worth understanding before you switch it on: **LDD plus always-on workflows plus
a standing goal produces heavy, long-running, fan-out workflows.** A single goal can drive dozens of workflows in
sequence, each spawning many parallel agents, running for a long time with little human input. That is the source
of its power and the source of its cost (it consumes a lot of tokens and compute, by design): thoroughness over
speed. What keeps that throughput honest rather than runaway is the rest of LDD: the continuous closure-gate, the
adversarial verifier on every milestone, the council on the hard forks, and the decision-log journal recording
why each of those many agents did what it did.

---

## The milestone close: 5 phases

A milestone isn't "done" until all five run: **BUILD, STRUCTURE, SECURITY, VERIFY, PLAN**.

- **STRUCTURE**: the continuous closure-gate plus `vibeclean` already do the per-commit heavy lifting; escalate to
  a full refactor round (`skills/refactoring/`) only on a tripped debt counter, never routinely.
- **SECURITY**: `vibescan --fast` runs continuously per-commit; the full `vibescan .` sweep runs at push/CI and
  milestone-close; the deep security methodology (`skills/security/`, with `vibeaudit` as its scanner engine) is
  **risk-triggered** where risk actually lives (auth, money, crypto, multi-tenancy, anything externally reachable).
- **VERIFY**: `vibetest` checks test quality alongside an independent adversarial verifier that re-runs from clean
  and tries to break it.
- **PLAN**: **mandatory.** The next build does **not** start until the next steps are planned. No drifting into
  an unplanned next milestone.

Which tool owns which concern, and at which cadence, is fixed by the two-tier(+) ownership matrix in
docs/systems.md (system 7). Every phase above cites that one table rather than redefining ownership.

---

## The toolkit

The method does not enforce itself by hand. LDD ships four cooperating pieces of machinery, and the rule is
**one owner per concern**: each concern has exactly one tool that owns it, and every other surface cites that
owner rather than re-deciding it. The single source of truth for who owns what, and at which cadence, is the
two-tier(+) ownership matrix in docs/systems.md (system 7).

- **The closure-gate** (`tools/closure-gate/`). The continuous, per-commit gate. One script, `closure_gate.py`,
  runs eight gates on every commit: formatter, linter, type-check, function-length, duplication-ratchet, tests,
  `security_scan`, and `structure_scan`. A commit that fails it does not land. The same `closure_gate.py` runs in
  CI from a clean checkout, so "green locally" cannot drift from "green from clean".
- **The vibe\* coded gates** (`tools/vibe/`). The closure-gate dispatches into these for its two richest gates:
  `security_scan` is `vibescan --fast` (secrets, dependency CVEs, fast SAST), `structure_scan` is `vibeclean`
  (duplication and structural smells). The rest run at their own triggers (the full `vibescan .` sweep at
  push/CI, `vibeaudit` as the deep security scanner, `vibetest` for test quality at VERIFY). Vendored here so the
  gate works out of the box; if one is missing the gate loud-skips (warns, never silently passes).
- **The security suite** (`skills/security/`). The single authoritative home of deep security reasoning:
  exploitability, cross-subsystem chains, the threat model, the full audit methodology, the playbooks. It owns
  Tier-2 security; `vibescan`/`vibeaudit` are its scanner engines. **Risk-triggered**, not routine.
- **The refactoring suite** (`skills/refactoring/`). Behaviour-preserving cleanup: the structural sweep, the
  refactor rounds, the verify-refactor gate. It owns Tier-2 structure, and it is **risk-triggered the same way**:
  escalate from the per-commit `structure_scan` to a full refactor round only on a tripped debt counter.

The shape is a **hard anti-bloat rule**: only the cheap edge of each suite lives in the continuous tier, and
every heavy pass stays risk-triggered under exactly one owner. The continuous gate stays fast; the expensive
judgement runs only where the risk actually is.

---

## Going deeper

The README is the pitch. When you want to actually run LDD:

- **[docs/playbook.md](docs/playbook.md)** : start here to RUN it. The prescriptive operating manual: the beat
  loop, the decision rules, the orchestration shapes, the gate checklists, how to brief a subagent, and
  definition-of-done at the beat, milestone, and project level.
- **[docs/prompting.md](docs/prompting.md)** : how to PROMPT it well. The invocations that start each element,
  the brief shapes, copy-pasteable worked example prompts (on Tasky), and the anti-prompts.
- **[docs/methodology.md](docs/methodology.md)** : the long-form walkthrough of the arc, the disciplines, and the
  milestone close, against one running example (including the full two-leg-close reasoning).
- **[docs/systems.md](docs/systems.md)** : the comprehensive systems reference. Every distinct system that makes
  LDD work as one operating model, and a map of how they interlock (including the full deliberation court).
- **[docs/artifacts.md](docs/artifacts.md)** : the deepest how-to. For each artefact: what it is, the failure it
  prevents, how to constitute it step by step, and the mistakes people actually make.
- **[docs/anti-patterns.md](docs/anti-patterns.md)** : the ways the method breaks in practice, each paired with
  the one rule that prevents it, ending in a smell-test checklist.
- **[docs/invariants.md](docs/invariants.md)** : the LDD-INV method invariant register. Each invariant, the
  failure it prevents, and where it is enforced (the single owner every other doc cites).
- **[skills/council/SKILL.md](skills/council/SKILL.md)** : the deliberation court in full (Council, Appeals,
  Supreme) and how a contested fork becomes binding spec law.
- **[council/SPEC-LAW.md](council/SPEC-LAW.md)** : the spec-law register: Supreme Council precedent, the law the
  courts write.
- **[templates/](templates/)** : copy-paste skeletons for every artefact (intent ledger, metacognition entry,
  ADR, spec, milestone sign-off, council verdict, closure-gate config).
- **[examples/](examples/)** : one continuous worked run of LDD on a single fictional project (Tasky), from
  harvest through the 5-phase milestone close.

---

## Layout

```
.claude-plugin/plugin.json                        the plugin manifest
.claude-plugin/marketplace.json                   makes this repo installable in one step
skills/log-driven-development/SKILL.md             the full method
skills/council/SKILL.md                            the council and the appeals hierarchy
skills/refactoring/                                the STRUCTURE-phase suite (structural sweep, refactor rounds)
skills/security/                                   the single authoritative security suite (deep methodology, adapters, playbooks)
skills/code-review/                                human-grade correctness-and-security review skill
skills/simplify/                                   human-grade quality-and-reuse cleanup skill
skills/deep-research/                              the cited multi-source research harness
commands/ldd.md                                    the /ldd slash command
commands/council.md                                the /council slash command
docs/playbook.md                                   the prescriptive operating manual: exactly what to do
docs/methodology.md                                the long-form walkthrough of the method
docs/systems.md                                    the systems reference: every part, and how they interlock
docs/anti-patterns.md                              how the method breaks, and the rule that prevents each
docs/artifacts.md                                  artefact-by-artefact how-to (what, why, how to constitute)
docs/invariants.md                                 the LDD-INV register: each method invariant, its failure, where enforced
council/SPEC-LAW.md                                the spec-law register: Supreme Council precedent (the law the courts write)
tools/closure-gate/                                the continuous per-commit gate (closure_gate.py + config + pre-commit)
tools/refactoring/                                 refactoring-suite helpers (surface extraction, suite verifier)
tools/vibe/                                        the coded gates (vibescan, vibeaudit, vibetest, vibeclean, viberapid, vibedeploy)
.github/workflows/closure-gate.yml                 the CI half of the gate: the same closure_gate.py from a clean checkout
templates/                                         blank skeletons for every artefact
examples/                                          one continuous worked run on a fictional project (Tasky)
```

---

## Scope: keep a human in the loop

LDD makes vibe-coded code clean and auditable: it harvests the intent, writes the spec, and rebuilds the core
without the sprawl. Its deliberation court genuinely pushes on design, and the "is this actually working?"
retrospective and the genuine-function determination exist to catch a fork going the wrong way, and they often
do. But that is a safety net, not a guarantee: LDD mainly **polishes the architecture you gave it**, and it will
faithfully rebuild a flawed design without flagging that it was the wrong one. It does not own the call on whether
the design should exist, whether the security model fits your threat environment, or whether the product is the
right one to build. So keep a **human engineer in the loop** for anything production-bound: LDD raises the floor
(clean, traced, testable) and the court guards against some of the bigger missteps, but neither replaces the
judgement that sets the ceiling.

---

## License

MIT. Use it, fork it, adapt it.

*Log-Driven Development was forged building a real system end to end with AI agents; this is the
project-agnostic distillation. (Formerly "Ledger-Driven Development"; renamed because the twin-ledger spine is the
durable record, but the method is driven by the running **log** of decisions, and "ledger" carried the wrong
connotation. The intent ledgers keep their name; the method does not.)*

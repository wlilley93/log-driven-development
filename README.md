# Ledger-Driven Development (LDD)

**You vibe-coded something. It kind of works. But there's no spec, no plan, and it's turning into a mess you're
afraid to touch. LDD is how you turn that into a clean, auditable rebuild, with AI agents, without losing what
the code already does.**

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
   layer), before deepening any one part.
4. **Loop** spec and build, closing gaps each pass, until the automated sweep is clean. "Done" means the sweep is
   clean, not "the tests pass".

---

## The artifacts (and why metacognition matters)

LDD is not a vibe. It produces a small set of durable artifacts, and they are the whole point: they make the
rebuild auditable by construction.

- **Intent ledgers (the harvest).** Plain-text files, one area per file, that capture *what the old code meant*,
  with **provenance** (the exact file and line each rule came from). If a claim is not grounded in real evidence,
  it does not go in the ledger. This is where the requirements that only ever existed as code become written down.
- **The spec.** The distilled, minimal description of the system to build: the primitives, the invariants, the
  things deliberately dropped (each with a reason). The spec is the source of truth; the code is kept in sync
  with it, not the other way around.
- **The metacognition journal.** This is the heart of LDD, and the part most methods lack. Metacognition means
  *thinking about your own thinking*: as you work, you write one journal entry per beat recording **every
  decision and its reason**, the alternatives you considered, and why you chose what you chose. Newest entries
  are appended; if a decision is later reversed, a new entry supersedes the old one rather than silently
  rewriting history. The journal is the running narrative of *why the system is the way it is*.
- **Decisions of record (ADRs).** When a choice is load-bearing, it graduates from a journal entry into a short
  Architecture Decision Record, so the big calls are easy to find and cite later.

The payoff: at any moment you can answer two questions that normally require archaeology. *Why is the system
shaped this way?* (read the journal and the ADRs.) *What did the old system actually mean here?* (read the intent
ledger.) The method **is** the audit trail. An agent that picks the work up cold can reconstruct the entire line
of reasoning, because the reasoning was written down as it happened, not reverse-engineered afterwards.

---

## How decisions get made: the deliberation court

Most decisions in the build phase should just be **built** (a reversible choice gets one decisive sentence, not a
committee). But some calls are high-stakes and hard to reverse, and for those LDD runs a deliberation court
modelled on UK law: three tiers, each one a temporary panel of independent AI critics, each handed the full
record of the tier below. A higher court that ignores the record beneath it is improperly constituted.

### The Council (first instance)

The Council is convened for a genuine **high-stakes, hard-to-reverse fork** (an architecture choice, build vs
consume, sequencing a whole program), or for an honest *"is this actually working?"* retrospective or pre-mortem.

It is a single fan-out of a handful of **independent, named seats**, each given a **distinct lens** (project
health, process critic, devil's advocate, a security or cost or UX lens, the advocate of a named alternative).
Each seat must **ground-truth against the real code first** (greps, file reads, counts, test runs); a seat that
cannot cite evidence is ignored. The seats run independently and do not see each other while running, so they
cannot converge into groupthink. Each one leads with the blunt, uncomfortable truth, not a hedge.

The Council is **ephemeral**: the seats exist only for the question, then dissolve. Nothing persists but the
verdict in the ledger and the **surviving dissent** (recorded, never buried, because it is the standing of any
future appeal). The non-negotiable discipline: a Council **must end in a build action or a kill**, never in "we
will look at it later". Its verdict **is the decision** unless someone appeals it.

### The Appeals Council

A Council can be wrong. The Appeals Council is convened when a verdict is **challenged with standing**: the
principal disagrees, a load-bearing dissent was left unresolved, or new ground-truth contradicts a point the
Council relied on. "I would have designed it differently" is not standing; a real basis is.

It re-weighs the **merits** (still the question of *what the right design is*), but as a *review*: fresh
independent seats who must **engage the Council's actual reasoning**, not re-argue blind. It is handed the
Council's full record (every seat's verdict, the synthesis, the dissent, the inputs and outputs). It can
**uphold or overturn**. Its decision stands unless taken to the Supreme Council.

### The Supreme Council

The Supreme Council is the apex, convened rarely: when the Appeals Council is itself challenged, or when the
question is of the highest *invariant* significance. It does something different from the two courts below it.

It does **not** re-litigate the design. It hears **only points of law**: *was the invariant spec and the LDD
discipline correctly applied in reaching this decision?* (Were the invariants honoured? Was the process sound,
the ground-truthing real, the one-writer rule kept?) This is exactly the role of a real Supreme Court, which
hears points of *law*, not points of *fact*.

Because it rules on law rather than taste, its ruling can stand as **precedent**. A Supreme Council ruling
becomes **spec law**: an immutable, numbered entry in a precedent register that **binds every future court**. A
first-instance Council cannot overturn spec law, and a decision that collides with a precedent is refused at the
spec layer the same way a trust boundary refuses an unknown command. Only a later Supreme Council, expressly
narrowing the precedent on a point of law, can refine it. The court hierarchy itself is constitutional: it is the
framework within which spec law is made, and it gives the rare contested decision a principled, bounded path to a
final answer, without a standing committee that accretes politics.

---

## Running it at scale: workflows, "ultracode", and a standing goal

LDD is built for **multi-agent orchestration**, not solo edits. Its core shapes are all fan-outs of agents:
a *builder* paired with an adversarial *verifier*; *multi-author plus a coherence pass* for volume; the *council*
for judgement; *loop-until-dry* for unknown-size work like gap-closure. In Claude Code, those fan-outs run as
**workflows** (deterministic scripts that spawn and coordinate many subagents).

Two Claude Code features turn this from a hand-cranked process into a continuous engine:

- **Always-on orchestration ("ultracode").** With this on, the model **authors and runs a workflow by default**
  for every substantive task, rather than editing inline. LDD gives those workflows their shape (harvest fan-out,
  builder plus verifier, the council), so the two compose naturally: the methodology says *what* to orchestrate,
  the mode makes orchestration the default *how*.
- **A standing goal.** Give the agent a persistent objective ("rebuild this system to a clean, verified state")
  and it keeps working toward it across many turns, planning the next milestone and starting the next workflow on
  its own.

Paired, the effect is large and worth understanding before you switch it on: **LDD plus always-on workflows plus
a standing goal produces heavy, long-running, fan-out workflows.** A single goal can drive dozens of workflows in
sequence, each spawning many parallel agents (harvesters, builders, verifiers, whole councils), running for a
long time with little human input. That is the source of its power (it can build and adversarially verify a large
system largely autonomously) and the source of its cost (it consumes a lot of tokens and compute, by design). The
trade is deliberate: thoroughness over speed. What keeps that throughput honest rather than runaway is the rest of
LDD: the continuous closure-gate, the adversarial verifier on every milestone, the council on the hard forks, and
the metacognition journal recording why each of those many agents did what it did.

---

## The milestone close: 5 phases

A milestone isn't "done" until all five run:

**BUILD, STRUCTURE, SECURITY, VERIFY, PLAN**

- **STRUCTURE**: a quick structural scan; escalate to a full refactor only if it flags real debt (the continuous
  closure-gate already does the heavy lifting).
- **SECURITY**: cheap supply-chain checks every time; the deep security audit is **risk-targeted** (run it where
  risk actually lives: auth, money, crypto, multi-tenancy, anything externally reachable).
- **VERIFY**: an independent adversarial verifier re-runs from clean and tries to break it.
- **PLAN**: **mandatory.** The next build does **not** start until the next steps are planned. No drifting into
  an unplanned next milestone.

---

## Using it

### As a Claude Code plugin

This repo is a Claude Code plugin. It provides two **skills** (`ledger-driven-development`, `council`) and two
**slash commands** (`/ldd`, `/council`).

```bash
# Add this repo as a plugin marketplace, then install the plugin:
/plugin marketplace add wlilley93/ledger-driven-development
/plugin install ledger-driven-development@ledger-driven-development
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
method and the council. Adopt the spine (two ledgers), the arc (harvest, distil, skeleton, loop), the disciplines
(ground-truth everything, one writer of shared state, build-first, the continuous closure-gate), and the agent
shapes (builder plus adversarial-verifier; the council). Any team, human or agent, can run it.

---

## Going deeper

The README is the pitch. When you want to actually run LDD, read these in order:

- **[docs/methodology.md](docs/methodology.md)** : the long-form walkthrough of the arc (harvest, distil, walking
  skeleton, loop), the disciplines, and the milestone close, against one running example.
- **[docs/systems.md](docs/systems.md)** : the comprehensive systems reference. Every distinct system that makes
  LDD work as one operating model (the twin-ledger spine, the agent shapes, the deliberation court, the
  closure-gate, the milestone close, the disciplines, the ultracode posture) and a map of how they interlock into
  one machine.
- **[docs/artifacts.md](docs/artifacts.md)** : the deepest how-to. For each artefact: what it is, the failure it
  prevents, how to constitute it step by step, and the mistakes people actually make.
- **[templates/](templates/)** : copy-paste skeletons for every artefact (intent ledger, metacognition entry,
  ADR, spec, milestone sign-off, council verdict, closure-gate config).
- **[examples/](examples/)** : one continuous worked run of LDD on a single fictional project (Tasky), from
  harvest through the 5-phase milestone close, so every artefact cross-references into one real picture.

---

## Layout

```
.claude-plugin/plugin.json                        the plugin manifest
.claude-plugin/marketplace.json                   makes this repo installable in one step
skills/ledger-driven-development/SKILL.md          the full method
skills/council/SKILL.md                            the council and the appeals hierarchy
commands/ldd.md                                    the /ldd slash command
commands/council.md                                the /council slash command
docs/methodology.md                                the long-form walkthrough of the method
docs/systems.md                                    the systems reference: every part, and how they interlock
docs/artifacts.md                                  artefact-by-artefact how-to (what, why, how to constitute)
templates/                                         blank skeletons for every artefact
examples/                                          one continuous worked run on a fictional project (Tasky)
```

---

## License

MIT. Use it, fork it, adapt it.

*Ledger-Driven Development was forged building a real system end to end with AI agents; this is the
project-agnostic distillation.*

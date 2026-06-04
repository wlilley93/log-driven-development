# Log-Driven Development (LDD)

**You vibe-coded something. It kind of works. But there's no spec, no plan, and it's turning into a mess you're
afraid to touch. LDD turns that into a clean, auditable rebuild, with AI agents, without losing what the code
already does.**

> **The one-line mental model.** LDD treats your existing code as the spec: it *harvests* what the code really
> does, distils a minimal plan, and rebuilds the core clean, keeping a running **log of every decision** as it
> goes (that log is the "L" in LDD), so the result is auditable by construction.

---

## Quickstart (the 60-second version)

```bash
# 1. Install the plugin (Claude Code)
/plugin marketplace add wlilley93/log-driven-development
/plugin install log-driven-development@log-driven-development

# 2. Point it at your mess
/ldd clean up and rebuild this project
```

That's it. LDD harvests what your code actually does, writes the spec, and rebuilds it clean, one auditable
**beat** at a time (each beat ends in a commit plus a one-line journal entry saying *why*).

Everything else on this page is **optional power tooling** you can ignore until you need it: a continuous
quality gate, a refactoring/security suite, and a rare **deliberation court** for the hard, contested calls. If
you only ever use the harvest-spec-rebuild loop, you are using LDD correctly.

---

## The problem it solves

When you rebuild a vibe-coded project with AI agents, three things usually go wrong. LDD prevents all three by
construction:

1. **Lost intent.** The code "knows" things (edge cases, domain rules, security tricks) that **nobody wrote
   down**. A naive rewrite drops them. LDD *harvests* that intent out of the code first.
2. **No audit trail.** Six weeks later nobody can say *why* the system is shaped the way it is. LDD records every
   decision as it happens.
3. **Quality drift.** "Looks done" isn't done. Agents accrete duplication until you've rebuilt the mess you were
   escaping. LDD's "done" is a checked sweep, not a vibe.

---

## How it works: the arc

> **harvest, distil, walking skeleton, loop until zero gaps**

1. **Harvest** the legacy into **intent ledgers**: plain-text files capturing what the old code *meant*, with
   **provenance** (the exact `file:line` each rule came from). No evidence, no entry.
2. **Distil** the smallest complete **spec**: the minimal primitives that solve the domain. Drop the sprawl on
   purpose, and record *why*.
3. **Walking skeleton**: build the thinnest end-to-end slice that actually runs (one real, authenticated path
   through every layer) before deepening any part.
4. **Loop** spec and build until the close is clean. "Done" is a **two-leg** close: the spec is internally
   coherent **and** a source-coverage sweep finds no load-bearing detail still un-folded from the code.

> **The single highest-leverage habit** is asking, of any "finished" spec: *"did you check it against the actual
> code, or just that it reads consistently?"* An internal-coherence check is structurally blind to an omission
> (an omission leaves no contradiction); only the source-coverage leg sees it. That one question is the whole
> "done" gate. Full reasoning in [docs/methodology.md](docs/methodology.md).

---

## The artifacts (the audit trail, by construction)

LDD produces a small set of durable artifacts. They *are* the point: they make the rebuild auditable for free.

- **Intent ledgers** (`_harvest/`): what the old code meant, with `file:line` provenance.
- **The spec**: the distilled source of truth; the code is kept in sync with it, not the reverse.
- **The metacognition journal**: one entry per beat recording **every decision and its reason**. Append-only; a
  reversal supersedes, never rewrites. This is the running **log** the method is named for.
- **ADRs**: load-bearing decisions graduate from a journal entry into a short, findable record.

These let you answer, at any moment, the two questions that normally require archaeology: *why is it shaped this
way?* (journal + ADRs) and *what did the old system actually mean here?* (intent ledger). The intent ledgers plus
the journal are the **twin-ledger spine**; everything else hangs off them. Per-artifact how-to in
[docs/artifacts.md](docs/artifacts.md); plain-English prompts in [docs/prompting.md](docs/prompting.md).

---

## The continuous quality gate

The method doesn't enforce itself by hand. A **closure-gate** runs on every commit (formatter, linter,
type-check, function-length, a duplication ratchet, tests, plus a security and a structure scan) so a commit that
regresses quality does not land, and the same gate runs in CI from a clean checkout so "green locally" can't drift
from "green from clean". The heavy passes (the full security methodology in `skills/security/`, a full refactor
round in `skills/refactoring/`) are **risk-triggered**, never routine. Setup and the per-gate ownership matrix are
in [docs/systems.md](docs/systems.md). *(The coded scanners under `tools/vibe/` are optional; the gate degrades
loudly, never silently, when one is absent.)*

---

## The rare hard call: the deliberation court

Most decisions just get **built**, a reversible choice gets one decisive sentence, not a committee. For the rare
fork that is **high-stakes, hard to reverse, and genuinely contested**, LDD has a deliberation court: a
**claimant** and a **defendant** each build the strongest case (which doubles as a filter, if only one side
survives, you decide there and convene nobody), and a **neutral bench** of independent AI critics ground-truths
both briefs and rules, ending in build-or-kill. A challenged ruling can escalate, and a settled point of law
becomes reusable precedent.

You will not touch this in your first week, and that is by design. The full machinery, when you do need it, is in
[the court skill](skills/court/SKILL.md), driven by one sentence: *"get a few honest, independent reads on the
real code and make the call."*

---

## Advanced: running it autonomously (the "ultracode" case)

LDD is also built to run as a continuous, multi-agent engine, not just solo edits. Its shapes are fan-outs:
*builder + adversarial verifier*; *multi-author + a coherence pass*; the *court* for judgement;
*loop-until-dry* for gap-closure. With always-on workflow orchestration plus a standing goal ("rebuild this to a
clean, verified state"), one goal can drive **many** long-running workflows with little human input.

That is the source of its power **and** its cost: a single autonomous run can be heavy (hours, millions of
tokens). It buys thoroughness over speed. This is the agent-fleet tier; the Quickstart above is the solo-human
tier. They are the same method at two very different scales, pick the one that fits.

---

## Going deeper

The README is the pitch. To actually run it:

- **[docs/playbook.md](docs/playbook.md)** : the prescriptive operating manual (the beat loop, decision rules,
  gate checklists, definition-of-done).
- **[docs/prompting.md](docs/prompting.md)** : how to prompt it well, with copy-pasteable worked examples and the
  anti-prompts that make it run badly.
- **[docs/methodology.md](docs/methodology.md)** : the long-form walkthrough of the arc and the disciplines.
- **[docs/systems.md](docs/systems.md)** : the systems reference, every part and how they interlock.
- **[docs/invariants.md](docs/invariants.md)** : the LDD-INV register, each method invariant, the failure it
  prevents, and where it is enforced.
- **[skills/log-driven-development/SKILL.md](skills/log-driven-development/SKILL.md)** : the method, end to end.
- **[skills/court/SKILL.md](skills/court/SKILL.md)** + **[court/](court/)** : the deliberation court and its
  registers (procedure, precedent, case law).
- **[templates/](templates/)** and **[examples/](examples/)** : skeletons for every artefact, and an illustrative
  worked run.

**What ships:** the plugin's front door is `/ldd` (the method) and `/court` (the rare hard call). It also bundles
the STRUCTURE/VERIFY tooling (`skills/refactoring/`, `skills/security/`, `skills/code-review/`, `skills/simplify/`)
and the `vibe*` coded gates under `tools/`, all opt-in. Full install (the closure-gate hook and the coded
scanners) is covered in [docs/playbook.md](docs/playbook.md).

---

## Scope: keep a human in the loop

LDD makes vibe-coded code clean and auditable, and its court pushes on the bigger design calls. But that is a
safety net, not a guarantee: LDD mainly **polishes the architecture you gave it**, and it will faithfully rebuild
a flawed design without flagging that it was the wrong one. It does not own the call on whether the design should
exist, whether the security model fits your threat environment, or whether the product is the right one to build.
Keep a **human engineer in the loop** for anything production-bound: LDD raises the floor (clean, traced,
testable); it does not set the ceiling.

---

## License

MIT. Use it, fork it, adapt it.

*Log-Driven Development is the project-agnostic distillation of building a real system end to end with AI agents.
(Formerly "Ledger-Driven Development"; the intent ledgers keep their name, the method is now named for the running
**log** of decisions.)*

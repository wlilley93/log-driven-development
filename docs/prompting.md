# Prompting LDD: how to actually drive it (and the court), in plain English

You do not need to memorize commands, invariants, or brief formats to run LDD. You describe your
situation and what you want in plain English; the method recognizes the shape of the work and supplies
the discipline (the citations, the both-altitudes harvest, the two-leg close, the court seats) that
you did not have to spell out. This guide shows the plain-English prompts a newcomer actually types,
what the method does with each, and the few habits that make an ask land well.

The running example is **Tasky**, the repo's worked example (a vibe-coded task tracker with three
competing notions of "completion", an auto-reopen-on-blocker rule, and a share link with no expiry).
The full Tasky run is under [`examples/`](../examples/).

> If you have the plugin installed, `/ldd <goal>` and `/court <question>` are shorthands. You do not
> need them: the skills also activate when you just describe the work, so everything below is written
> as plain sentences you could type to any LDD-aware agent.

---

## You mostly just describe the situation

The single most useful thing to know: **say what you inherited and what you want done, and point at
the real thing.** You do not orchestrate the agents; the method does. Each example below is the whole
prompt a newcomer types, followed by what the method then does on its own.

### Start a harvest (understand the legacy)
> *"I inherited this task tracker and nobody knows how 'completion' actually works, there seem to be a
> few competing versions of it. Before we touch anything, work out what the code really does and write
> it down, with where you found each rule."*

What the method does: harvests the area into an intent ledger, capturing both the data shapes AND the
real procedures (e.g. exactly how the auto-reopen cascade runs), cites the source line for every
claim, and records what it deliberately leaves out. You did not have to ask for any of that.

### Distil the spec (and trust it dropped the right things)
> *"Good. Now turn that into the smallest spec we'd actually rebuild from, and be honest about what
> you're leaving out and why."*

What the method does: distils the minimal spec, records each drop with a reason, and runs an adversary
over those drops to make sure it dropped duplication, not a real rule it simply never read.

### Check it is actually done
> *"You told me the spec is finished, but did you check it against the real codebase, or just that it
> reads consistently?"*

What the method does: runs the close's second leg, the source-coverage sweep, which re-walks the code
asking "what is in here that never made it into the spec?" This is the leg most people skip, and the
only one that catches an omission (a missing thing leaves no contradiction for an internal check to
trip on).

### Make a contested decision, and escalate if needed
You never describe the panel; you ask, and the court forms itself.
> **Decide it:** *"We keep arguing about whether Tasky's share links should expire. Get a few
> independent, honest reads on the real code and just make the call, don't book another meeting."*

The method convenes a Court: independent critics who each cite the actual code, ending in a decision
(say, add expiry and revocation), with the losing argument recorded as dissent.

> **You're not sure / you disagree:** *"I'm not convinced, the worry about breaking existing links got
> brushed aside."*

That is standing for an appeal. Fresh critics re-weigh it against the Court's record and uphold or
overturn.

> **Settle it for good:** *"This same fight keeps coming up on other projects too, settle the rule
> itself, not just this one case."*

The Supreme Court rules on the principle and writes a numbered **spec law** that binds every future
project. Three plain sentences from you; the whole three-tier court underneath.

### Pick the work up cold
> *"I have no idea where this left off. What is the state and what is the one next thing to do?"*

What the method does: reads the RESUME pointer, the recent journal, and the task list, and tells you
where you are and the single next move.

---

## What makes a plain-English ask land well

You do not need the jargon, but three simple habits make any LDD ask sharper:

1. **Point at the real thing.** "this task tracker", "the share-link code", "the spec you just wrote".
   The method's first move is always to read the actual code; naming it helps.
2. **Say what you want out of it.** "write down what it does", "make the call", "tell me if it's
   really done". A goal turns a chat into a deliverable.
3. **Say when you want a decision.** If you add "and just decide, don't give me options", you get a
   court that ends in a build-or-kill instead of a discussion. If you say "be honest about what's
   missing", you get the source-coverage check, not a reassurance.

That is the whole skill of prompting LDD. Everything stricter than this is the method's job, not
yours.

---

## Under the hood (you do not type this)

For the curious, and for advanced users who want to hand-write a sub-agent brief: your plain-English
ask is expanded by the method into disciplined briefs for its sub-agents. You never have to write
these, but this is the shape they take and the rule each encodes.

- **Harvest brief.** "Extract the intent of `<area>` from `<path>`. Capture BOTH altitudes: the SYSTEM
  (shapes/enums/state) AND the PROCESS (the step-by-step procedure one level down). Cite `file:line`
  for every claim; record what you DROP and why." (Encodes LDD-INV-18 and provenance.)
- **Distil/drop-list adversary.** "Re-open the cited source for each dropped item and rule it
  redundancy (fine) or missed-procedure (not fine); spot-check retained claims for fidelity; read every
  auth/money file completely." (Encodes LDD-INV-13.)
- **Two-leg close.** "Leg A: walk the SOURCE for load-bearing detail that never reached the spec, loop
  until dry. Leg B: check the spec against itself. Done only if both are clean." (Encodes LDD-INV-5.)
- **Court seat.** "Ground-truth the real tree first; a seat that cannot cite is ignored. Lead with
  the uncomfortable truth. Return a blunt verdict." Then the orchestrator determines genuine function
  and ends in build-or-kill, recording dissent.

The point of the plain-English layer is that you say the first version and the method writes the
second.

---

## When the ask goes wrong (and the small fix)

These are the plain-English asks that make LDD run badly, each with the one change that fixes it.

| What goes wrong | Why | Say this instead |
|---|---|---|
| *"Summarize the codebase."* | You get a tour of the structure, not the behaviour. | *"...and explain how it actually behaves, step by step, not just what the pieces are."* |
| *"Is it done?"* / *"Looks good?"* | The agent agrees with its own summary. | *"Check the spec against the real code for anything missing, then tell me."* |
| *"Write up the spec."* | It can read tidy and still have dropped a whole layer. | *"...and be honest about what you left out and why."* |
| *"Have a think about whether to do X."* | You get a discussion that ends in "let's revisit". | *"...get a few independent reads and just make the call."* |
| *"Trust me, just build from the notes."* | Ungrounded notes calcify into wrong requirements. | *"Check the notes against the code first, then build."* |

The pattern: a vague ask gets a vague answer; one concrete clause (point at the real thing, ask for
the behaviour, ask for a decision, ask what's missing) is enough.

---

## See also
- [README.md](../README.md) : the pitch, with these prompts scattered by section.
- [playbook.md](playbook.md) : the step-by-step operating manual, once you want the full discipline.
- [skills/court/SKILL.md](../skills/court/SKILL.md) : the court and its appeal tiers in full.
- [examples/](../examples/) : the full Tasky harvest, spec, court verdict, and ADRs.

# Anti-patterns, and the rule that prevents each

This is the field guide to the ways LDD goes wrong in practice, and the discipline that prevents each one. The
[README](../README.md) is the pitch, [methodology.md](./methodology.md) is the long-form arc, and
[systems.md](./systems.md) is the systems reference. This doc is the inverse view: not "here is the machine" but
"here is how the machine breaks, and the one rule that stops it."

Every entry below is a failure mode that actually happens when you run LDD with AI agents, especially under
always-on orchestration where many agents fan out with little human input. Each entry is kept tight on purpose:
**the failure** (what you see), **why it happens** (the pull that produces it), **the rule that prevents it** (the
discipline to apply), and **how to catch it** (the cheap check that surfaces it before it costs you).

The disciplines these map to live in [systems.md, system 8](./systems.md#8-the-disciplines) and
[methodology.md, section 4](./methodology.md#4-the-standing-disciplines-each-prevents-a-specific-failure). Read
this when you want to recognise the smell early, in yourself or in an agent's output.

A note on framing: most of these failures are not stupidity, they are an optimisation pulling the wrong way. An
agent reaching for the tidy answer, a builder eager to report success, a panel that feels productive while
deferring. The rule in each case is the thing that redirects that pull back toward a clean, grounded, shipped
result.

---

## 1. Drift (the rebuild becomes the mess)

**The failure.** Structure rots one commit at a time. A second copy of a rule lands here, an over-long function
there, a parallel helper that does almost what an existing one does. None of it trips anything, because nothing is
checking. By the time someone notices, the clean rebuild has re-grown the sprawl it was supposed to escape, and
the "looks done" build is the same tangle in new clothes.

**Why it happens.** Quality enforcement was treated as a periodic ritual (a refactor sprint, a review day) rather
than a continuous gate. Between rituals, every agent and every human takes the locally cheap path, and locally
cheap duplication is globally expensive. Agents in particular will happily write a third near-copy of a function,
because each copy is locally correct and they cannot see the whole tree at once.

**The rule that prevents it.** The closure-gate runs on **every commit**, not periodically: a max-function-length
deny, formatter and linter as hard gates, and a cross-module **duplication ratchet** held by *folding* duplication,
never by raising the number. The ratchet is the load-bearing part: the duplication budget is a number you only
ever hold or lower, and you lower it by consolidating, never raise it to make a commit pass. When the gate runs
continuously, the heavy periodic refactor becomes a net for what slipped, not the primary control.

**How to catch it.** If a commit ever passed by *raising* the duplication budget, that is the drift, caught
red-handed in the diff to the gate config. Cheap scan: grep the gate config history for any increase to the
ratchet number. Slower scan: the STRUCTURE phase of the milestone close is the backstop that flags any God-object,
leaked abstraction, or near-duplicate the per-commit gate let through.

---

## 2. Over-claiming done (the half-build that says it shipped)

**The failure.** A subagent returns "complete, all tests passing," the orchestrator records it as done, and the
milestone moves on. Later, a whole surface turns out to be stubbed, an invariant was never actually enforced, or a
test asserted the wrong thing. The "done" was a self-report that nobody ground-truthed.

**Why it happens.** A builder agent is optimising to report success, and "the tests I wrote pass" is the easiest
success to report. The orchestrator, under throughput pressure, treats that report as the verdict instead of as an
input. "Looks done" and "is done" feel identical from the outside until someone attacks the surface.

**The rule that prevents it.** **Done is the orchestrator's judgement after a clean closure sweep, never a
worker's claim.** A subagent saying "done" is an input. The orchestrator re-runs build, test, lint, and re-proves
the load-bearing invariant itself, from a clean checkout. And every milestone closes through an **independent
adversarial verifier** that re-runs from clean and tries to break the new surface: in practice the verifier earns
its keep by catching real defects, including security holes, that the builder talked itself out of seeing.

**How to catch it.** "Done" without a re-run from clean is the tell. Before accepting any "complete," ask: did
*I*, the orchestrator, build and test this from a clean tree, and re-prove the named invariant? If the only
evidence is the worker's word, it is not done yet. The closure sweep (build covers spec, not just tests green) is
the mechanical version of the same check.

---

## 3. Racing on a shared file (two writers, one hot file)

**The failure.** Two agents are spawned to work in parallel and both edit the same hot file (the spec, an index,
a shared module). Their writes interleave or clobber, cross-references break, and the merged result is incoherent
in a way no single agent intended. Worst case it is silent: the file is syntactically fine but semantically
corrupt.

**Why it happens.** Parallelism is tempting for throughput, and it is easy to fan out work without first
partitioning the files each agent owns. The collision is invisible at spawn time and only shows up in the merged
output.

**The rule that prevents it.** The **file-partition rule**: parallel authors own **distinct** files, one owner
each, and never touch another's. For a genuinely hot shared file, agents do not write it at all: they **return**
their content blocks, a coherence agent emits an integration checklist, and the **orchestrator applies it
serially**. Authoring is parallel; integration is serial and single-writer.

**How to catch it.** Before spawning a fan-out, list the files each agent will write and check the sets are
disjoint. If two briefs name the same file, stop and re-partition. After a multi-author wave, a coherence pass
that scans for contradictions and duplicate sections catches any collision that slipped through.

---

## 4. Guessing over grounding (confident fiction in the record)

**The failure.** An agent asserts a fact about the legacy ("there is one completion path," "this endpoint checks
auth") that is plausible and tidy and wrong. It goes into the intent ledger unchallenged, calcifies into a false
requirement, and the rebuild is now built on a fiction nobody can trace back to evidence.

**Why it happens.** The tidy answer is the one the model reaches for first, because it is the most probable
continuation, not the true one. Reading and citing the actual tree is slower than asserting, so an
unconstrained agent asserts. Most bad rebuilds rest on plausible claims nobody checked.

**The rule that prevents it.** **Ground-truth everything**, and **provenance or it does not go in.** Every claim,
finding, and "it is done" cites real evidence: a grep, a file read, a count, a test run, an exact file and line.
An agent (or a person) that cannot cite is **ignored**. If you cannot point at `file:line` or command output, you
do not know it yet, you are guessing.

**How to catch it.** Scan any ledger claim or agent finding for its citation. A sentence about the legacy with no
`file:line` attached is a vibe, not a fact: strike it or ground it. The same test applies to council seats, a seat
that cannot cite the real code is disregarded by construction.

---

## 5. Blanket commits (the add-all that sweeps the world)

**The failure.** A beat ends with `git add -A` (or `git add .`), and the commit sweeps in build artifacts,
unrelated edits, a stray scratch file, and the actual change all together. History becomes unattributable and
unbisectable: nobody can later isolate *which* change introduced *which* effect.

**Why it happens.** Blanket-add is the fastest way to stage, and under autonomous throughput the fast path wins
unless a rule forbids it. The cost (an unbisectable history) is deferred and invisible at commit time.

**The rule that prevents it.** **Commit per beat with explicit paths**, never a blanket add. One coherent unit per
commit, each path named, with the co-author trailer. The explicitness is the point: naming the paths forces you to
commit exactly the change and nothing else.

**How to catch it.** Any commit command containing `add -A`, `add .`, or `add --all` is the anti-pattern, visible
in the command itself before it runs. After the fact, a commit that touches build output, lockfile-plus-unrelated,
or files from two different concerns is the smell: it should have been two commits with explicit paths, or one
with the artifact excluded.

---

## 6. Deliberation as procrastination (the panel that only defers)

**The failure.** A council, audit, or review is convened and produces... another document. "We should investigate
this further." "Let us revisit next milestone." The deliberation felt productive, but nothing was built and
nothing was killed. The fork is exactly as open as before, now with a paper trail.

**Why it happens.** Deliberating feels like progress and carries no build risk, so it is the comfortable default
when a decision is hard. A panel with no termination rule will reliably produce a deferral, because deferral is the
lowest-friction output that still looks like a conclusion.

**The rule that prevents it.** A council **ends in a build action or a kill**, the same beat, never "we will look
at it later." And the **deliberation budget** governs whether a council is convened at all: in the build phase the
risk lives in the *unbuilt* surface, so a reversible, swappable choice gets **one decisive sentence and then you
build it**, not a panel. Reserve the council for genuinely irreversible, load-bearing forks.

**How to catch it.** Read the verdict's last line. If it is not a concrete commit or an explicit kill, the council
failed and must reconvene to a decision. The slower tell is the **meta-to-build ratio**: if the project has held
more councils than it has shipped milestones, deliberation has become the work, and that is itself a finding to
surface at the retrospective.

---

## 7. Building on an unexercised choice (the armchair decision-of-record)

**The failure.** A decision-of-record is written selecting a framework, a store, or a protocol, on the strength of
argument alone, and the build commits to it. Then the thing turns out not to do what the prose assumed: the
library cannot express the invariant, the store has the wrong consistency model, the protocol does not compose.
Now an irreversible-feeling choice has to be unwound from under a built surface.

**Why it happens.** Writing a convincing rationale is easy and feels rigorous; actually exercising the artefact is
slower and risks revealing the choice was wrong. The armchair ADR has all the *form* of diligence with none of the
contact with reality.

**The rule that prevents it.** **No decision-of-record selecting a buildable thing without having exercised it.**
A buildable artefact (framework, store, protocol) is chosen by a **spike or a thin slice that actually runs it**,
not by an ADR written from the armchair. For an irreversible or load-bearing choice, the spike comes **before** you
commit to it, not after.

**How to catch it.** Read the ADR for a buildable choice and look for the spike it cites. An ADR selecting a
framework with no reference to code that exercised it is the anti-pattern. If the "evidence" is entirely prose,
the choice has not actually been tested, build the thin slice before recording the decision.

---

## 8. The orchestrator editing shared state from a subagent (the one-writer breach)

**The failure.** A spawned agent, told to "update the journal" or "tick off the task," writes to the ledgers, the
index, the spec, or the task list directly. Several do it at once and their appends collide: lost writes, a
mangled index, a task list that disagrees with itself. The shared record, the one thing that has to stay coherent,
is now incoherent.

**Why it happens.** It is convenient to let the agent that did the work also record it, and the breach is
invisible until two agents append concurrently. The pull is toward "whoever did the thing writes the thing," which
is exactly the wrong owner under parallelism.

**The rule that prevents it.** **The one-writer rule: only the orchestrator writes shared state.** Spawned agents
**return** their what and why as free text; the orchestrator integrates serially and owns the truth. Every brief
must say it explicitly: do NOT journal, do NOT touch shared state, do NOT commit; return your findings and the
orchestrator records them.

**How to catch it.** Every subagent brief should carry the "do not write shared state, return instead" instruction;
a brief missing it is the gap. After a wave, a shared file with edits from a non-orchestrator hand (or an index
with duplicate or out-of-order entries) is the breach made visible.

---

## 9. Rigid output schemas under rate-limiting (the cascade failure)

**The failure.** Subagents are required to return a strict structured format (rigid JSON, a fixed field schema).
Under rate-limiting or partial responses, an agent returns something that does not parse, the orchestrator's
strict parser rejects it, and the whole fan-out cascades into failure instead of degrading gracefully. Good work
is thrown away because its wrapper was malformed.

**Why it happens.** A rigid schema feels safer and more machine-friendly, so it is the tempting design for
agent-to-orchestrator returns. But agents under load do not reliably honour rigid schemas, and a brittle parser
turns one flaky response into a total failure.

**The rule that prevents it.** **Prefer free-text returns and self-written files** over rigid output schemas. Let
agents return prose (or write their own file and return its path); the orchestrator extracts what it needs
tolerantly. **Wave-throttle** concurrency so you do not slam the rate limit, and give each agent **per-agent
retry** so one failure does not sink the wave.

**How to catch it.** If a fan-out's failures cluster at "could not parse the response" rather than "the work was
wrong," the schema is too rigid, loosen it to free text. The tell at design time is any brief that demands an
exact output shape from the agent; relax it to "return your findings as text."

---

## 10. Unplanned drift into the next milestone (the close that never planned)

**The failure.** A milestone's build is done and verified, and work simply continues into the next thing without
ever planning it. There is no named next milestone, no scoped sequence, no single next move. Direction is now
improvised commit by commit, and the next agent to pick up cold has no pointer to what was meant to happen.

**Why it happens.** Momentum. The build is working, so continuing to build feels like the obvious move, and
stopping to plan feels like a tax. But unplanned momentum is how scope creeps and how a cold resume loses the
thread.

**The rule that prevents it.** **PLAN is the mandatory fifth phase of the milestone close, and the next build does
not start until it runs.** PLAN names the next milestone's scope, sequence, and risks, plus the single next move,
and it updates the RESUME pointer so a cold agent can lift it. A high-stakes next fork escalates from PLAN to a
planning agent or a council. No drifting into an unplanned next milestone.

**How to catch it.** Read the RESUME pointer: if it does not name one concrete next move, PLAN did not happen.
A milestone sign-off missing its PLAN section is the same gap on the artefact. The cold-start test is the sharpest:
hand the RESUME pointer to a fresh agent, if it cannot say what to do next from that alone, the plan is not real.

---

## 11. Skipping the walking skeleton (integration risk hidden until the end)

**The failure.** The rebuild goes layer by layer (all the storage, then all the domain, then all the API) instead
of one thin path through every layer first. Each layer looks complete in isolation. Then they are wired together
at the end and the integration surprises land all at once, exactly where they are most expensive to fix.

**Why it happens.** Layer-by-layer feels orderly and lets each layer be "finished" before moving on. But it
defers the riskiest part, the seams between layers, to the latest possible moment.

**The rule that prevents it.** Build the **walking skeleton first**: the thinnest end-to-end slice that actually
runs, one real path through storage, domain, API, and surface, before deepening any one part. The exit criterion
is concrete: one real request runs end to end from a clean checkout with the gates green. Thin, but whole.

**How to catch it.** Ask whether one real request runs end to end through every layer today. If the answer is "not
yet, we are still finishing the storage layer," the skeleton was skipped and integration risk is accumulating
unseen. The closure-gate's red-until-built tests for declared-but-unbuilt surfaces make the gap visible: a whole
layer with no green end-to-end path is the smell.

---

## 12. Transcribing instead of distilling (the spec as big as the legacy)

**The failure.** The "spec" comes out the same size and shape as the legacy: every quirk, every redundant
mechanism, every accreted special case faithfully copied across. The sprawl was preserved, not dropped. The
rebuild now has the same complexity to carry, with a spec that merely re-describes the mess.

**Why it happens.** Transcribing is mechanical and safe-feeling: copy what is there and nothing is "lost."
Distilling requires the harder judgement of deciding what to drop, and dropping anything feels risky, so the
timid default is to keep it all.

**The rule that prevents it.** Distil the **smallest complete spec**: the minimal set of primitives that solves the
domain, with the sprawl **dropped on purpose** and **each drop recorded with its reason**. The data structure is
the product; get the core types and invariants right and everything else is a view over them. A dropped thing is
never dropped silently, it is recorded so a future reader sees a choice, not an oversight.

**How to catch it.** Compare the spec's size to the legacy's. If it is as big as the legacy, you transcribed, you
did not distil. The other tell is an empty drop-list: a genuine distillation of a vibe-coded system always drops
duplicated mechanisms and accreted special cases, so a spec that dropped nothing did not do the work.

---

## 13. Deferring a security issue (the known hole that survives the rebuild)

**The failure.** The harvest (or a verifier, or a review) surfaces a real security defect: a token with no expiry,
a missing access check, an injection path. It gets filed for later instead of fixed now. "Later" slips, the
rebuild ships, and the known hole survives into the clean system, which is now clean everywhere except the one
place it actually mattered.

**Why it happens.** A security fix interrupts the current beat and feels like a detour, so the pull is to log it
and keep moving. But a filed security issue competes with everything else in the backlog and reliably loses.

**The rule that prevents it.** **Fix security the moment it is found.** This overrides every schedule and every
beat plan. A security issue is never committed knowingly and never deferred: it is fixed when found, the moment it
is found, before the beat continues. (A genuine *design* fork around the fix, the kind that has real cost on both
sides, can go to a council, but the council still ends in a build action that closes the hole.)

**How to catch it.** Any backlog entry of the form "TODO: fix security X" is the anti-pattern by definition: a
security item in a backlog is one that was deferred instead of fixed. Scan the task list and the DROP-lists for
security smells that were logged rather than closed, each one is a hole still open.

---

## 14. Three-things-at-once (the beat that is really five beats)

**The failure.** A "beat" bundles several unrelated changes: a feature, a refactor, a config tweak, a dependency
bump, all in one swing and one commit. When something breaks, the cause is buried in a tangle of unrelated edits,
and the journal entry cannot honestly say what this beat was *about* because it was about five things.

**Why it happens.** Batching feels efficient ("while I am in here..."), and an agent given a broad goal will
naturally try to satisfy all of it at once. But a beat that does five things cannot be cleanly verified, cleanly
committed, or cleanly explained.

**The rule that prevents it.** **Pick the one next move**: the smallest coherent unit that advances the goal, not
three things, one. One beat, one coherent change, one commit with explicit paths, one journal entry that can state
plainly what and why. If you find yourself writing "and also" in a journal entry, it was two beats.

**How to catch it.** A journal entry with multiple unrelated "and also" clauses is the tell, as is a commit
touching files from several different concerns. Before starting work, name the single next move in one sentence; if
the sentence needs an "and," split it.

---

## 15. Council without standing, or the wrong tier (the appeal that re-argues blind)

**The failure.** A settled verdict gets re-opened on a whim ("I would have designed it differently"), or an appeal
re-argues the question from scratch without engaging the original reasoning, or a point of *law* (was the method
applied correctly?) gets mixed into a court that hears *merits* (what is the right design?). The hierarchy
collapses into endless re-litigation with no principled stopping point.

**Why it happens.** Without a standing requirement, any dissatisfaction looks like grounds for appeal, and without
the merits-versus-law split, every tier re-fights the same fight. Taste masquerades as a basis for reopening.

**The rule that prevents it.** Escalation needs **standing**: the principal disagrees, a load-bearing dissent was
left unresolved, or new ground-truth contradicts a relied-upon point. "I would have designed it differently" is
not standing. The **Appeals Council** re-weighs the **merits** but as a *review* that must engage the original
reasoning, not re-argue blind. The **Supreme Council** hears **only points of law** (was the invariant spec and the
LDD discipline correctly applied), and its ruling becomes **spec law**, immutable precedent that binds every future
court. A decision colliding with spec law is refused at the spec layer.

**How to catch it.** Check the appeal's basis against the standing list before convening anything: no standing, no
appeal. Check that an Appeals seat cites the Council's actual reasoning rather than starting fresh. Check that a
Supreme question is genuinely about *law* (method and invariants) and not smuggled-in *taste*: if it is taste, it
does not belong at the apex.

---

## 16. The principal's call decided by an agent (guessing on policy)

**The failure.** A question that is really the principal owner's **policy or domain call** (a product direction, a
compliance posture, a pricing or trust decision) gets settled by an agent or a council as if it were a technical
choice. The agent guesses on the owner's behalf, and the guess becomes a built-in assumption nobody actually
authorised.

**Why it happens.** From inside the build, a policy call can look like just another fork to resolve, and an
autonomous agent is biased toward resolving forks rather than pausing to ask. The boundary between "technical
decision we own" and "owner's call we must ask about" is easy to blur under momentum.

**The rule that prevents it.** A decision that is the principal owner's policy or domain call, **not** a technical
one, is **asked**, not guessed. The court decides technical merits and points of law; it does not decide what the
owner wants the product to be. When a fork turns on policy, surface it and ask.

**How to catch it.** Before a council or a build commits to a fork, ask: is this a technical question, or is it
really "what does the owner want here?" If reasonable owners could differ on values (not facts), it is a policy
call: stop and ask the principal rather than recording a guess as a decision.

---

## The smell test (scan this to self-check)

A fast checklist an agent can run against its own work, mid-beat or at close. Each line is a smell; if it is true,
stop and apply the rule above.

- A claim about the legacy with **no `file:line`** behind it. (Ground-truth it or strike it.)
- **"Done" that only a worker said**, not one the orchestrator re-ran from clean. (Re-prove it yourself.)
- A commit staged with **`add -A` / `add .`**. (Name explicit paths.)
- The duplication ratchet **raised** to make a commit pass. (Hold or fold, never raise.)
- A council or audit whose last line is **not a commit or a kill**. (Reconvene to a decision.)
- A decision-of-record for a framework/store/protocol with **no spike** behind it. (Exercise it first.)
- A subagent that **wrote shared state** (journal, spec, index, task list). (Only the orchestrator writes.)
- Two parallel agents whose briefs **name the same file**. (Re-partition, or return-and-integrate serially.)
- A brief demanding a **rigid output schema** from the agent. (Free text, wave-throttle, per-agent retry.)
- A RESUME pointer that **names no single next move**. (PLAN did not happen.)
- **No real request runs end to end** yet. (The walking skeleton was skipped.)
- A spec **as big as the legacy**, or with an **empty drop-list**. (You transcribed, not distilled.)
- A security issue **filed in the backlog** instead of fixed. (Fix it now; never defer.)
- A journal entry with **"and also"** in it. (That was two beats; pick one next move.)
- An appeal opened on **"I'd have done it differently"**. (No standing, no appeal.)
- A **policy/owner question** being settled by an agent. (Ask the principal, do not guess.)

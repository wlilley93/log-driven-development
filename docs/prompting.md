# Prompting LDD: how to actually drive it (and the council) well

LDD is run by an agent (Claude), and the quality of an LDD run is mostly the quality of the prompts
that drive it. This guide is the prompt-level companion to the [playbook](playbook.md): the
invocations that start each element, the brief shape that makes each one work, the disciplines a good
prompt encodes, and the prompts that make it run badly.

The running example throughout is **Tasky**, the repo's worked example (a vibe-coded task tracker
whose intent was never written down): it has three drifting representations of "completion" (`done`
boolean, a `status` enum, an `archivedAt` timestamp), an auto-reopen-on-blocker rule that cascades
through the blocks graph, and a share link with no expiry and no revocation. The full Tasky harvest,
spec, council verdict, and ADRs are under [`examples/`](../examples/). Every example prompt below is
written against Tasky so you can read it concretely and lift the shape for your own codebase.

> One framing to hold: a prompt is not a wish, it is a brief. The agent does what the brief makes
> checkable, not what it hopes you meant. Every recipe below turns a discipline into something the
> agent must produce and you (or a verifier) can check.

---

## The one rule under every good LDD prompt

Three things make any LDD brief work; their absence is why most fail.

1. **Demand ground-truth, refuse vibes.** Tell the agent to grep, read the real files, run the
   counts, and to cite `file:line` or command output for every claim. "A claim you cannot point at,
   you do not know yet" (LDD-INV-1). A brief that does not ask for citations gets confident fiction.
2. **Give exact anchors and the exact thing to prove.** Name the files, the invariant to hold, and
   for a verifier the exact attack to run and the verdict shape to return. Vague briefs produce vague
   work; the agent fills ambiguity with the easiest reading.
3. **State the end-state, and make it a hard stop.** "Return X", "write to exactly this file", "end
   in build-or-kill", "stop before the build". An LDD element without a defined terminal state runs
   long or declares a false done.

If a prompt has those three, the agent can run the element. If it is missing one, name which: most
"the agent went sideways" moments are a missing anchor or a missing end-state.

---

## Entry invocations (how to start)

| You want | Say |
|---|---|
| Start a run / a phase | `/ldd <what to harvest or build>` (with the plugin), or without it: "Read `skills/ledger-driven-development/SKILL.md` end to end, then follow the beat loop for: `<goal>`." |
| Check where a run is | `/ldd status` (or: "Read `metacognition/RESUME.md`, the last few journal entries, and the task list, then tell me the one next move.") |
| Make a hard, contested call | `/council <the decision or the honest question>` (or the convening prompt in the Worked examples below). |
| Challenge a verdict | `/council <the verdict> | appeal` (needs standing); a point of *method law* goes `| supreme`. |

The no-plugin form is just the plugin form spelled out: point the agent at the skill, then at the
goal. The skill is self-contained and prescriptive, so "read it and follow the beat loop" is a
complete instruction.

---

## Per-element prompt recipes

Each recipe is: the shape of the brief, the disciplines it must encode, and the invariant it serves.

### Harvest agent (one ledger, BOTH altitudes)
Brief shape: "You are a harvest agent. Extract the INTENT of `<area>` from `<path>`. Capture BOTH
altitudes: the SYSTEM (shapes, enums, state-machines) AND the PROCESS (the step-by-step procedure,
the rules, the ordering, the edge cases - what actually happens, one level below the structure).
Cite `file:line` for every claim; provenance or it does not go in. Sample large trees strategically
and SAY what you skipped. Check for archived/zipped copies before declaring a file absent, and note
all copies of a source. Write your ledger to exactly `<file>`; record what you DROP and why. Return a
short what/why; do not journal or commit."

Why it works: the explicit PROCESS altitude is the load-bearing word (LDD-INV-18). Without it, an
agent satisfies "domain rules" with structure ("a task has a `status` enum") and silently withholds
the procedure ("how a blocked task reopens"). The drop-with-reason makes the distil auditable later.

### Distil / drop-list adversary (before "harvest done")
Brief shape: "You are the drop-list adversary. Re-open the cited source for each entry in the
harvest's DROP list and rule it: legitimate REDUNDANCY (verbatim/duplicate, fine to drop) or
negligently-missed PROCEDURE (a step, rule, or algorithm whose only home was source we did not fully
read). Spot-check a sample of RETAINED claims against their `file:line` for fidelity (a
self-consistent ledger can still be wrong). Force security-COMPLETE, not sampled, reads of every
auth/money/external-reach file. Return: each drop reclassified, any infidelity found, any risk file
not fully read."

Why it works: distil is the hardest step and the one most often left with no adversary (LDD-INV-13).
This brief is the decision-step analogue of builder + adversarial-verifier: it re-opens the source so
a dropped procedure cannot hide behind "we distilled it".

### Two-leg closure (the source-coverage sweep is the one people skip)
Brief shape: two briefs, both required for "done" (LDD-INV-5).
- Leg A, source -> spec coverage: "Re-walk every harvest source and ask: what load-bearing PROCEDURE
  lives here that never reached the spec? Loop until a round finds nothing new. Your evidence base is
  the SOURCE and the ledger drop-lists, NOT the spec. Bar: every load-bearing procedure, not every
  byte. Return the residual gaps."
- Leg B, spec -> internal coherence: "Check the spec against itself: ids resolve, no contradiction,
  traceability holds, hygiene clean. Return findings by severity."

Why it works: an internal-coherence sweep audits the spec against itself and is structurally blind to
an omission (an omission leaves no contradiction). Only Leg A, looping over the SOURCE, can see
un-folded detail. The single most common closure failure is running Leg B, getting "clean", and
calling it done. Name Leg A explicitly or it will not happen.

### Builder + adversarial verifier (any substantive build)
Brief shape (verifier): "Try to BREAK this. Re-run from a clean checkout, attack `<the invariant>`
with `<the exact attack>`, and return the verdict as `<shape>`. Default to 'broken' if you cannot
affirmatively show it holds." The builder builds; the verifier is an independent skeptic, not a
second opinion.

Why it works: a single pass rationalises its own work; an adversary prompted to refute catches what
the builder talked itself past, including security holes. "Default to broken if unsure" stops the
verifier from rubber-stamping.

### The council (the adversarial deliberation court)
Brief shape: pick distinct, non-overlapping seats (e.g. process-critic, devil's-advocate/null-
hypothesis, the rejected alternative's advocate, a security lens). Tell EACH seat: "Ground-truth the
real tree first; a seat that cannot cite is ignored. Lead with the uncomfortable truth, not a hedge.
Return a blunt verdict." Run them blind to each other (parallel). Then synthesise, run a
**determination of genuine function** (decide by ground-truth, a spike or a demonstrated mechanism,
whether the chosen thing will actually work, not just whether it is right on the merits), and
**end in a build action or a kill** the same beat. Record the surviving dissent verbatim.

Why it works: the seats' independence prevents groupthink; ground-truth-first keeps it from becoming
opinion theatre; the genuine-function determination stops a plausible-but-unworkable verdict; and
"end in build-or-kill" is the discipline that separates a council from a meeting (anti-pattern #6).
The dissent is recorded because it is the standing of any future appeal.

### The appeals tiers (rare; standing required)
Brief shape: hand the higher court the FULL lower-court record (every seat verdict, the synthesis, the
dissent) and SCOPE the remit. Appeals Council: "re-weigh the merits, engaging the Council's actual
reasoning, not re-arguing blind; uphold or overturn." Supreme Council: "rule ONLY on whether the
method's invariants and discipline were correctly APPLIED (not whether the design is best); output a
numbered precedent." Fresh seats each tier, only the record carries over.

Why it works: the merits-vs-law split is what lets a Supreme ruling stand as precedent. Without
scoping the remit, an appeal just re-runs the trial. Standing ("the principal disagrees", "a
load-bearing dissent is unresolved", "new ground-truth falsifies a relied-upon point") stops free
appeals.

---

## Worked examples (example prompts)

Real, copy-pasteable prompts, written against Tasky. Lift one and swap in your area/paths. Each is
annotated with the discipline it encodes.

### A harvest-agent brief (both altitudes)
```text
You are a harvest agent. Extract the INTENT of Tasky's task-completion + blocking area from
src/. Capture BOTH altitudes:
- SYSTEM: the shapes/enums/state that represent completion and blocking (find them; cite file:line).
- PROCESS: the actual procedures - how a task moves open->doing->done, and EXACTLY how the
  auto-reopen-on-blocker cascade runs (order, depth, whether it notifies). The procedure is the
  precious part; do not stop at naming the enum.
Rules: cite file:line for every claim; provenance or it does not go in. If you sample, say what you
skipped. Write the ledger to exactly _harvest/task-model.md. List what you DROP and why. Return a
6-line what/why; do NOT journal, commit, or touch shared state.
```
Encodes: LDD-INV-18 (the PROCESS altitude is named and made the point), LDD-INV-2 (provenance),
LDD-INV-3 (the agent returns, the orchestrator writes).

### A drop-list adversary brief
```text
You are the drop-list adversary for the Tasky harvest. Open _harvest/task-model.md and, for each
entry under "What to DROP", re-read the cited source and rule it: REDUNDANCY (fine) or
MISSED-PROCEDURE (a rule/step we failed to read, not a duplicate). Pay special attention to the two
dropped completion paths and the second auth path - confirm each is truly redundant, not a distinct
behaviour. Spot-check 5 RETAINED claims against their file:line. Read the share-link code COMPLETELY
(it is the one security surface) - do not sample it. Return: each drop reclassified with evidence,
any infidelity, and confirmation the share-link file was fully read.
```
Encodes: LDD-INV-13 (distil has an adversary; redundancy-vs-procedure; security-complete coverage).

### A two-leg closure brief (Leg A is the one that catches gaps)
```text
Run BOTH legs of the Tasky closure; "done" needs both on record.
LEG A (source -> spec coverage): re-walk every file the harvest cited and ask "what load-bearing
PROCEDURE lives here that never reached docs/spec/?" Loop until a pass finds nothing new. Evidence
base = the SOURCE and the ledger drop-lists, NOT the spec. Bar = every load-bearing procedure, not
every line. Write residual gaps to _qa/source-coverage.md.
LEG B (internal coherence): check docs/spec/ against itself - ids resolve, no contradictions,
traceability holds, no dashes/secrets. Write findings to _qa/internal.md.
Return: leg-A residual count, leg-B severity counts, and a verdict (DONE only if BOTH are clean).
```
Encodes: LDD-INV-5 (two legs; Leg A loops over SOURCE, which is the only leg that sees an omission).

### A council convening prompt (an honest "is this working?")
```text
Convene a council on: "Is the Tasky harvest actually capturing the system's behaviour, or only its
structure?" Seat four independent lenses, run blind to each other:
1. process-critic: where did the harvest capture structure but miss procedure? cite ledger+source.
2. closure-gate critic: would our 'done' gate even catch a missed procedure? what is it blind to?
3. devil's-advocate / null-hypothesis: argue the harvest is fine and this is scope creep; concede
   the narrowest point where it genuinely is a defect.
4. method-improvement: the smallest change that would have caught it, tied to the exact rule it amends.
Each seat: ground-truth the real tree first (a seat that cannot cite is ignored), lead with the
uncomfortable truth. Then I will synthesise, DETERMINE GENUINE FUNCTION (does the proposed fix
actually catch the class, by demonstration not assertion?), and END IN BUILD-OR-KILL the same beat.
Record the surviving dissent verbatim.
```
Encodes: the full council discipline - distinct seats, blind runs, ground-truth-first, the
genuine-function determination, build-or-kill, recorded dissent. (This is the exact shape that, on a
real estate, surfaced a method defect and ended in three committed method changes.)

### A spec handoff prompt ("what it is and is not")
```text
You are a fresh agent. Examine the spec at <path> and write an honest "what it is and what it is not".
Start at BIBLE.md, README.md, metacognition/RESUME.md, then the spec docs and _harvest ledgers.
A. WHAT IT IS: artifact type, scope, whether it captures SYSTEM and PROCESS; spot-check 5-10 claims'
   file:line anchors actually resolve in the source; the closure status and what it means.
B. WHAT IT IS NOT: not running/tested code; a minimal substrate that DROPS redundancy (not a runbook);
   not an endorsement of the legacy (it records contradictions/risks as intent); list open decisions
   and any unsourced surfaces.
C. CAVEATS: anything you could not verify; any cited file:line that does NOT resolve (that is a real
   defect - report it).
Rules: cite file:line for every load-bearing claim; do not restate the spec's own summary as fact -
confirm it. ~1.5 pages.
```
Encodes: independent verification over paraphrase (the failure mode LDD exists to prevent), and an
honest is/is-not rather than a sales pitch.

---

## Anti-prompts (what makes LDD run badly)

| The prompt that fails | What happens | The rule it violates |
|---|---|---|
| "Harvest the codebase." (no altitude, no paths, no provenance ask) | A structure-only ledger that names enums and withholds procedure; graded "well-grounded" anyway. | LDD-INV-18; anti-pattern #17 |
| "Write the spec." (no source-coverage close) | An internally-tidy spec that silently omits a whole source layer; the gate cannot see it. | LDD-INV-5; anti-pattern #18 |
| "Distil the harvest." (no drop-list adversary) | Dropped procedure hides behind "we distilled it"; a skipped file keeps its secret; a wrong-but-consistent claim survives. | LDD-INV-13; anti-pattern #19 |
| "Is it done?" / "Looks good?" | The agent rationalises a false done from its own summary. | LDD-INV-1, LDD-INV-5; anti-pattern #2 |
| "Have a panel discuss it." (no seats, no ground-truth, no terminal state) | Opinion theatre that ends in "let's revisit"; no decision, no build. | the council discipline; anti-pattern #6 |
| "Verify this." (no attack, no clean re-run, no default-to-broken) | A rubber-stamp "looks correct". | builder+verifier; anti-pattern #2 |
| "Trust the ledger, build from it." | Builds on un-ground-truthed claims; vibes calcify into requirements. | LDD-INV-1, LDD-INV-2; anti-pattern #4 |

The pattern in every failure row: a missing discipline becomes a missing word in the prompt. Put the
word back (the altitude, the source leg, the adversary, the attack, the seats, the terminal state)
and the element runs.

---

## See also
- [playbook.md](playbook.md) - the step-by-step operating manual and the beat loop.
- [skills/ledger-driven-development/SKILL.md](../skills/ledger-driven-development/SKILL.md) - the
  prescriptive procedure and the orchestration shapes.
- [skills/council/SKILL.md](../skills/council/SKILL.md) - the court in full, with the appeals tiers.
- [invariants.md](invariants.md) - the LDD-INV register every recipe cites.
- [anti-patterns.md](anti-patterns.md) - the failure modes (incl. #17-19) the anti-prompts map to.
- [examples/](../examples/) - the full Tasky harvest, spec, council verdict, and ADRs.

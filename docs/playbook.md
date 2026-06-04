# The LDD playbook: exactly what to do

This is the **prescriptive** operating manual. The [README](../README.md) is the pitch, the
[methodology](./methodology.md) is the narrative *why*, and [systems.md](./systems.md) is the reference for *how the
parts interlock*. This doc is the *how to operate*: a capable agent should be able to run Log-Driven Development
(LDD) from here with no further questions. Everything below is imperative and mechanical. When you are unsure what
to do next, the answer is in one of the seven sections here.

Read it once end to end, then keep the [Quick reference card](#7-quick-reference-card) in working memory and run the
[beat loop](#1-the-beat-loop) on every beat.

> **A beat** is the smallest coherent unit of work that lands together (one decision, one built slice, one harvest
> area). LDD runs as a sequence of beats. The procedure in section 1 is what you do on *every* one of them.

The running example throughout is **Tasky**, the same vibe-coded task-tracker used in the other docs (three
contradictory ways to mark a task done, a buried auto-reopen-on-blocker rule, a share link with no expiry). The
worked artefacts live under [`examples/`](../examples/).

---

## 1. The beat loop

Run these nine steps **in order** on every beat. Each step names its one-line *how* and the failure it prevents.
Do not skip a step because the last beat did it; the loop is the unit of safety.

**1. ORIENT.**
*Do:* read the RESUME pointer (you-are-here + the one next move + the paste-to-resume block), the last few
metacognition journal entries, and the task list. That is the entire working state.
*Prevents:* the cold-start tax (rebuilding state by archaeology, or worse, acting on a stale mental model).

**2. GROUND-TRUTH before deciding.**
*Do:* grep, read the real files, run the tests. Cite `file:line` or a command's output for every claim you are
about to rely on. If you cannot cite it, you do not know it yet, so go find out.
*Prevents:* confident fiction. Never trust a summary, a memory, or a prior claim over the actual tree.

**3. PICK THE ONE NEXT MOVE.**
*Do:* choose the single smallest coherent unit that advances the goal. One thing, not three. If you are tempted to
bundle, split it into separate beats.
*Prevents:* scope creep inside a beat, which produces an uncommittable tangle and an unwritable journal entry.

**4. ORCHESTRATE, do not edit inline.**
*Do:* for anything substantive, spawn the right agent shape (see [section 3](#3-choosing-an-orchestration-shape)).
Write the brief with **exact anchors** (`file:line`), the **load-bearing invariant** to prove, and for a verifier
the **exact attack** to run (see [section 5](#5-how-to-brief-a-subagent)). Trivial mechanical edits (a one-line typo,
a rename you can fully see) you may do inline; everything with judgement in it gets a shape.
*Prevents:* a single unsupervised pass rationalising away its own gaps, and vague briefs that produce vague work.

**5. GROUND-TRUTH THE RESULT FROM CLEAN.**
*Do:* you (the orchestrator) build, test, lint, and **re-prove the load-bearing invariant yourself**, from a clean
state. A subagent saying "done" is an **input**, never the verdict.
*Prevents:* a worker self-report passing as truth. "Done" is *your* judgement after BOTH legs of the closure sweep
are clean (internal coherence AND a source -> spec coverage sweep on record, see [section 6](#6-definition-of-done-three-levels)),
not a claim you inherited.

**6. FIX ANYTHING WRONG before committing.**
*Do:* if the result is wrong, fix it (spawn a fix beat or correct it) before you commit. **If it is a SECURITY
issue, fix it the moment it is found.** Never ask first, never commit it, never defer it.
*Prevents:* shipping a known defect, and (for security) a known hole surviving into the rebuild because it was
filed for later.

**7. COMMIT per beat with EXPLICIT paths.**
*Do:* `git add <explicit path> <explicit path>` then commit one coherent unit, with the co-author trailer. **Never**
`git add -A` or `git add .` (it sweeps build artefacts and unrelated files).
*Prevents:* unattributable, unbisectable history and accidental staging of junk.

**8. RECORD (you, the orchestrator, only).**
*Do:* write the metacognition journal entry (the *what* and the *why*, with the alternatives for a decision); append
the one-line INDEX pointer; rewrite the RESUME pointer (new you-are-here + the one next move); update the task list.
Only the orchestrator writes shared state (the **one-writer rule**).
*Prevents:* a lost audit trail, and collision/lost-writes if more than one writer touches shared state.

**9. REPORT at milestone boundaries, not mid-batch.**
*Do:* surface progress to the principal at milestone close (or when blocked on a principal-call), not after every
small beat.
*Prevents:* noise that buries the moments that actually need a human.

> The journal entry in step 8 uses [`templates/metacognition-entry.md`](../templates/metacognition-entry.md); the
> worked beats are [`examples/metacognition/0001-harvest-task-model.md`](../examples/metacognition/0001-harvest-task-model.md)
> (an action beat) and [`examples/metacognition/0002-collapse-completion-to-one-status.md`](../examples/metacognition/0002-collapse-completion-to-one-status.md)
> (a decision beat with its rejected alternatives).

---

## 2. Decision rules

When a decision arises mid-beat, classify it and apply the matching action **mechanically**. The default in the
build phase is **build, do not deliberate**: the risk lives in the unbuilt surface, so bias hard to building. Spend
deliberation only where the table says to.

| The decision is... | Test for it | Do exactly this |
|---|---|---|
| **Reversible / swappable** | You could undo or swap it later cheaply (an ID format, a helper name, a local refactor) | Write **one decisive sentence** in the journal, then build it. Convene nothing. |
| **Irreversible / load-bearing, and it picks a buildable thing** | Hard to undo *and* it selects a framework, store, protocol, or schema | Run a **spike or thin slice** that exercises it **before** you commit to it. Never record a decision selecting a buildable thing by argument alone. Then journal the result; graduate to an [ADR](#on-adrs) if load-bearing. |
| **A genuine hard fork, or an honest "is this actually working?"** | A real architectural fork, build-vs-consume, sequencing a whole program, a retrospective, or a pre-mortem | Convene a **Court** (see [section 3](#3-choosing-an-orchestration-shape) and the [`court` skill](../skills/court/SKILL.md)). It **must end in a build action or a kill**, never another doc that defers. |
| **A challenged Court verdict (with standing)** | The principal disagrees, a load-bearing dissent is unresolved, or new ground-truth contradicts a relied-upon point | Convene the **Appeals Court** (re-weighs the merits as a review). "I would have designed it differently" is *not* standing. |
| **A question of how the invariants or the method were APPLIED** | Not "is this the best design?" but "was the invariant spec / the discipline correctly applied?" | Convene the **Supreme Court**. Its ruling is **spec law** (binding precedent). |
| **The principal's policy or domain call** | It is a business, product, legal, or domain judgement, not a technical one | **ASK the principal.** Do not guess on their behalf. |
| **A security issue** | Any vulnerability, leaked secret, missing access check, weak crypto | **Fix it immediately.** This overrides every schedule, every milestone, and every other rule in this table. |

Two rules sit above the table. First: **a panel, audit, or court always terminates in a committed change or an
explicit kill, the same beat.** A deliberation whose output is "we will look at it later" is the exact pathology
the court exists to catch. Second: **surface the meta-to-build ratio honestly.** If you have held more courts than
you have shipped milestones, that is itself a finding to raise.

---

## 3. Choosing an orchestration shape

For any substantive task, reach for a **shape**, not a hand edit. Match the situation to the shape, then write the
brief per [section 5](#5-how-to-brief-a-subagent).

| The situation is... | Shape | How it runs |
|---|---|---|
| **Build one thing and be sure it is correct** | **Builder + adversarial verifier** | One agent produces. At least one *independent* skeptic tries to **break** it: grounds in the real tree, re-runs the load-bearing checks, attacks the invariants. The verifier earns its keep by catching real defects (including security holes) the builder introduced. Its verdict is your **input**, not the final word. |
| **Author a volume of independent files** | **Multi-author + coherence** | N authors run in parallel, each owning **distinct** files (never the same file). One coherence pass then merges, dedups, finds contradictions, and emits an integration checklist you apply serially. This is the harvest shape. |
| **Unknown-size discovery (find all the gaps / all the bugs)** | **Loop-until-dry** | Keep spawning rounds until **K consecutive rounds find nothing new** (K is typically 2 or 3). A fixed count stops too early and misses the tail. This is how the spec-and-build loop knows it is finished. |
| **A judgement call under stakes** | **Court** | A fan-out of independent, named seats, each a distinct lens (project health, process critic, devil's advocate, plus a domain lens: security, cost, UX, the advocate of a named alternative). Each ground-truths first; seats run independently (no groupthink); each leads with the blunt truth. Ends in a build action or a kill. See the [`court` skill](../skills/court/SKILL.md). |

Two hard rules for every shape:

- **Never let two agents write the same file.** Partition by file with a single owner each, or have them return
  content blocks for the orchestrator to integrate serially.
- **Wave-throttle concurrency** and give each agent a per-agent retry. Prefer **free-text returns** and
  self-written files over rigid output schemas, which fail under rate-limiting.

---

## 4. The gates

Two layers of enforcement. Tier 1 (the closure-gate) runs on **every commit**, continuously. Tier 2 (the five-phase
milestone close) runs at **every milestone boundary**. Tier 1 doing its job continuously is exactly what lets Tier 2
be proportionate (a scan, risk-targeted) rather than a ritual.

### 4a. The per-commit gate (continuous, every commit)

Stand this up **before the walking skeleton**, so "clean" is checkable from the first line of the rebuild. The
config is [`templates/closure-gate.config.md`](../templates/closure-gate.config.md); the worked one is
[`examples/closure-gate.config.md`](../examples/closure-gate.config.md). Every commit must pass:

- [ ] **Formatter** clean (deny on fail).
- [ ] **Linter with warnings-as-errors** (deny on fail).
- [ ] **Type-check** clean, if the language has one (deny on fail).
- [ ] **Max-function-length** limit (deny over the threshold: a long function hides duplication and God-objects).
- [ ] **The invariant test suite** green **from a clean checkout** (not just locally green).
- [ ] **The duplication ratchet** holds. This is the load-bearing gate: a cross-module duplication budget you only
      ever **hold or LOWER by folding** duplication into one shared function. **Never raise the number to make a
      commit pass** (raising it concedes the sprawl you are fighting).
- [ ] **Red-until-built tests** present for every spec surface declared but not yet built (so an unbuilt surface is
      visibly red, never silently absent).
- [ ] **`security_scan`** (`vibescan scan`): the continuous, fast security gate (secrets, dependency CVEs, fast
      SAST), the single security owner at this tier. Loud-skip if the tool is missing (warn, never silently pass).
- [ ] **`structure_scan`** (`vibeclean scan`): the structural-suite edge on the changed surface, paired with
      the max-function-length and duplication gates above. Loud-skip if the tool is missing.
- [ ] **A clean tree** (no stray artefacts, nothing uncommitted you did not mean to leave).

These are the eight gates the orchestrator runs every commit (the function-length number, the duplication budget,
and which security tool owns this tier are not restated here; see the two-tier(+) ownership matrix in
[systems.md](./systems.md), system 7, LDD-INV-7 / LDD-INV-9).

### 4b. The milestone close (five phases, in order)

A milestone is **not done** until all five run, in order. Record them in
[`templates/milestone-signoff.md`](../templates/milestone-signoff.md); the worked one is
[`examples/M1-signoff.md`](../examples/M1-signoff.md). Each phase needs **reproduced evidence** (the actual command
and the actual result), not "looks fine".

1. [ ] **BUILD.** Implement the milestone's scope. Formatter, linter, tests green from a clean checkout.
2. [ ] **STRUCTURE.** A structural *scan* of the new surface (the closure-gate continuous gates plus `vibeclean`):
   does the ratchet hold? any over-long function, God-object, leaked abstraction? Escalate to a **full refactor
   pass** (the refactoring suite) **only on flagged debt** (the continuous gate already did the heavy lifting). This
   is a scan, not a ritual.
3. [ ] **SECURITY.** The continuous `vibescan scan` gate (the one security owner, subsuming supply-chain) ran on
   every commit; at close run the full `vibescan .` sweep. The **heavy deep audit** (the security-suite methodology,
   with `vibeaudit` as its scanner engine) is **risk-targeted**: mandatory on a high-risk surface (auth, money,
   crypto, multi-tenancy, anything externally reachable), plus periodically. Do not bureaucratically deep-audit a
   trivial surface the verifier already attacked.
4. [ ] **VERIFY.** `vibetest` for test quality, and an **independent adversarial verifier** re-runs **from clean**,
   attacks the milestone's invariants, and tries to break the new surface. This is the primary
   correctness-and-security net, every milestone.
5. [ ] **PLAN (MANDATORY).** The milestone does **not** close, and the next build does **not** start, until the next
   steps are planned: the next milestone's scope, sequence, and risks, plus the single next move. A high-stakes next
   fork escalates to a planning agent or a Court. **Never drift into an unplanned next milestone.**

> Which tool owns each phase and at which trigger is not restated here: see the two-tier(+) ownership matrix in
> [systems.md](./systems.md) (system 7), the single source of truth (LDD-INV-9).

### 4c. The project-close gate (the FREEZE checklist, both legs required)

At project FREEZE the five-phase milestone close is not enough: it audits the spec against itself. Before you stamp
FREEZE/done you must also have the **source -> spec coverage sweep on record**. This item is mandatory and checkable:

- [ ] **A source-coverage sweep is ON RECORD.** A loop-until-dry re-walk of **every** harvest source (run as the
      loop-until-dry shape, K consecutive empty rounds) asked, source by source, "what load-bearing PROCEDURE lives
      here that never reached the spec?" Its evidence is the **source ranges plus the ledger drop-lists**, not the
      spec. Leg (a)'s internal-coherence audit cannot satisfy this item: an omission leaves no contradiction, so a
      clean coherence sweep is blind to it. **A FREEZE verdict with no source-coverage sweep recorded is not done**,
      no matter how clean leg (a) is.

> **What "done" means at the gate.** "Done" means **you ground-truthed it and BOTH legs of the closure sweep are
> clean.** Leg (a), **internal coherence**: the spec audited against itself (ids resolve, no cross-doc contradiction,
> every claim provenanced, traceability holds). Leg (b), **source -> spec coverage**: a re-walk of every harvest
> source asking "what load-bearing detail lives here that never reached the spec?", whose evidence is the source
> ranges plus the ledger drop-lists, **not** the spec. Leg (a) audits the spec against itself and is structurally
> blind to an omission (an omission leaves no contradiction), so leg (b) is the only one that catches a whole
> procedure that was never folded in. A done verdict with **no source-coverage sweep on record** is not done. It
> never means "the tests pass" alone, it never means internal coherence alone, and it never means a worker said so.
> (The coverage bar is "every load-bearing PROCEDURE reached the spec", not "every source byte": distil still
> governs, do not let the coverage loop drag the spec toward transcription.)

---

## 5. How to brief a subagent

A vague brief produces vague work. A precise brief produces a result you can ground-truth in minutes. Tell **every**
spawned agent these standing rules, then give it the specifics.

**Standing rules to put in every brief:**

- Do **NOT** journal. Do **NOT** touch shared state (the ledgers, the index, the spec, the task list). Do **NOT**
  commit.
- **RETURN** your *what* and *why* as free text; the orchestrator records it.
- **Ground-truth everything** you claim: cite `file:line` or command output. A claim you cannot cite is ignored.

**Specifics to include:**

- **Exact anchors:** the precise `file:line` the work touches.
- **The precise invariant or property to prove** (or, for a verifier, to attack).
- **For a verifier:** the **exact adversarial attack** to run, and the **exact verdict shape** to return.
- Prefer **free-text returns** and self-written files over a rigid schema.

### Annotated example: a builder brief

```
ROLE: Builder. Implement INV-REOPEN on the Tasky status lattice.

ANCHORS:
  - Spec: examples/spec.md, invariant INV-REOPEN (a task dropping below `done` drops every task it
    blocks to at most `in_progress`, recursive over `blockedBy`, cycle-guarded).
  - Legacy rule it replaces: src/events/onTaskReopen.ts:12 (the buried auto-reopen handler).
  - Build into: the new domain module that owns `status` transitions.

PROVE: after any transition that drops a task below `done`, every task reachable via `blockedBy`
  is at most `in_progress`; a blocking CYCLE (A->B->A) terminates and does not infinite-loop.

CONSTRAINTS: max function length 40 lines; fold any shared comparison into one `isDone(status)`
  helper (do not inline `status >= done` in three places, the ratchet will trip).

RETURN (free text): what you built and where (file:line), how you proved INV-REOPEN with a citation
  to the test you wrote, and any spec line you found wrong while building.
DO NOT journal, touch shared state, or commit. I will ground-truth and record.
```

Why it works: the builder cannot guess the wrong invariant (it is quoted), cannot inline the duplication (the
constraint names the ratchet trap), and must return a *cited* proof, not a claim.

### Annotated example: a verifier brief

```
ROLE: Adversarial verifier. Try to BREAK the INV-REOPEN build. You are not here to confirm it.

GROUND IN: a clean checkout. Re-run the suite yourself: `npm test`. Do not trust the builder's run.

EXACT ATTACKS TO RUN:
  1. Build chain A -> B -> C (A blocks B blocks C), advance all to `done`, reopen A; assert B and C
     dropped to at most `in_progress`. If any stayed `done`, that is a FAIL.
  2. Build cycle A -> B -> A; reopen A; assert the cascade TERMINATES (no hang, no stack overflow).
  3. Post-migration, construct a row with `done=true, status=open`; assert the tie-break resolves
     deterministically and the lattice is not corrupted.

VERDICT SHAPE (free text): PASS or FAIL, and for each of the 3 attacks: the command you ran, the
  observed result, and a file:line citation. If FAIL, the minimal reproduction.
DO NOT journal, touch shared state, or commit. RETURN the verdict; I decide "done".
```

Why it works: the verifier has no room to wave it through. Each attack is concrete, the verdict must be cited
per-attack, and the verifier re-runs from clean rather than trusting the builder. This is the shape that catches the
defect the builder talked itself out of seeing.

### Annotated example: a harvest brief

The harvest is run as multi-author + coherence (see [section 3](#3-choosing-an-orchestration-shape)). A harvest brief
must demand BOTH altitudes and force the practical source checks, or the harvester fills the structure and silently
withholds the procedure.

```
ROLE: Harvester. Build the intent ledger for the <area> surface from the legacy.

SOURCES (enumerate ALL copies first): list every tree this area lives in - the live source, any
  vendored copy, doc mirror, and ARCHIVED / COMPRESSED / BACKUP copy (zips, tarballs, backup dirs).
  An "empty" directory is usually a placeholder for archived content: before you call a surface
  unsourced/empty/lost, look inside the archives and back up your claim with a path. A scrub that
  touches one copy and misses the others is not a harvest.

HARVEST AT BOTH ALTITUDES (fill BOTH sections, neither may be left empty):
  - SYSTEM: the shapes, enums, state-machines, capabilities, taxonomy - the structure.
  - PROCESS: the step-by-step procedure one altitude DOWN - the rules, the deadline arithmetic,
    the eligibility gates, the scoring rubrics, the document/pack contents, the per-variant
    differences: what a human or operator actually DOES. The procedure usually lives one read
    deeper than the structure, which is exactly why a sampling pass misses it. Capturing
    "the rule is ADGM => {SPV,TSL,OPCO}" is the enum, NOT the procedure of incorporating an SPV.

PROVENANCE: every claim cites file:line. Carry the risk-surface field (auth / money / crypto /
  multi-tenant-isolation / external-reach).

RETURN (free text): the ledger with BOTH altitudes filled and a DROP-list with a reason per drop.
  An EMPTY PROCESS section means the ledger is incomplete by construction: say so, do not roll it
  up as well-grounded.
DO NOT journal, touch shared state, or commit. I will ground-truth and record.
```

Why it works: the harvester cannot answer "the enum" and stop (the PROCESS section must be filled), cannot quietly
skip an archived copy (the SOURCES line forces the archive/all-copies check before any "empty/lost" claim), and must
return a drop-list with reasons so the distil adversary below has something to re-open.

### Annotated example: a distil adversary brief (run BEFORE "harvest done")

Distil is the one major step that must carry its own adversary, the decision-step analogue of builder +
adversarial-verifier. Before you ever stamp "harvest done", spawn a drop-list adversary. A self-consistent spec can be
uniformly wrong, and a drop-list that is only ever written is where a missed procedure or a skipped secret hides.

```
ROLE: Drop-list adversary. Re-open the cited source and challenge the distil. You are not here to confirm it.

GROUND IN: the actual source ranges (file:line) cited by the ledgers and the spec, NOT the spec's own prose.

DO ALL THREE:
  1. EVERY DROP: re-open the cited source and rule each drop legitimate-REDUNDANCY (verbatim or
     duplicate material, a fine distil) vs negligently-missed-PROCEDURE (a step sequence, rule,
     algorithm, deadline, eligibility gate, or document/pack content whose only home was source
     never opened - a coverage hole wearing distil's banner). The drop-list is no longer write-only.
  2. RETAINED claims (spot-check a sample): check each against its path:line for source-fidelity.
     A self-consistent spec can be uniformly WRONG; the only test is the byte it claims to quote.
  3. SECURITY = COMPLETE, not sampled: walk EVERY external-reach / money / auth surface, not a
     sample (sampling can skip the one file holding a live secret).

VERDICT SHAPE (free text): per drop, REDUNDANCY or MISSED-PROCEDURE with a file:line; per sampled
  retained claim, FAITHFUL or WRONG with the source byte; per security surface, the file walked and
  the finding. Any MISSED-PROCEDURE or WRONG or skipped-secret BLOCKS "harvest done".
DO NOT journal, touch shared state, or commit. RETURN the verdict; I decide whether distil is done.
```

Why it works: dropping redundancy is distil, dropping un-read procedure is a coverage hole, and only re-opening the
source tells them apart. The retained-claim spot-check catches the uniformly-wrong spec, and the complete (not
sampled) security walk catches the one file with the secret. Without this step, distil would be the only major move
with no adversary.

---

## 6. Definition of done (three levels)

"Done" is never a feeling and never a worker's word. It is a checked condition, and it differs by level.

**A beat is done when:**

- [ ] You ground-truthed the result yourself (built, tested, linted from clean; re-proved the load-bearing
      invariant). A subagent's "done" was an input, not the verdict.
- [ ] Anything wrong was fixed (and any security issue fixed the moment it was found).
- [ ] It is committed with **explicit paths** and the co-author trailer.
- [ ] The journal entry, the INDEX pointer, the RESUME pointer, and the task list are all updated (by you, the one
      writer).

**A milestone is done when:**

- [ ] All five close phases ran in order, and the sign-off records, **per phase, the actual command string and its
      actual output** (BUILD, STRUCTURE, SECURITY, VERIFY, PLAN): not "looks fine", but the literal command run and
      the result it returned (e.g. the `vibescan scan` result and, when risk-triggered, the `vibescan .` /
      security-suite output for SECURITY; the closure-gate / `vibeclean` result for STRUCTURE; the `vibetest` result
      for VERIFY). DoD cites tool output (LDD-INV-5).
- [ ] An **independent adversarial verifier** re-ran from clean and failed to break the invariants.
- [ ] PLAN named the next milestone's scope, sequence, risks, and the single next move (the close does not finish
      without this).
- [ ] The sign-off record exists and records all five phases and their evidence.

**The project is done when (BOTH closure legs are clean, not one):**

- [ ] **Leg (a), internal coherence:** the spec audited against itself finds zero gaps (not "the tests pass"): every
      spec surface is built, every declared-but-unbuilt red test is now green, the duplication ratchet holds, the
      structural budgets are met, ids resolve, no cross-doc contradiction, traceability holds.
- [ ] **Leg (b), source -> spec coverage:** a loop-until-dry re-walk of **every harvest source** asking "what
      load-bearing detail lives here that never reached the spec?" found nothing new for K consecutive rounds. Its
      evidence on record is the **source ranges plus the ledger drop-lists**, not the spec (leg (a) cannot see an
      omission, because an omission leaves no contradiction). The coverage bar is "every load-bearing PROCEDURE
      reached the spec", not "every source byte". **A FREEZE/done verdict with no source-coverage sweep on record is
      not done.**
- [ ] Every load-bearing decision is traceable: the journal records why the system is shaped this way, and the
      load-bearing ones graduated to ADRs.
- [ ] Every harvested load-bearing behaviour is either built or explicitly dropped-with-a-reason in the spec.

> The headline rule, one line: **"done" means the orchestrator ground-truthed it and BOTH closure legs are clean -
> internal coherence AND a source -> spec coverage sweep on record.** Internal coherence alone is blind to an
> omission; only the source-coverage leg sees the procedure that was never folded in.

---

## 7. Quick reference card

Hold this in working memory. It is the whole manual compressed to one screen.

```
EVERY BEAT (in order):
  1 ORIENT      read RESUME + last journal entries + task list (= the whole working state)
  2 GROUND      grep / read / run; cite file:line or command output, or you don't know it
  3 PICK        the ONE smallest next move (not three)
  4 ORCHESTRATE spawn the right shape; brief with exact anchors + the invariant (+ verifier's attack)
  5 VERIFY      YOU re-build/test/lint from clean + re-prove the invariant; "done" said by a worker = input only
  6 FIX         fix anything wrong before commit; SECURITY -> fix the instant found, never ask, never commit it
  7 COMMIT      explicit paths only (never add -A) + co-author trailer; one coherent unit
  8 RECORD      journal (what+why+alternatives) + INDEX line + RESUME pointer + task list  [ORCHESTRATOR ONLY]
  9 REPORT      at milestone boundaries, not mid-batch

DECIDE:
  reversible            -> one sentence, build it
  buildable+irreversible-> spike/thin slice BEFORE you commit to it
  hard fork / "working?"-> COURT (ends in a build action or a kill)
  challenged verdict    -> Appeals Court (needs standing)
  "was the method/invariant applied right?" -> Supreme Court (= spec law)
  principal's policy call-> ASK the principal
  security              -> FIX NOW (overrides every schedule)

SHAPES:
  build one thing correctly      -> builder + adversarial verifier
  volume of independent files    -> multi-author + coherence (distinct file owners; never share a file)
  unknown-size discovery         -> loop-until-dry (K consecutive empty rounds)
  judgement under stakes         -> court

GATES (8 per commit; owner of each concern = the matrix in systems.md system 7):
  every commit -> formatter, linter (warnings=errors), type-check, max-fn-length,
                  duplication ratchet (fold, never raise), invariant tests green from clean,
                  security_scan (vibescan scan, the one security owner), structure_scan (vibeclean scan),
                  + red-until-built tests present, clean tree
  milestone    -> BUILD, STRUCTURE (closure-gate + vibeclean scan), SECURITY (vibescan scan continuous +
                  vibescan . at close; deep audit = security suite, vibeaudit engine, risk-targeted),
                  VERIFY (vibetest + independent adversary from clean), PLAN (mandatory)

SUBAGENTS: tell them: don't journal, don't touch shared state, don't commit; RETURN what+why; cite file:line.
           give exact anchors + the invariant to prove (+ for a verifier: the exact attack + verdict shape).
           wave-throttle; free-text returns over rigid schemas.

DONE = orchestrator ground-truthed it AND BOTH closure legs clean:
       (a) internal coherence (ids resolve, no contradiction, provenance, traceability)
       (b) source->spec coverage sweep ON RECORD (loop-until-dry re-walk of every harvest source:
           "what load-bearing detail here never reached the spec?"; evidence = source ranges + drop-lists, NOT spec)
       Leg (a) is blind to an omission; only (b) sees it. No source-coverage sweep on record = NOT done.
       Bar = every load-bearing PROCEDURE reached the spec (not every byte). Never "tests pass". Never "a worker said so".
```

---

## On ADRs

**ADR** stands for **Architecture Decision Record.** It captures **one** significant, hard-to-reverse decision: the
*context* that forced it, the *decision* itself, and the *consequences* (the tradeoffs kept and the ones given up). A
plain journal decision **graduates** into an ADR when it is load-bearing enough that people will need to find and
cite it later, by ID, without scrolling the whole journal. Use [`templates/adr.md`](../templates/adr.md); the worked
one is [`examples/adr/ADR-0001-one-task-status-lattice.md`](../examples/adr/ADR-0001-one-task-status-lattice.md)
(collapsing Tasky's three completion paths into one ordered status lattice). ADRs are append-only as a set: you
supersede an ADR with a new ADR, never edit the old one to flip it.

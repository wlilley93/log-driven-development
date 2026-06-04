---
name: code-review
description: The adversarial code review used in the VERIFY phase of Log-Driven Development. Review a diff (or a set of files) for real correctness bugs, security holes, silent failures, weak type design, comment rot, and inadequate test coverage - each finding evidence-backed with a file:line citation and a confidence score, reported high-confidence-first, never inflated. Run as a fan-out of specialised reviewer lenses whose findings the orchestrator integrates. Use when an independent skeptic must try to BREAK a change before it is called done, before a commit, or before opening a pull request.
---

# Code review (the adversarial VERIFY lens)

> One agent produces; an **independent skeptic tries to break it**. This skill is that skeptic. It reviews a
> change for the defects a builder talks itself out of seeing, returns every finding with a `file:line` citation
> and a confidence score, and reports high-confidence findings first. It does not confirm; it attacks.

This is the **VERIFY-phase** reviewer of Log-Driven Development and the standing *builder + adversarial
verifier* shape applied to code quality and correctness. The builder's "it works" is an **input**, never the
verdict. The reviewer's job is to ground-truth the real tree, re-run the load-bearing checks, and surface what
the build missed. A review with no findings is a *result*, not a goal: it must be earned by genuinely trying to
break the change, not by reading charitably.

## The operating law

1. **Evidence before opinion.** Every finding cites `file:line` (or a command and its output). A claim you
   cannot anchor to the tree is a hypothesis, and you label it as one. No vibes.
2. **No grade inflation.** Score each finding by confidence and report only the ones that clear the bar (see
   *Confidence scoring*). Ten speculative nits bury the one real bug. Quality over quantity, filtered hard.
3. **Name the specific element.** "Improve error handling" is noise. "The `catch` at `api/share.ts:48` swallows
   every error and returns an empty result, so a DB outage looks identical to an empty list" is a finding.
4. **Review advises; the orchestrator decides and fixes.** This skill produces findings and concrete fix
   suggestions. It does not silently rewrite the code (a separate apply step or the `simplify` skill does that).
   The exception is the standing LDD rule below.
5. **A security finding is fixed the moment it is found.** It overrides every schedule. It is never filed for
   later, never committed as-is, never deferred to a follow-up.

## When to invoke

- **VERIFY phase of a milestone close:** an independent adversary re-runs from a clean checkout and attacks the
  milestone's new surface. This is the primary correctness-and-security net, every milestone.
- **Before a commit:** a proactive review of the freshly written diff, to catch defects before they enter
  history.
- **Before opening a pull request:** a full-diff pass so review round-trips are spent on substance, not basics.

## How to run it (the fan-out)

Review is a **fan-out of specialised lenses**, then a single integration. Each lens is an independent reviewer
given the same diff and a narrow mandate; the orchestrator merges their findings, de-duplicates, and decides what
is real. You can run the lenses as separate subagents (the LDD default for a substantive review) or as a single
pass that walks each lens in turn for a small diff.

### Step 1: Establish the scope and ground-truth

- Default scope is the unstaged diff (`git diff`) or the milestone's diff (`git diff <base>...HEAD`). The caller
  may name specific files instead. State the scope at the top of the review.
- **Re-run the load-bearing checks yourself, from clean.** Do not trust the builder's run. Run the formatter,
  the linter, the type-checker, and the test suite from a clean checkout. Record the actual commands and their
  actual output. A green claim you did not reproduce is not evidence.

### Step 2: Run each reviewer lens

Brief each lens with the standing subagent rules (do **not** journal, do **not** touch shared state, do **not**
commit; **return** findings as free text with `file:line` citations). Give it the diff, the relevant invariant or
property it must check, and its lens mandate. The six standing lenses:

**A. Correctness and project-rule reviewer.** The general adversary. Checks the change against the project's own
rules (typically in `CLAUDE.md` or an equivalent contributor guide: import patterns, framework conventions,
error-handling and logging conventions, naming, testing practice) **and** hunts real bugs: logic errors,
null/undefined handling, race conditions and concurrency, off-by-one, resource leaks, type-safety holes, and
security vulnerabilities (injection, broken auth or access checks, secrets in code, SSRF, path traversal,
insecure deserialization). Scores each finding 0-100 and reports only the high-confidence ones.

**B. Silent-failure hunter.** Zero tolerance for errors that vanish. Locate every `try/catch` (or `try/except`,
or `Result`/`Either` handling, or error callback), every fallback and default-on-failure, every place an error is
logged but execution continues, and every optional-chain or null-coalesce that might skip a failing operation.
For each, ask: is the error surfaced and actionable, or hidden? Is the catch specific, or could it swallow
unrelated errors? Is the fallback explicit and justified, or does it mask the real problem? Flag, as defects:
empty catch blocks, catch-log-and-continue, returning null/default on error without logging, and any production
fallback to a mock or stub. Severity: CRITICAL (silent failure, over-broad catch), HIGH (poor or missing error
message, unjustified fallback), MEDIUM (missing context).

**C. Type-design analyzer.** For each new or changed type, identify its invariants (data-consistency rules, valid
state transitions, cross-field constraints, business rules the type should encode) and rate it on four axes,
each 1-10 with a one-line justification: **encapsulation** (are internals hidden, can the invariants be violated
from outside?), **invariant expression** (are the rules visible in the structure, enforced at compile time where
possible?), **invariant usefulness** (do the invariants prevent real bugs, neither too strict nor too loose?),
and **invariant enforcement** (are they checked at construction and at every mutation, so an invalid instance
cannot be built?). Flag the standing anti-patterns: anemic models, types that expose mutable internals,
invariants enforced only by documentation, types with too many responsibilities, missing construction-time
validation. Prefer making illegal states unrepresentable; weigh the complexity cost of every suggestion.

**D. Comment and doc-rot analyzer.** Cross-reference every comment and docstring in the diff against the actual
code: do the documented parameters, return types, behaviour, edge cases, and complexity claims match what the
code does? Flag comments that are factually wrong or misleading (CRITICAL), comments that merely restate obvious
code (recommend removal), and comments that explain *what* where they should explain *why*. Prefer comments that
will not rot as the code changes. This lens advises only; it never edits.

**E. Test-coverage analyzer.** Check that the change's critical paths and edge cases are actually tested, without
being pedantic about 100% coverage. For new branches, validation, parsing, or business logic: are the new code
paths exercised, including the failure and boundary cases? Surface the *critical* gaps (an untested security
check, an untested invariant), not every uncovered line. This is where a declared-but-unbuilt spec surface should
be a visibly failing (red-until-built) test, not a silently absent one.

**F. Invariant-attacker (the load-bearing lens for LDD).** Take the milestone's named invariant from the spec and
**try to construct an input that violates it.** Build the adversarial case the builder did not write: the cycle,
the boundary, the concurrent interleaving, the post-migration tie-break. Run it. A passing invariant test you
*wrote to break it* and could not is real evidence; a green suite the builder shipped is not. This lens is what
catches the defect the builder rationalised away.

> Not every diff needs all six. A pure-types change leans on C and A; an error-handling change leans on B; a
> milestone with a named invariant always runs F. Pick the lenses the change earns, and always include A.

### Step 3: Integrate (the orchestrator)

Merge the lens findings, drop duplicates and confirmed false positives, and assemble one review. The orchestrator
owns this integration (the one-writer rule); the lenses only return text. Re-derive the confidence of any finding
two lenses disagree on by going back to the tree.

## Confidence scoring (the filter that keeps the review trusted)

Rate every candidate finding 0-100, then **report only findings at or above 80** (drop the bar to ~60 only when
the caller explicitly asks for a broad, exhaustive pass and accepts more uncertain findings):

- **0-25:** likely a false positive, or a pre-existing issue the diff did not introduce.
- **26-50:** a minor nit not grounded in a project rule or a real bug.
- **51-75:** valid but low-impact.
- **76-90:** an important issue that needs attention before this is called done.
- **91-100:** a critical bug, a security hole, or an explicit violation of a stated project rule.

A finding you cannot raise above the bar with evidence is dropped or demoted to an explicit hypothesis. This
filter is the whole reason the review is worth reading: it is aggressively pruned to the findings that matter.

## Output format

State the scope first (what diff, what commands you re-ran, with their results). Then, grouped by severity:

```
## Code review: <scope>  (re-ran from clean: <commands + results>)

### Critical (90-100)
- [<confidence>] <file:line> - <specific finding>. Why it matters: <impact>. Fix: <concrete suggestion>.

### Important (80-89)
- [<confidence>] <file:line> - <specific finding>. Why it matters: <impact>. Fix: <concrete suggestion>.

### Type design (if types changed)
- <TypeName> (<file:line>): encapsulation X/10, expression X/10, usefulness X/10, enforcement X/10. <concerns>.

### Invariant attack (if a named invariant is in scope)
- INV-<NAME>: <the adversarial case you built>, <the command you ran>, <PASS or FAIL>, <file:line>.

### Hypotheses (uncertain, not yet evidence)
- <finding> - could not confirm because <reason>; would need <what> to verify.
```

If nothing clears the bar, say so plainly and summarise what you attacked and re-ran, so the caller can see the
review was earned, not skipped. The verdict is **PASS** (nothing blocking) or **FAIL** (at least one blocking
finding), and the orchestrator, not the reviewer, decides whether the milestone closes.

## How this plugs into LDD

- It is the **VERIFY** phase of the [milestone close](../../docs/playbook.md#4b-the-milestone-close-five-phases):
  an independent adversarial verifier, every milestone, re-running from clean and attacking the new surface.
- It implements the **builder + adversarial verifier** shape from the
  [methodology](../../docs/methodology.md#5-the-orchestrated-agent-shapes): the verifier's verdict is the
  orchestrator's input, not the final word.
- Its findings feed back into the build: a correctness or security finding is fixed before the milestone closes
  (security the instant it is found), and a quality finding is handed to the [`simplify`](../simplify/SKILL.md)
  pass.
- It is one half of the two-tier quality gate. The other half, the continuous per-commit
  [closure-gate](../../tools/closure-gate/README.md), catches structural drift mechanically so this human-grade
  review can spend its attention on correctness, security, and design rather than on formatting.

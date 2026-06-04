# The closure-gate (runnable continuous structural enforcement)

This directory is the **runnable** form of LDD's closure-gate: the continuous structural
enforcement that runs on every commit and decides, mechanically, whether the tree is
clean. It mechanises the discipline described in
[`docs/methodology.md`](../../docs/methodology.md) ("The closure-gate") and the contract
template at [`templates/closure-gate.config.md`](../../templates/closure-gate.config.md).

Stand it up **before the walking skeleton**, so "clean" is checkable from the first line
of the rebuild. The whole point: **"done" means this sweep is clean, never "the tests
pass" alone.**

## What is here

| File | What it is |
|---|---|
| `closure_gate.py` | The orchestrator. Runs every gate in order and denies (exit 1) if any fails. |
| `duplication_ratchet.py` | The load-bearing gate: a cross-module duplication budget you may only HOLD or LOWER (never raise). |
| `max_function_length.py` | The max-function-length deny gate: a long function hides duplication and God-objects. |
| `closure-gate.toml` | The machine-readable config (your stack's commands + the two portable thresholds). |
| `pre-commit` | An example git pre-commit hook that runs the gate on every commit. |

The two Python scripts are **language-agnostic and dependency-free** (Python 3.8+, no
third-party packages). They run on any project out of the box. The orchestrator shells
out to **your** stack's real formatter, linter, type-checker, and test commands, plus the
two continuous suite gates (`security_scan`, `structure_scan`), which you wire in
`closure-gate.toml`.

## The gates (in order)

1. **Formatter** clean (deny on fail) - no formatting noise in diffs.
2. **Linter**, warnings-as-errors (deny on fail) - the obvious class of defect, caught before review.
3. **Type-check** clean, if the language has one (deny on fail).
4. **Max-function-length** (deny over the limit) - `max_function_length.py`.
5. **Duplication ratchet** (deny over budget) - `duplication_ratchet.py`. The load-bearing one.
6. **Tests** green from a clean checkout (deny on fail).
7. **Security-scan** (`vibescan --fast`) - the ONE security owner at this tier: secrets +
   dependency CVEs + a fast SAST pass in one. It subsumes the old separate supply-chain /
   dep-CVE gate.
8. **Structure-scan** (`vibeclean --changed`) - the richer AI-slop / god-file / duplication
   scanner the per-commit ratchet shells out to.

Gates 1-3 and 6 are your project commands (blank = skipped, and a skipped gate is
*reported* as skipped, never silently absent). Gates 4-5 are the portable scripts. Gates
7-8 are the continuous edge of the security and refactoring suites, defaulted ON to the
vendored vibe* tools (`../vibe`): a missing tool is a LOUD skip (exit 127 = warn with an
install hint, never a silent absence and never a hard deny).

> Red-until-built tests (a failing placeholder for every spec surface declared but not yet
> built) are part of the closure-gate contract too, but they live in **your test suite**
> (so an unbuilt surface is visibly red), so the "tests" gate above covers them. See the
> config template for how to track them.

### Scope: gate what you own, not what you consume
The portable checks (4-5) never police consumed-commodity trees. Build/cache dirs
(`node_modules`, `dist`, `.venv`, ...) are always excluded; for vendored or generated code
you own-but-did-not-author, list it under `[scope] exclude` in the config (comma-separated
path globs; a bare `a/b` prunes that subtree). This is the consume-the-commodity boundary
made checkable: you gate your differentiating code, not code you merely vendored. (This repo
vendors the vibe* tools under `tools/vibe`, so its own config excludes them.)

### Files
- `closure_gate.py` - the orchestrator (runs every gate, prints the summary, exit 1 on any deny).
- `max_function_length.py`, `duplication_ratchet.py` - the two portable, zero-dep checks.
- `_common.py` - the single home for the shared file-walk, significance test, and config reader.
- `tests/` - the gate's own stdlib-unittest suite (`python3 -m unittest discover -s tools/closure-gate/tests`);
  the code that enforces "tests pass" is itself tested.

## Quick start

From your repo root, with this directory vendored at `tools/closure-gate/`:

```bash
# 1. Copy the config and wire YOUR stack's commands (uncomment one [commands] block).
cp tools/closure-gate/closure-gate.toml ./closure-gate.toml
$EDITOR ./closure-gate.toml

# 2. Seed the duplication budget ONCE on the walking skeleton (records the current value).
python3 tools/closure-gate/duplication_ratchet.py --config ./closure-gate.toml --update-budget src/

# 3. Run the whole gate.
python3 tools/closure-gate/closure_gate.py --config ./closure-gate.toml --paths src/

# 4. Install the commit hook (or call closure_gate.py from your hook manager / CI).
cp tools/closure-gate/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```

Run the **same** `closure_gate.py` command in CI as locally, so "green on my machine"
cannot diverge from "green from a clean checkout".

## The duplication ratchet (the discipline, not just a number)

The budget in `[duplication] budget_percent` is **the number you last closed at**. The
rule, stated once:

- `--check` (the default, used by the gate) **denies** if the measured duplication exceeds
  the budget.
- `--update-budget` **lowers** the stored budget to the current value when you have folded
  duplication, and **refuses to raise it**. Raising the number concedes the sprawl the
  gate exists to delete. If you genuinely must accept new duplication (a large vendored
  import, say), edit the config by hand and journal the reason, so the concession is on
  the record rather than hidden in a passing commit.

When a change trips the ratchet, you **fold** the duplication into one shared function;
you do not move the line. (In the running task-tracker example, inlining the `status >=
done` comparison in the list, the board, and the shared view trips the ratchet, and the
fix is to fold all three into one `isDone(status)` helper. That single fold is what stops
a *fourth* way to complete a task from ever appearing.)

### How the portable scanner measures duplication

`duplication_ratchet.py` normalises whitespace, ignores blank and comment-only lines,
hashes every window of `min_lines` consecutive significant lines, and reports the fraction
of significant lines that sit inside a window appearing in two or more distinct locations.
It is a portable approximation of a clone detector, deliberately dependency-free so the
gate runs everywhere.

For a heavier, AST-aware scan, run a real clone detector (for example `jscpd`, PMD's
`cpd`, or `simian`) and feed its percentage to the ratchet so the hold-or-lower discipline
still applies:

```bash
DUP=$(jscpd src --min-lines 5 --min-tokens 30 --reporters json --silent && \
      jq '.statistics.total.percentage' jscpd-report.json)
python3 tools/closure-gate/duplication_ratchet.py --config ./closure-gate.toml --measured "$DUP" --check
```

## How the max-function-length gate measures length

`max_function_length.py` finds function and method definitions across common brace
languages (JS/TS, Rust, Go, Java, C/C++, C#, Kotlin, Swift, PHP) and indent languages
(Python), then counts the **significant** body lines (blank lines and whole-line comments
excluded). It is a portable heuristic, not a full parser. Where your linter has a native
rule (ESLint `max-lines-per-function`, Clippy `too_many_lines`, and so on), enable it too
and add it to the `lint` command; this script is the portable floor that runs even where
no such rule is configured.

## Tuning and tightening

Tighten the two thresholds over time, **never loosen them**:

- `[function] max_lines` - lower it as the codebase proves it can hold a tighter limit.
- `[duplication] budget_percent` - lower it every time you fold duplication; the
  `--update-budget` flag does this and refuses to go the other way.
- `min_lines` - the smallest run of identical significant lines that counts as a clone
  (default 5). Lower it to catch smaller clones, raise it to reduce false positives on
  boilerplate.

Both portable scanners take explicit `--paths`, so you can scope them to `src/` and keep
generated code, vendored code, and fixtures out (the default exclude list already skips
`node_modules`, `dist`, `build`, `target`, `vendor`, `.venv`, and the like).

## How this plugs into LDD

- It is **Tier 1** of the two-tier(+) cadence: continuous, per-commit, mechanical. For what
  each Tier-2 heavy pass owns (deep security reasoning, the full refactor round, the
  adversarial verifier), see the two-tier(+) ownership matrix in
  [`../../docs/systems.md`](../../docs/systems.md) (system 7), the single source of truth for
  one-owner-per-concern (LDD-INV-9). Because Tier 1 runs on every commit, the **STRUCTURE**
  phase of a milestone close becomes a light *scan* for what slipped rather than the primary
  enforcement, and the heavy [refactoring](../../skills/refactoring/SKILL.md) round is
  reserved for flagged debt.
- It enforces **consolidation over fragmentation**: the ratchet is exactly what stops the
  rebuild re-growing the duplicated mechanism it was escaping. The portable duplication
  ratchet (gate 5) is the OWNER of the per-commit duplication budget; `vibeclean` (gate 8)
  is the richer scanner that cites it, never a second independent budget (per the matrix).
- The human-grade review skills ([`code-review`](../../skills/code-review/SKILL.md) for
  correctness and security, [`simplify`](../../skills/simplify/SKILL.md) for quality) sit
  alongside it: the gate holds the structural budgets mechanically so the reviewers can spend
  their attention on judgement, not formatting.

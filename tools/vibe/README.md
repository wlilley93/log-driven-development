# The vibe* tools - the coded gates of LDD

These are the runnable command-line tools that mechanise the LDD quality and security gates. The methodology
(see `skills/log-driven-development`) describes the gates abstractly; these tools are how an agent actually
executes them on a real tree. They are vendored here in full so the kit is self-contained (the whole operating
model in one place), and each is also an independent MIT-licensed package you can `pip install`.

Every tool follows the same shape: it orchestrates best-in-class open-source analyzers, normalises their output
into one Finding schema, deduplicates overlap, and returns a single pass/fail verdict suitable for CI gating.
None of them needs configuration to start.

## The tools

| Tool | What it does | LDD phase it serves |
|---|---|---|
| **vibescan** | Security scanner. Orchestrates ~13 OSS security tools (secrets, SAST, dependency CVEs, IaC, licences) in parallel, dedups, one verdict. | SECURITY: the fast edge (`vibescan scan`) is the continuous per-commit owner via the closure-gate `security_scan` gate; full `vibescan .` runs at push/CI and milestone-close. See the ownership matrix in `../../docs/systems.md` (system 7). |
| **vibeaudit** | Deep security auditor. The heavier, evidence-extracting pass behind vibescan for high-risk surfaces. | SECURITY: the scanner engine of the security-suite deep methodology (`skills/security/`), Tier 2 risk-triggered, NOT a parallel auditor. See the matrix in `../../docs/systems.md` (system 7). |
| **vibetest** | Test-quality auditor (not a runner). Statically finds missing tests, weak assertions, test smells, flakiness, coverage gaps. | VERIFY (alongside the adversarial verifier) |
| **vibeclean** | AI-slop and hygiene detector. Catches the spaghetti, dead code, and mess that LLM-assisted coding produces. | STRUCTURE (alongside the refactoring suite) |
| **viberapid** | Performance analyser. Orchestrates ~65 perf tools across 13 categories, computes quick wins, checks perf budgets. | STRUCTURE / SECURITY (perf budget, as needed) |
| **vibedeploy** | Pre-deploy readiness analyser (SSL/headers/CORS/secrets/config) with a ship-safe gate. | release readiness (as needed) |

## How the LDD process invokes them

The five-phase milestone close (`skills/log-driven-development`) wires to these tools:

- **STRUCTURE** runs `vibeclean .` over the new surface (and the refactoring suite when it flags real debt).
- **SECURITY** has two cadences for one owner: the continuous per-commit owner is `vibescan scan` (the
  closure-gate `security_scan` gate, which catches secrets + dependency CVEs + a fast SAST pass on every commit),
  and the milestone-close runs the full `vibescan .` sweep over the whole tree. On a high-risk surface (auth,
  money, crypto, multi-tenancy, any externally-reachable entry point) it escalates to the security-suite
  methodology (`skills/security/`), with `vibeaudit` as that methodology's scanner engine, not a parallel pass.
- **VERIFY** runs `vibetest .` to audit the tests the build added, alongside the independent adversarial verifier.
- The **closure-gate** (`tools/closure-gate`) is the continuous, per-commit tier; these tools are the milestone
  gates that catch what a single surface scan would miss. Which tool owns which concern at which cadence is the
  two-tier(+) ownership matrix in `../../docs/systems.md` (system 7); this section maps to it, it does not restate it.

A tool that returns a non-zero verdict blocks the milestone close, exactly like a failing test.

## Running them

Each tool is a standalone Python package. Two ways to run:

```bash
# Option A - install from PyPI (each is published independently):
pip install vibescan vibeaudit vibetest vibeclean
vibescan install && vibescan .          # vibescan installs the OSS scanners it orchestrates

# Option B - run from this vendored copy (no PyPI dependency):
cd tools/vibe/vibescan && pip install -e . && vibescan .
```

Each tool exits non-zero when it finds blocking issues, so they drop straight into a CI gate or a pre-commit hook.

## Licence

All of the vibe* tools are MIT-licensed (see each tool's `pyproject.toml`).

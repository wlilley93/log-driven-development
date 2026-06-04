# Preflight wave (shared infrastructure)

Reused by both `create-refactor-plan` (NORMAL mode) and `structural-sweep` (STRUCTURAL_SWEEP mode). Run before
per-module review or per-batch dispatch so agents reason against concrete tool findings, not just code reading.

## Why this exists

A single-pass LLM review has known blind spots: AST-detected IDOR / mass-assignment / auth-bypass patterns,
multi-file exploit chains, claim-versus-code drift, CVE-pinned dependency posture, and compliance control gaps.
Tools find these deterministically and reliably; LLMs miss or under-prioritise them. Conversely, tools miss
business-logic flaws and semantic drift the LLM catches. Run both, dedupe, feed the union into the next phase.

## 4a. Deterministic wave (parallel, ~10 min)

Dispatch concurrently. Each writes a structured artefact under `preflight/`. The three `vibe*` scanners are coded
tools; runnable cleanroom reference implementations ship under `tools/refactoring/`. If a tool is unavailable,
write a stub artefact noting the skip; do not block the wave.

| Tool | Command | Output | Catches |
|---|---|---|---|
| vibescan | `vibescan {repo_root}` | `vibescan.json` | CVEs, secrets, SAST. Aggregates a panel of open-source scanners (secret scanners, SAST engines, dependency/vuln scanners, IaC scanners, license checks) into one normalized report. |
| vibeaudit (static) | `vibeaudit scan {repo_root}` | `vibeaudit-static.json` | AST patterns: IDOR, mass-assignment, auth-bypass shape, race-condition skeletons. |
| vibeclean | `vibeclean scan {repo_root} --output json --output-file vibeclean.json` | `vibeclean.json` | Atomization debt: complexity (cyclomatic, function/file length), duplication, dead code, naming conventions, slop (redundant comments, over-abstraction). This is the deterministic atomization-finding source; LLM module review supplements but does not replace it. |
| compliance audit | `{project-specific audit script}` | `compliance.txt` | Authn/authz, CSRF, audit logging, encryption, retention controls (ripgrep-driven). Project-owned; see 4a-lazy. |
| typecheck | `{typecheck command}` | `typecheck.txt` | Type-level errors. |
| lint | `{lint command, JSON format}` | `lint.json` | Lint violations. |
| schema | `{schema validate command}` (when applicable) | `schema-validate.txt` | Schema integrity. |
| dep audit | `{dependency audit command, JSON}` | `dep-audit.json` | Dependency CVEs (vibescan also covers; keep raw for cross-check). |
| control-plane-scan | project-specific ripgrep/script | `control-plane-scan.txt` | Copied auth, permission, tenant, status, validation, schema, API-client, logging/audit, retry, and error-handling policy that should use a shared source of truth. |
| ui-token-drift | project-specific ripgrep/script | `ui-token-drift.txt` | Raw styling, inline style, arbitrary utility classes, radius drift, token bypass. Tune per project to avoid false-positive token definitions. |
| ui-state-scan | project-specific AST/ripgrep/script | `ui-state-scan.txt` | Components that fetch or mutate data but have no detectable loading/empty/error/retry/permission/mobile state handling. Prefer a real AST scanner; ripgrep heuristics are only triage. |
| ui-vv-smoke | project-specific command (e.g. browser-driver screenshots + accessibility checks on changed routes) | `ui-vv-smoke.txt` + screenshots/traces | Visual render, responsive layout, accessibility smoke, route-level crash checks for UI overhaul rounds. |

For non-frontend projects, skip the `ui-*` tools with a stub. For frontend or UI overhaul rounds, treat missing
`ui-*` artefacts as a coverage gap in `findings.md`, not as proof of absence. Deterministic UI scanners are
intentionally noisy; they produce candidates that 4b/Step 5 must validate against the real design system and
accepted handovers.

**Deep security reasoning is owned by the security suite, not by this preflight.** `skills/security/` is the single
owner of deep security reasoning, and it has its OWN front doors that are reachable at harvest and bootstrap, not
only via a refactor preflight round: its standalone audit, release-gate, and incident playbooks are direct entry
points. The `vibescan` and `vibeaudit` rows in the wave above are the refactoring suite's BOUNDED dispatch INTO
that owner, not a parallel security pass: `vibescan` is the scanner whose findings feed `findings.md`, and
`vibeaudit` is the scanner ENGINE of the security-suite methodology (see 4b.2 below), never a second independent
auditor (LDD-INV-9, ldd-security G-5). See the two-tier(+) ownership matrix in `docs/systems.md` (system 7).

## 4a-lazy. Lazy initialization of project-specific security infrastructure

Run BEFORE the deterministic wave dispatches its compliance step. Detects whether the project has the
security-suite-generated artefacts it needs; if not, offers to generate them on first preflight.

```bash
PROJECT_NAME=$(basename "$(pwd)")
SECURITY_AUDIT_SKILL="<overrides-root>/security-audit-$PROJECT_NAME.md"
COMPLIANCE_SCRIPT="scripts/audit-compliance.sh"

if [ ! -f "$COMPLIANCE_SCRIPT" ] && [ ! -f "$SECURITY_AUDIT_SKILL" ]; then
  echo "[preflight] No project-specific security infrastructure detected."
  echo "[preflight] Options:"
  echo "  (a) generate now (Tier-2, ~5-10 min) - produces the project-specific security-audit skill"
  echo "  (b) skip for this round - methodology dispatch runs the neutral methodology only"
  echo "  (c) configure permanently as 'no compliance obligations' - sets PREFLIGHT.SECURITY_SUITE_REQUIRED: false"
  echo ""
  echo "If preflight is running unattended, the default is (b) skip with degraded methodology coverage."
fi
```

When the user picks (a), dispatch the security-suite generator agent. It reads the security suite's generator and
neutral methodology, inspects this project's auth/CSRF/encryption/audit-logging code, and writes the
project-specific audit skill (the project-specific layer that pairs with the neutral methodology). The generator
produces ONLY the audit skill, not the compliance ripgrep scripts: those encode tribal threat-model knowledge
specific to each codebase's auth/tenancy/encryption patterns, so they remain project-owned (human-authored, or
LLM-authored then human-reviewed). After generation, the refactor preflight updates its OWN overrides file (it
owns `refactoring-overrides.md`; it should not delegate that to the security-suite generator): confirm
`PREFLIGHT.COMPLIANCE_AUDIT` if a compliance script exists, and note that the project-specific audit skill now exists so
methodology dispatch in 4b will use it.

After the generator completes, subsequent preflight runs skip 4a-lazy (the artefact exists) and dispatch normally.
For projects without compliance obligations, option (c) sets a permanent override flag; future preflights skip the
check. Do not generate audit infrastructure for compliance you do not have. Why lazy, not bootstrap-time: the
security-suite generator is owned separately. Bootstrapping a refactor project should not transitively bootstrap an
unrelated suite; that couples concerns. Letting preflight detect the gap and offer to fill it keeps the suites
independent while still making the new-project experience seamless.

## 4b. LLM wave (parallel-by-module or sequential, ~1-3 hours)

Up to four agentic passes. Slow, but they catch what the deterministic wave misses; dispatch the control-plane and
UI V&V passes only when the round scope warrants them.

**1. Deep agentic scan** (`vibeaudit ... --deep`)

```bash
# Interactive session: delegate triage to the local model CLI, no API spend.
vibeaudit scan src --deep --provider <local-cli> --skip command_injection > preflight/vibeaudit-deep-src.md
vibeaudit scan app --deep --provider <local-cli> --skip command_injection > preflight/vibeaudit-deep-app.md

# CI / non-interactive only: a paid API path with a budget cap.
# vibeaudit scan {repo_root} --deep --provider <api> --model <mid-tier> --budget 5.00 > preflight/vibeaudit-deep.md
```

This deep agentic scan and the security-suite methodology dispatch (4b.2) are ONE deep-security pass with ONE
owner, not two: `vibeaudit` is the scanner ENGINE of the security-suite methodology (`skills/security/`), and the
methodology is the deep-security owner that reasons over its output. They are staged together (the scan warms the
context the methodology reasons over), never run as two competing audits (LDD-INV-9, ldd-security G-4 / G-5;
matrix row "Deep security reasoning" in `docs/systems.md` system 7).

An agentic LLM autonomously explores the codebase, traces middleware chains, and reads multiple files per finding.
Best for multi-file business-logic vulnerabilities the static pass cannot see end to end. Prefer the local-CLI
provider for interactive sessions: it inherits the running session's project context and incurs no per-call API
spend. Use a paid API provider only when running outside an interactive session (CI, scheduled jobs). **Always
scope** the scan to source and app directories separately rather than the repo root: worktree-littered repos
(`.worktrees/`, build output, vendored `node_modules`) inflate the candidate-region count roughly 10-15x and on
large repos can hang the static extraction pass for tens of minutes. Skip `command_injection` unless explicitly
hunting it; it is the false-positive-dominant class on many stacks.

**2. Security-suite methodology dispatch** (Tier 2)

Dispatch logic depends on whether the project has a project-specific audit skill (from 4a-lazy). If the
project-specific security-audit skill exists, dispatch against it (it imports the neutral methodology and adds the
project-specific layer: reasoning over this codebase's auth, tenancy, and identity model). If not, dispatch against
the neutral methodology only; findings will be less project-specific but the structure is the same. The agent runs
a structured reasoning pass (threat model, chokepoint sweep, claim-versus-code, tenant isolation, secret discovery,
compliance gaps) and writes findings to `preflight/methodology.md`. For large codebases, parallelise by section
across worktree subagents (each section is independently reasonable); for small codebases, run as a single
sequential agent.

**3. Control-plane methodology dispatch** (Tier 2)

Dispatch when `control-plane-scan.txt` has candidates, cross-cutting findings exist, or a round goal mentions
architecture/consolidation. This subagent decides whether repeated logic should become a shared "bus" or stay
local. It reads the control-plane scan, the features-list dependency graph and module ownership, shared
service/client/schema/auth/logging directories, related tests, and public API snapshots. It writes
`preflight/control-plane-methodology.md` with findings grouped as:

- `B-missing`: shared policy copied in 3+ sites and suitable for centralization.
- `B-split`: multiple helpers/schemas own the same policy with different semantics.
- `B-leaky`: the shared helper exists but callers still reproduce policy details.
- `B-god`: the central layer absorbs feature-specific behavior and should be split back out.

The subagent must justify why a proposed bus is stable shared policy, not feature-specific behavior. Good fixes
centralize auth, permission, validation/schema, API-client, logging/audit, feature-flag, status, retry, and error
policy; they do not create a single god object for everything.

**4. UI overhaul V&V methodology dispatch** (Tier 2)

Dispatch when any of these is true: the round goal mentions UI/visual/design overhaul, changed files include
components/styles/routes, design handovers exist, or `ui-*` deterministic artefacts contain findings. It reads
accepted design handovers or screenshots (if present), UI architecture / design-token docs (if present), the three
`ui-*` artefacts, and changed routes/components and their tests. It writes `preflight/ui-vv-methodology.md` with
findings grouped as:

- `U-state`: missing loading/empty/error/retry/permission/stale/mobile/long-content states.
- `U-token`: raw styling or token/control-plane bypass.
- `U-primitive`: duplicated local tables/modals/buttons/loaders/forms instead of shared primitives.
- `U-boundary`: data fetching, validation, permissions, persistence, or business rules embedded in render components.
- `U-visual`: screenshot/accessibility/responsive mismatch against the accepted handover.

The reviewer must distinguish "deterministic scanner candidate" from "confirmed issue" and include file paths,
route/screen name, viewport, and command/screenshot evidence when available.

## 4c. Dedupe + module-tag + write findings.md

Aggregate every artefact from 4a + 4b into a single `preflight/findings.md`. Each finding gets:

| Field | Source |
|---|---|
| `id` | Stable hash of (file + line + rule) for cross-round dedup. Hash on file/line/rule only, NOT message: tool messages drift across versions but the underlying issue stays. |
| `source` | `vibescan` / `vibeaudit-static` / `vibeaudit-deep` / `methodology` / `compliance` / `typecheck` / `lint` / `schema` / `dep-audit` / `control-plane-scan` / `control-plane-methodology` / `ui-token-drift` / `ui-state-scan` / `ui-vv-smoke` / `ui-vv-methodology` / `deferred-ledger` |
| `severity` | Tool's native severity, normalised to 0.0-10.0 using the scoring table in `formats/features-list-format.md`. |
| `file` | Path (or list of paths if cross-cutting). |
| `line` | Line number (or range, or `n/a` for cross-cutting). |
| `module` | Path-prefix routed against the features-list `Touches` column. If the path matches multiple modules, attach to the most-specific. If no match, `unrouted` (triage manually before dispatch). |
| `cross_cutting` | `true` if the finding touches files in 3+ different modules (e.g. a CSRF gap across 5 routes, a missing validation pattern in 7 handlers). Cross-cutting findings get routed to a synthetic `platform` module rather than fragmented across each affected module. |
| `description` | Tool's message + any cross-source corroboration. |
| `schema_migration` | `true` if the proposed fix touches the schema file or any migration script; surfaces in the close-checklist. |

**Dedup rules:** identical `(file, line, rule)` from multiple sources collapse into one finding with a
`corroborated_by: [...]` array. Disagreement on severity escalates to the higher value.

**Cross-cutting detection:** scan all findings for the same `rule` appearing in files owned by 3+ different
modules. Replace the per-module instances with a single `cross_cutting: true` finding under module `platform`,
listing all affected files in the `file` field. Keep the original module-tagged instances as a
`decomposes_into: [...]` array for traceability, but the platform finding is what gets atomized in 4d. This
catches: CSRF gaps across N routes, missing validation patterns across N handlers, addon-gating drift,
error-handling shape inconsistency. These are the findings that previously got re-discovered per-module instead of
fixed once at the platform layer.

Sort `findings.md` by severity descending within each module.

## 4d. Draft per-module fix-prompts (atomization head-start)

(NORMAL mode only; STRUCTURAL_SWEEP has its own per-batch dispatch in S2/S3.)

For each module with one or more findings, dispatch a Tier-2 agent that reads the module's slice of `findings.md`
and writes `preflight/<module>/draft-fix-prompt.md`. This front-loads atomization to preflight: the agent does NOT
read code (it has only findings), so it produces draft fixes that the validation phase then verifies against the
actual codebase. The draft uses `formats/fix-prompt-format.md`, with these constraints:

- One fix per finding (or one fix bundling 2-3 corroborated findings on the same root cause).
- `Fix:` uses tool/methodology hints when present (vibescan + vibeaudit findings often suggest remediations);
  otherwise the agent proposes a fix from finding context.
- Mark `Confidence:` per fix: `high` (clear-cut, adopt verbatim), `medium` (likely correct but needs code
  verification), `low` (drafted blind, expect the validation phase to rewrite).
- Sequencing respects the dependency graph from features-list.md. Findings touching shared upstream files block
  downstream module fixes.
- Rollback + Result schema: leave as templated placeholders; the validation phase fills in commit hashes during execution.

The agent receives the module's slice only, no codebase view. This is intentional: the value of front-loading
atomization is parallel scaling. Many modules' draft prompts can be generated concurrently while the heavy LLM-wave
preflight still runs. The validation phase then has both the findings AND a structured draft to review, so its work
shrinks to "diff the draft against code, fix what's wrong, finalize." If a module has zero findings, skip the
draft; the validation phase operates as a full review pass instead.

## Performance / cost notes

Total preflight wall-clock is dominated by the LLM wave (1-3 hr). On the cache-warm side, the deep agentic scan
shares prompt cache with the methodology agent if you stage them in sequence rather than in parallel (the deep scan
first warms the cache). For first-round runs, accept the wall-clock; for follow-up rounds, skip preflight entirely
if no commits have landed since the last round (compare HEAD against the previous round's `git-log.txt` baseline).
The 4d draft generation is fast (~30s per module, parallelizable) and adds negligible time relative to 4a + 4b.

Token cost (estimates with a mid-tier model for Tier 2, prompt-cache hot):
- 4a deterministic wave: $0 (no LLM).
- 4b deep agentic scan: a few dollars to ~$15 per repo.
- 4b methodology: a few dollars per repo (cache-warm subsequent rounds drop to well under a dollar).
- 4d drafts: cents per module.

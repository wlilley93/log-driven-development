# Refactoring overrides template

This file documents the per-project override schema. Each project that uses the refactoring suite gets its own
`refactoring-overrides.md` under `<overrides-root>/`. The template playbooks (`create-refactor-plan`,
`run-refactor`, `verify-refactor`, `structural-sweep`) read these overrides at runtime and substitute
project-specific values into the codebase-neutral procedure.

## Why this split exists

The *methodology* of refactoring (preflight, atomization, wave dispatch, drift detection, deferred ledger) is
portable. The *mechanics* (which test command, which deploy gate, which architecture-spec directory) are
project-specific. Forking the entire skill per project means template improvements do not propagate. Inlining
everything in the template means the template lies for any project that does not match one canonical stack.
Overrides are the seam.

## Schema

The overrides file is a single markdown document with the sections below. Every section is optional; if absent,
the template's default applies. The template defaults assume a Node/TypeScript stack (a JS test runner, an ORM
with a schema file, a typed build) purely because *some* concrete default is needed; change them if your project
differs.

### Identity

```markdown
## Project identity
- **Name:** <project name>
- **Repo root:** <absolute path>
- **Stack:** <one-liner: language / framework / ORM / etc.>
- **Refactor docs root:** <e.g. docs/refactoring/>
- **Architecture specs glob:** <e.g. docs/architecture/*.md>
```

### Build + test commands

```markdown
## Commands
- **Test (full):** <e.g. npm run test:run / go test ./... / pytest>
- **Test (per-module fast loop):** <e.g. npm run test:run -- <path>>
- **Test (related selector):** <e.g. npx vitest run --related>
- **Test (single):** <e.g. npx vitest run>
- **Lint:** <e.g. npm run lint -- --format json>
- **Type check:** <e.g. npx tsc --noEmit / mypy / go vet>
- **Schema validate:** <e.g. the schema engine's validate command>
- **Build:** <e.g. npm run build>
- **Install:** <e.g. npm install>
```

### Schema-migration deploy gate

```markdown
## Schema migration
- **Local migration:** <e.g. the schema engine's apply command>
- **Prod migration:** <full deploy-time command, including version pinning>
- **Rollback path:** <e.g. point-in-time recovery within the recovery window>
- **Migration runner pin reason:** <why the runner version is pinned, if it is>
```

Pin the migration runner version to the deployed runtime version, not the manifest version; auto-resolved runner
versions have shipped breaking changes mid-round.

### Preflight tool dispatch

```markdown
## Preflight tools
- **vibescan:** [enabled | disabled] - reason if disabled
- **vibeaudit:** [enabled | disabled] - default the local-CLI provider for interactive sessions (no API spend).
  Override only for CI / non-interactive. Always scope scans to source + app dirs separately; full-tree runs are
  killed by worktree / build-output / vendored-dependency pollution.
- **vibeclean:** [enabled | disabled] - atomization/duplication/slop detector. Default enabled. Skip selected
  runners if a runner produces too many false positives for the codebase.
- **Security-suite methodology:** [enabled | disabled]
- **Project-specific compliance audit:** <command, e.g. bash scripts/audit-compliance.sh>
- **Additional project-specific scanners:** <list of any custom audit/check scripts>
```

### Deploy + post-deploy verification

```markdown
## Deploy
- **Deploy command:** <project deploy command>
- **Smoke check command:** <a curl/health-check that confirms the deploy is live>
- **Post-deploy logs:** <how to read prod logs>
- **Rollback command:** <how to roll a bad deploy back>
```

### Drift-detection paths

```markdown
## Drift detection
Files whose changes between rounds auto-flag a module for re-review:
- **Module index source:** <which file's module-index table to diff; default the architecture-overview doc>
- **Architecture specs:** <glob pattern>
- **Additional drift paths:** <repo-specific files that signal architectural change>
- **Snapshot location:** <where to write per-round snapshots; default <refactor-docs-root>/round-N/snapshot.md>
```

### Project-specific learnings

```markdown
## Learnings
Append-only list of project-specific gotchas the refactor preflight should encode. Each entry: title, date, brief
description, which preflight wave or step picks it up.

### YYYY-MM-DD: <title>
<2-4 sentence description. What surfaced, where, what to look for in future rounds.>
**Encoded in:** <e.g. "Step 4 deterministic wave > <a specific guard test>">
```

These are the lessons that do not fit anywhere else (for example: a count or invariant that must reconcile across
N docs after every round, encoded as a CI guard; "schema-touching deploys need an explicit migration step,"
encoded as the Step 9 close-checklist; a sync hazard between an external store and the repo, encoded as
commit-cadence guidance).

### Module-specific knobs

```markdown
## Module knobs
| Module | Custom test path | Custom drift signals | Notes |
|---|---|---|---|
```

When a module has unusual review needs (special attention to a ledger column's drift; a check for orphaned storage
keys; etc.), record them here so each round's preflight knows.

## How the template uses overrides

Template playbooks use HTML-comment markers at hook points:

```markdown
<!-- OVERRIDE: COMMANDS.TEST -->
npm run test:run
<!-- /OVERRIDE -->
```

At runtime, the playbook reads the template, then the overrides file (if it exists). For each
`<!-- OVERRIDE: KEY -->` block, look up `KEY` in the overrides file. If found, substitute; if not, use the inline
default. Marker keys follow `SECTION.SUBKEY` form. Defined keys:

| Key | Source section | Inline default |
|---|---|---|
| `MODELS.TIER_1` | Model tier | a small/local model |
| `MODELS.TIER_2` | Model tier | a mid-tier reasoning model |
| `MODELS.TIER_3` | Model tier | a top-tier reasoning model |
| `MODELS.LOCAL_BIN` | Model tier | (none; Tier 1 routes to the small hosted model unless set) |
| `MODELS.LOCAL_MODEL` | Model tier | (none) |
| `DISPATCH.WAVE_SIZE` | Coordination | `6` |
| `DISPATCH.WORKTREE_PATH` | Coordination | `.worktrees/round-N/` |
| `TRACKER.WORKSPACE` | Coordination | (none; projection disabled) |
| `TRACKER.PROJECT_ID` | Coordination | (none) |
| `TRACKER.NORMAL_PROJECTION_ENABLED` | Coordination | `false` |
| `REVIEW.SKIP_HIGH_CONFIDENCE_LOCAL` | Reviewing agent | `false` (review every fix; set true to skip review for high-confidence local fixes only) |
| `TELEMETRY.COST_LEDGER_PATH` | Cache telemetry | (none; degrades gracefully) - a command/script that aggregates per-round model cache stats from the project's cost ledger |
| `RETROSPECTIVE.AUTO_AMEND_OVERRIDES` | Retrospective | `false` (propose-only) |
| `PREFLIGHT.SECURITY_SUITE_REQUIRED` | Preflight | `true` (preflight 4a-lazy prompts to generate the project security audit on first run if missing). Set `false` for projects with no compliance obligations to permanently skip the prompt. |
| `PREFLIGHT.COMPLIANCE_AUDIT` | Preflight | (none) - a runnable compliance-audit command once the security-suite generator runs |
| `PREFLIGHT.CUSTOM_SCANNERS` | Preflight | (empty) |
| `STRUCTURAL.MAX_FILE_LINES` | Structural floor | `400` |
| `STRUCTURAL.MAX_FUNCTION_LINES` | Structural floor | the closure-gate `[function] max_lines` threshold in `tools/closure-gate/closure-gate.toml` (cited, never an independent number; LDD-INV-9) |
| `STRUCTURAL.MAX_COMPLEXITY` | Structural floor | `15` |
| `STRUCTURAL.MAX_NESTING` | Structural floor | `4` |
| `STRUCTURAL.MAX_PARAMS` | Structural floor | `5` |
| `STRUCTURAL.MAX_SLOP_RATIO` | Structural floor | `0.05` |
| `IDENTITY.REFACTOR_DOCS_ROOT` | Project identity | `Docs/refactoring/` |
| `IDENTITY.ARCH_SPECS_GLOB` | Project identity | (none; skip) |
| `COMMANDS.TEST` | Commands | `npm run test:run` |
| `COMMANDS.TEST_RELATED` | Commands | `npx vitest run --related` |
| `COMMANDS.TEST_ONE` | Commands | `npx vitest run` |
| `COMMANDS.TEST_COVERAGE` | Commands | `npm run test:run -- --coverage --coverage.reporter=json-summary` |
| `COMMANDS.LINT` | Commands | `npm run lint` |
| `COMMANDS.TYPECHECK` | Commands | `npx tsc --noEmit` |
| `COMMANDS.SCHEMA_VALIDATE` | Commands | (none; skip schema step if unset) |
| `COMMANDS.EXTRACT_API_SURFACE` | Commands | `npx tsx scripts/extract-api-surface.ts` |
| `SCHEMA.PROD_MIGRATION` | Schema migration | (none; skip schema deploy gate) |
| `CONTROL_PLANE.SCAN` | Control-plane V&V | (none; skip) |
| `UI.TOKEN_DRIFT` | UI V&V | (none; skip) |
| `UI.STATE_SCAN` | UI V&V | (none; skip) |
| `UI.VV_SMOKE` | UI V&V | (none; skip) |
| `DEPLOY.DEPLOY_CMD` | Deploy | (none) |
| `DEPLOY.SMOKE_CHECK` | Deploy | (none) |
| `DRIFT.MODULE_INDEX_SOURCE` | Drift detection | the architecture-overview doc |
| `DRIFT.ADDITIONAL_PATHS` | Drift detection | (empty) |
| `LEARNINGS` | Learnings | (empty) |

If your project introduces a new hook point, add the marker to the template playbook AND document the key here.
Keys are append-only; never repurpose an existing key.

## Generator

To bootstrap an overrides file for a new project, run `bootstrap-refactor-overrides`. It scans the repo (manifest
scripts to `COMMANDS.*`, schema-file presence to `SCHEMA.PROD_MIGRATION`, deploy-target file to `DEPLOY.*`,
compliance scripts to `PREFLIGHT.COMPLIANCE_AUDIT`, architecture-overview presence to `DRIFT.MODULE_INDEX_SOURCE`) and
writes the populated overrides file. After that, edit the file directly as the project's refactor learnings
accumulate.

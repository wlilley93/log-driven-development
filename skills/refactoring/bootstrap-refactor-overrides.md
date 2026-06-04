---
name: bootstrap-refactor-overrides
description: Refactoring suite, run-once-per-project bootstrap. Detects a project's stack characteristics (test runner, deploy target, schema engine, audit scripts, docs layout) and writes a populated refactoring-overrides.md from the override schema, plus the two helper scripts the suite expects. The output is a starting point the project owner reviews and edits before the first refactor round. Use when adopting the refactoring suite on a new project for the first time.
---

# Bootstrap refactor overrides

**Scope:** Run once per project to generate the initial `<overrides-root>/refactoring-overrides.md`.

Detects a project's stack characteristics (test runner, deploy target, schema engine, audit scripts, docs layout)
and writes a populated overrides file from `references/overrides-template.md`. The output is a starting point: the
project owner reviews and edits it before the first refactor round.

`<overrides-root>` is wherever your project keeps refactor configuration. A reasonable default is a tracked
directory at the repo root, for example `.refactoring/` or `docs/refactoring/config/`. Use one location
consistently; the other playbooks read the overrides file from the same place.

## Invocation

- run the bootstrap: scan and generate the overrides file
- dry-run: scan only, output the detection report without writing the overrides file

## When to invoke

- Adopting the refactoring suite on a new project for the first time.
- Major stack changes that invalidate existing overrides (rare; usually a manual edit is faster).
- Validating the suite's detection logic by running against a project that already has hand-written overrides
  (compare-as-test).

NOT for ongoing maintenance. Once the overrides file exists, edit it directly. Re-running this bootstrap
overwrites manual edits.

## Procedure

### 1. Identify the active project

```bash
PROJECT_ROOT=$(pwd)
PROJECT_NAME=$(basename "$PROJECT_ROOT")
OVERRIDES_PATH="$PROJECT_ROOT/.refactoring"   # or wherever your project keeps refactor config
```

If `$OVERRIDES_PATH/refactoring-overrides.md` already exists, ABORT unless `--force` is passed. Do not overwrite
hand-written content.

### 2. Detect stack characteristics

Run these probes; each emits a `key=value` to stdout. The probes below assume a Node/TypeScript project as the
worked example; add equivalents for your stack (Go modules, Cargo, Gradle, Poetry, etc.) following the same
"emit key=value, map to an override key" shape.

```bash
# package.json scripts (Node example)
if [ -f package.json ]; then
  jq -r '.scripts | to_entries | .[] | "\(.key)=\(.value)"' package.json
fi

# Test framework detection
test -f vitest.config.ts -o -f vitest.config.js && echo "test_framework=vitest"
test -f jest.config.ts -o -f jest.config.js && echo "test_framework=jest"
test -f pytest.ini -o -f pyproject.toml && grep -q pytest pyproject.toml 2>/dev/null && echo "test_framework=pytest"
test -d cypress && echo "e2e_framework=cypress"
test -f playwright.config.ts && echo "e2e_framework=playwright"

# Schema / migration engine
test -f prisma/schema.prisma && echo "schema_engine=prisma"
test -f drizzle.config.ts && echo "schema_engine=drizzle"
test -d migrations && echo "schema_engine=sql-migrations"

# Deploy target
test -f Dockerfile && echo "deploy_target=docker"
test -f vercel.json && echo "deploy_target=vercel"
test -f netlify.toml && echo "deploy_target=netlify"
test -f fly.toml && echo "deploy_target=fly && deploy_app=$(grep '^app =' fly.toml | cut -d'\"' -f2)"

# Refactor docs root
test -d docs/refactoring && echo "refactor_docs_root=docs/refactoring/"
test -d internal-docs/refactoring && echo "refactor_docs_root=internal-docs/refactoring/"

# Architecture specs glob (project convention; adjust the pattern to yours)
find docs/architecture -maxdepth 1 -name '*.md' 2>/dev/null | head -1 | grep -q . \
  && echo "arch_specs_glob=docs/architecture/*.md"

# Project-specific audit / check scripts
ls scripts/audit-*.sh 2>/dev/null  | while read s; do echo "audit_script=$s"; done
ls scripts/check-*.* 2>/dev/null   | while read s; do echo "check_script=$s"; done

# CI workflow
test -f .github/workflows/ci.yml && echo "ci_workflow=.github/workflows/ci.yml"

# Architecture-overview doc presence (the module-index source)
test -f ARCHITECTURE.md && echo "arch_overview=ARCHITECTURE.md"
test -f README.md && grep -qiE '^(##|###) (module index|key modules)' README.md && echo "module_index_in=README.md"

# Cost / usage ledger detection (optional; powers cache telemetry)
find . -path ./node_modules -prune -o -name 'cost-ledger.*' -print 2>/dev/null | head -1 \
  | while read f; do echo "cost_ledger=$f"; done

# Recency proxies
git log -1 --format=%ci 2>/dev/null | head -1 | while read d; do echo "last_commit=$d"; done
git log --oneline 2>/dev/null | wc -l | while read n; do echo "total_commits=$n"; done
```

Output goes to `/tmp/bootstrap-detection.txt`.

### 3. Map detected values to override keys

For each detected key, map to an override key per `references/overrides-template.md`:

| Detected | Maps to override |
|---|---|
| test script in package.json | `COMMANDS.TEST` (else infer from `test_framework`) |
| lint script | `COMMANDS.LINT` |
| build script | `COMMANDS.BUILD` |
| typecheck (default) | `COMMANDS.TYPECHECK` |
| `schema_engine=<engine>` | `COMMANDS.SCHEMA_VALIDATE` (engine-specific validate command) |
| `schema_engine` + `deploy_app` | `SCHEMA.PROD_MIGRATION` (the deploy-time migration command, with version pinning) |
| `deploy_target` + app/site | `DEPLOY.DEPLOY_CMD` |
| `refactor_docs_root` | `IDENTITY.REFACTOR_DOCS_ROOT` |
| `arch_specs_glob` | `IDENTITY.ARCH_SPECS_GLOB` |
| `module_index_in` | `DRIFT.MODULE_INDEX_SOURCE` |
| `audit_script` (name contains `compliance`) | `PREFLIGHT.COMPLIANCE_AUDIT` |
| `check_script` | `PREFLIGHT.CUSTOM_SCANNERS` (appended to the list) |
| `cost_ledger` | `TELEMETRY.COST_LEDGER_PATH` |

For everything not detected, use template defaults (Tier-2 + Tier-3 model dispatch, wave size 6, projection
disabled, characterization gate enabled, and the structural floor 400 file-lines / 15 complexity / 4 nesting / 5
params / 0.05 slop). The function-length axis is NOT a default here: it cites the closure-gate `[function]
max_lines` threshold in `tools/closure-gate/closure-gate.toml`, never a hardcoded number (LDD-INV-9).

### 4. Dispatch a generator agent (Tier 2)

Run a Tier-2 agent with this prompt:

```
You are bootstrapping a refactoring overrides file for a new project.

Inputs:
- /tmp/bootstrap-detection.txt (raw detection output)
- references/overrides-template.md (the schema reference)
- The project's architecture-overview doc (if it exists)
- The project's manifest / package descriptor (if it exists)

Output: a complete refactoring-overrides.md populated with detected values + sensible defaults.

Required sections (per overrides-template.md):
- Project identity
- Commands
- Schema migration (only if a schema engine was detected)
- Preflight tools
- Deploy (only if a deploy target was detected)
- Drift detection
- Learnings (empty for now; gets populated as rounds land)
- Module knobs (empty for now; gets populated when first preflight runs)
- Sub-agent dispatch limits (defaults)
- Model tier dispatch (defaults)
- Stakeholder projection (disabled by default)
- Structural floor (defaults)
- Pre-commit reviewing agent (enabled by default)
- Cache hit rate telemetry (degrades gracefully if no cost ledger)
- Round retrospective (enabled, propose-only)

Constraints:
- Use detected values where available; use template defaults where not.
- For each section, add a one-line note explaining what was detected vs defaulted.
- Mark detections as "DETECTED" and defaults as "DEFAULT" so the user can scan.
- Do NOT invent values for things you can't detect; use the template default.

After writing, output a summary: what was detected (count + list), what used defaults (count + list),
what needs user attention (anything ambiguous or with multiple plausible values).
```

### 5. Write the overrides file

```bash
mkdir -p "$OVERRIDES_PATH"
# Agent writes to "$OVERRIDES_PATH/refactoring-overrides.md"
```

### 6. Generate the helper scripts the suite expects

The suite uses two helper scripts that live in the project's `scripts/` directory. Both are mechanical templates.

#### 6a. `scripts/extract-api-surface.ts` (used by `references/api-surface-diff.md`)

Walks the source tree, parses it, and emits one line per exported symbol with its signature. The round-close
API-surface diff consumes the output. A Node/TypeScript reference implementation (using `ts-morph`) ships under
`tools/refactoring/extract-api-surface.ts`. For other stacks, write the equivalent: the only contract is "one
tab-separated line per exported public symbol, sorted, on stdout." Add the parser dependency to the project if
the language needs one.

#### 6b. `scripts/extract-round-cache-stats.<ext>` (used by the cache-telemetry step)

Only generated if a cost/usage ledger was detected. The aggregation is project-specific (each project's ledger
has different columns), so the bootstrap writes a SCAFFOLD that the project owner fills in. It must accept a
`--round N` argument, read the round's start and end commit SHAs, query the ledger for entries in that range,
group by model-tier, sum input / cache-read / cache-create tokens, compute the cache hit rate per tier, and emit
a markdown table. If no ledger is detected, skip this and mark `TELEMETRY.COST_LEDGER_PATH: (not detected)` in
the overrides; the telemetry step degrades gracefully.

### 7. Final report

```markdown
# Bootstrap complete: <PROJECT_NAME>

## Generated this run
- overrides file (X DETECTED, Y DEFAULT, Z NEEDS-ATTENTION)
- scripts/extract-api-surface.* (used by the API-surface diff at round close)
- [conditional] scripts/extract-round-cache-stats.* SCAFFOLD (cost ledger detected; fill in the TODO queries)

## Pre-existing (detected, no action)
- <refactor docs root>/ exists
- <arch specs glob> exists

## Lazy-initialized at preflight time (NOT bootstrap's job)
The following are owned by other phases and generate themselves on first invocation when missing:
- Project-specific security-audit infrastructure (the preflight wave detects the gap and offers to generate it)
- Pre-arc characterization tests for untested files (the structural-sweep generates these on first arc)
- Round baselines (create-refactor-plan captures them on round 1)

## Recommended next steps (in order)
1. Review the generated overrides file and edit any NEEDS-ATTENTION items.
2. If a cost ledger was detected, fill in the TODO queries in the cache-stats script.
3. Run create-refactor-plan in dry-run to preview round 1.
4. If the projection looks reasonable, run create-refactor-plan to commit round 1.
```

## Validation: bootstrap-versus-handwritten comparison

Running the bootstrap against a project that already has a hand-written overrides file is a good sanity check.
The generator output should match the hand-written file's mechanical sections (commands, deploy, schema, drift)
within roughly 95%. Sections it should NOT touch: Learnings (project history), Module knobs (per-module gotchas),
and any multi-round arc plan. The differences pinpoint where the generator missed detection (improve the probes)
versus where the hand-written file holds tribal knowledge the generator cannot reach (document the gap; do not
fight it).

## What this bootstrap does not do

- Does not write the project's architecture-overview doc (project-owned).
- Does not generate the security-suite content (separate generator; the preflight wave handles that detect-and-offer flow).
- Does not write the refactor docs root structure (create-refactor-plan captures baselines on round 1).
- Does not validate that detected paths actually work (test that yourself post-bootstrap).
- Does not generate pre-arc characterization tests (the structural-sweep handles that when an arc starts).

These are explicit non-goals. The bootstrap's scope is exactly: refactor-suite overrides plus the helper scripts
the suite expects to find. Anything outside that boundary is a separate concern owned by a different generator or
by the project's contributors.

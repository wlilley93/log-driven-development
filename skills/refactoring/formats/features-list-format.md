# Features-list format

Reference schema for `<refactor-docs-root>/features-list.md`: the master inventory + dependency graph + score
history. Persistent across all rounds.

## Top-level structure

```markdown
# Features list - refactoring tracker

**Last updated:** YYYY-MM-DD
**Total modules:** N
**Total findings:** X (Yc critical, Zh high, Wm medium)

## Severity scoring
[scoring table - see below]

## Dependency graph
[ASCII tree - see below]

## Modules
### [Category]
[per-module rows - see below]
```

## Severity scoring table

Each module gets a severity score from 0.0 to 10.0 based on:

| Factor | Weight | Description |
|--------|--------|-------------|
| Security boundary crossed | 3.0 | Auth bypass, XSS, injection, SSRF, data leak |
| Data loss/corruption possible | 2.5 | Race conditions, silent overwrites, orphaned records |
| Compliance control gap | 2.0 | Missing audit logging, unvalidated input, no CSRF |
| Atomization debt | 2.0 | File over the floor's max file lines, function over the max function lines, complexity over the max, nesting over the max, or named on the score-trajectory as a known god-component. Reading cost compounds across every future round; high penalty. |
| Availability impact | 1.5 | Infinite loops, memory exhaustion, missing indexes |
| Comprehension cost | 1.5 | Mixed concerns in one file (HTTP + business logic + DB), duplicated blocks across 3+ sites, deep type-shape coupling, slop patterns (redundant comments, defensive checks unreachable under the type system) |
| Control-plane drift | 1.5 | Shared policy copied instead of routed through a source of truth: auth, permissions, API client, validation/schema, logging/audit, status enums, feature flags, error handling |
| UI state gap | 1.5 | Demo-path-only UI: missing loading, empty, error, retry, permission-denied, stale-data, long-content, or mobile/responsive states |
| Design-system drift | 1.5 | Raw colors/classes, duplicated primitives, token bypass, page-specific styling forks, inconsistent table/modal/button/loader patterns |
| UX degradation | 1.0 | Silent errors, missing accessibility, wrong data shown |

Score = sum of applicable factors (capped at 10.0).

**Atomization weighting is deliberate.** Past rounds repeatedly identify the same god-components (very large grid
components, large reconciliation modules, large parser files) as M-class findings, then defer them every round
because Maintainability scored low. With Atomization debt at 2.0 + Comprehension cost at 1.5, a known god-component
lands at 3.5+ before any other factor, comparable to a critical-tier security finding. This is intentional:
reading-cost debt accumulates faster than security debt because every future round's LLM review pays the
comprehension tax on the same files.

## Dependency graph

ASCII tree showing modules that share files or data flows. Fixes to upstream modules must land before downstream.
Example shape (illustrative; build your own from the real codebase):

```
auth-security (foundation)
  └── all other modules depend on auth

framework-core
  ├── profiles (core, always active)
  │   ├── addon-a (depends on profiles + <data>)
  │   └── addon-b (depends on profiles)
  ├── <data> (depends on profiles)
  └── agent-layer

tables + records (core platform)
  ├── knowledge-base (uses tables for docs)
  ├── dashboards (reads from tables)
  ├── workflow (triggers from records)
  └── forms-submissions (creates table rows)

files-identity (cross-cutting)
  ├── extraction (uses file records)
  ├── oversight (uses identity)
  └── portal (uses files)
```

Update this graph when modules are added or dependencies are discovered during review.

## Per-module rows

Group by category (security infrastructure, core platform, addons, integrations, infrastructure):

```markdown
### Security infrastructure

| Module | Dir | Status | Score | Findings | Key risk | Depends on | Touches |
|--------|-----|--------|-------|----------|----------|------------|---------|
| Auth | src/lib/auth/ | Done (round-N) | 0.5 | 0c/0h/2m | Session + invite flow | - | src/lib/auth.*, app/(auth)/* |
```

Required columns:
- **Module** - name as it appears in the architecture-overview module index.
- **Dir** - canonical source directory (used for path-prefix routing in preflight 4c).
- **Status** - one of: `Needs review` / `In progress (round-N)` / `Done (round-N)` / `Deprecated`.
- **Score** - latest severity score (0.0-10.0).
- **Findings** - latest count: `Xc/Yh/Zm` (critical/high/medium).
- **Key risk** - one-line description of the dominant concern.
- **Depends on** - upstream modules from the dependency graph.
- **Touches** - files this module owns (used for cross-cutting detection in preflight 4c).

## Maintenance

- **create-refactor-plan Step 1** auto-detects drift by comparing the architecture-overview module index against
  this table. New modules in the overview but missing here get appended with status `Needs review`. Modules removed
  from the overview get marked `Deprecated`.
- **run-refactor Step 6** updates each module's row at completion: status → `Done (round-N)`, score recalculated,
  finding counts updated, commit range appended.
- **create-refactor-plan Step 8** re-evaluates scores after preflight findings land. A module with no historical
  interest but suddenly 5 critical preflight findings gets bumped automatically.
```

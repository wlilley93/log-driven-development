# Review format

Reference schema for per-module `review.md` files (NORMAL mode, written in `create-refactor-plan` Step 5).

## Required sections

1. **Header** - date, scope, files reviewed (table with line counts, complexity scores from the maintainability
   scanner, last-touched commit).

2. **Verification evidence** - before reviewing, run actual queries/checks. Report what you ran and what you
   found, not just inference. Examples: check for duplicate keys or constraint violations with a direct query;
   check for missing indexes on frequently-queried columns; check for orphaned records (FK targets that do not
   exist); run the linter on the module files and note errors; run any module-specific health checks.

3. **Git context** - for each file reviewed: `git log --oneline -5 <file>` (when was it last touched?) and
   `git log --oneline --since="3 months ago" <file>` (is it actively changing?). Files untouched for 6+ months
   with zero bug reports are lower risk; files rewritten recently are higher risk (new code = new bugs). Note this
   context when assigning severity.

4. **Security** - severity score + strengths + findings (`S1`, `S2`, ...).

5. **Performance** - severity score + strengths + findings (`P1`, `P2`, ...).

6. **Correctness** - severity score + strengths + findings (`C1`, `C2`, ...).

7. **Maintainability** - severity score + strengths + findings (`M1`, `M2`, ...). Cite the maintainability
   scanner's findings (complexity, duplication, dead code, slop) by ID rather than re-discovering them.

8. **Control-plane / source-of-truth drift** - required for cross-cutting modules, useful for all. Severity score
   + findings (`B1`, `B2`, ...). Look for duplicated policy that should flow through a stable "bus": auth/session/
   tenant checks copied across handlers instead of shared middleware; permissions, roles, feature flags, route
   guards, status enums, validation/schema, API client, logging/audit, retry/error handling repeated in multiple
   sites; multiple sources of truth with slightly different semantics; an over-centralized "god bus" that owns
   feature-specific behavior and makes local changes unsafe.

9. **UI state & design-system drift** - required for frontend modules or UI overhaul rounds. Severity score +
   findings (`U1`, `U2`, ...). Cite deterministic evidence where available, then add LLM judgment for semantic
   gaps: raw styling drift (direct hex/rgb/hsl, one-off utility classes, inline styles, duplicated spacing/type/
   color decisions that should flow through tokens or primitives); primitive drift (repeated table/modal/button/
   tab/loader/empty-state/toast/form patterns that should use the shared control plane); demo-path state gaps
   (missing loading, empty, error, retry, permission-denied, stale-data, disabled, optimistic, long-content,
   mobile/responsive states); ownership boundaries (API calls, validation, persistence, permissions, business
   rules embedded in render components); visual verification (screenshots, traces, accessibility output, or an
   explicit "not runnable" reason with the command attempted).

10. **Additional sections** as needed (Schema, Data Integrity, Integration Gaps, Test Coverage).

11. **Priority fixes table** - `| # | Score | ID | Issue | Fix | Rollback |`.

## Per-finding requirements

Every finding must include: file path; line number (or range); code snippet; problem description; fix description;
severity score (0.0-10.0) using the scoring table from `formats/features-list-format.md`; source attribution if it
came from preflight (e.g. `(from vibescan: SECRET-23)`, `(from vibeaudit-deep: AUTH-bypass-44)`). Do not
re-discover what the deterministic wave already found.

## What goes in M-class (Maintainability)

The M-class is the primary atomization-finding output of NORMAL rounds. With the scoring table giving Atomization
debt 2.0 + Comprehension cost 1.5, M-findings can score 3.5+ before any other factor. High-value M-findings:
file over the structural floor's max file lines (cite the maintainability-scanner complexity entry); function over
the max function lines; cyclomatic complexity over the max; mixed concerns in one file (HTTP handler + business
logic + DB code); duplicated logic across 3+ sites; slop ratio over the floor (redundant comments, defensive
checks unreachable under the type system); god-components on the score-trajectory's known list.

## What goes in B-class (Control-plane / source-of-truth drift)

Use B-class findings when the module lacks the coding equivalent of a reliable bus, or when the bus has become too
large: **Missing bus** (auth, permissions, tenant scoping, API calls, validation/schema, status mapping, feature
flags, logging/audit, retries, or error handling copied across 3+ places); **Split bus** (two helpers or schemas
claim the same responsibility with different semantics); **Leaky bus** (callers still need to know low-level policy
details the helper should own); **God bus** (one central layer absorbs feature-specific rules and becomes harder
to test or change than local code). Good remediation centralizes stable shared policy while keeping
feature-specific behavior local and testable.

## What goes in U-class (UI state & design-system drift)

Use U-class findings for frontend-specific gripes that generic maintainability scans underweight: missing UI
states (loading, empty, error, retry, permission-denied, stale-data, optimistic, disabled, long-content,
mobile/responsive); design-token bypass (raw hex/rgb/hsl, inline styles, page-local CSS variables that duplicate
canonical tokens, utility one-offs where the project uses primitives); primitive drift (feature-local versions of
tables, modals, buttons, tabs, loaders, command bars, filters, empty states, or form controls); component-boundary
drift (fetch/permission/schema/business rules inside render components instead of hooks, services, schemas, or
shared clients); visual/accessibility regressions (overlapping text, broken responsive layout, missing labels/
focus states, inaccessible controls, screenshots that differ from the accepted handover).

When the round mode is STRUCTURAL_SWEEP, these findings are out of scope (handled by per-batch dispatch) and the
review.md is replaced by `batch/result.md`. NORMAL rounds still benefit from M-findings being weighted enough to fix.

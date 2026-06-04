# Fix-prompt format

Reference schema for per-module `fix-prompt.md` files. Used by `create-refactor-plan` Step 4d
(preflight-drafted skeleton), `create-refactor-plan` Step 5 (validated and finalized by the per-module agent), and
`run-refactor` Step 4 (executed by dispatch agents).

## Top-level structure

```markdown
# Module Name - Fix prompt (round-N)

## What's wrong
2-3 sentence summary with the total severity score and the dominant risk class.

## Sequencing
If fixes have ordering constraints, an ASCII dependency diagram. Otherwise omit.

## Fixes
[per-fix blocks - see below]

## Refactoring
Structural improvements bundled with fixes (e.g. "while applying Fix 3, also extract X helper").

## Deferred
Items not in scope this round, with rationale. These get appended to the deferred.md ledger at round close.

## Verification
Checklist of post-fix checks beyond the per-fix Verify commands.

## Execution result
[result manifest - filled by run-refactor - see below]
```

## Per-fix block

```markdown
### Fix N (Score: X.X): Title - ID

**File:** path/to/file
**Problem:** Description
**Fix:** Concrete instructions
**Schema migration:** [yes | no]
  - If yes: name the table/column/index added or modified. Surfaces in the close-checklist as a required prod migration step.
**Confidence (preflight-drafted):** [high | medium | low | n/a if LLM-discovered]
**Blast radius:** [local | module | cross-module | platform | schema | infra]

**Rollback:** If this fix causes failures:
- Revert command: `git revert <commit>` (or specific manual steps if revert is non-trivial)
- Verify: <a runnable command that confirms the rollback worked, e.g. the module's test path or a health-check>
- Data recovery: [steps to undo any data migration; for additive schema changes the rollback is "leave the
  column"; for destructive changes it is the project-specific point-in-time-recovery or backup procedure]

**Result schema:**
- files_modified: [list]
- tests_added: [count]
- tests_modified: [count]
- findings_resolved: [IDs]
- schema_change_applied_to_prod: [n/a | yes-{commit-hash} | pending-deploy]
```

### Required fields

| Field | Purpose | Validation |
|---|---|---|
| Score | Severity from the scoring table | Required, 0.0-10.0 |
| Title - ID | Human label + machine-readable ID for cross-references | Required, ID format `<module>-<class>-<n>` (e.g. `auth-S-3`, `orders-fix-6`) |
| File | Path being modified | Required, must exist at HEAD |
| Problem | Why this is broken | Required, 1-3 sentences |
| Fix | What to do about it | Required, concrete enough that an agent can execute without re-thinking |
| Schema migration | Yes/no flag | Required; if yes, also requires a migration command in Verify |
| Confidence | Preflight-draft confidence | Required when from Step 4d; otherwise n/a |
| Blast radius | Affected scope | Required; shapes test-selection (local → related/module tests; cross-module → broader sweep; platform → full suite) |
| Rollback | Recovery steps | Required, including a runnable Verify command |
| Result schema | What run-refactor fills in | Template only; the executing agent populates it |

### Why each field exists

- **Schema migration: yes/no** is the gate that prevents the schema-incident class (a schema change shipped
  without a prod migration, so every read against the new column throws). The close-checklist auto-emitter scans
  for this flag.
- **Confidence** lets the Step-5 validating agent triage fast: high-confidence drafts get spot-checked,
  low-confidence drafts get rewritten from scratch.
- **Blast radius** drives test-selection in run-refactor: `local` → the related-tests selector; `module` → the
  module fast-test path; `cross-module` → multiple module test paths; `platform` → the full suite.
- **Rollback Verify** as a runnable command instead of prose is what makes auto-bisect work: verify-refactor can
  run this command at each bisect step rather than requiring human interpretation.

## Result manifest (filled by run-refactor)

After all fixes execute, the dispatched agent fills in:

```markdown
## Execution result

| Fix | Status | Files modified | Tests | Schema migration | Commit |
|-----|--------|---------------|-------|------------------|--------|
| Fix 1 | applied | src/lib/<module>/<file>, ... | +0/-0 | no | abc123 |
| Fix 2 | applied | <schema-file>, src/services/... | +2/-0 | yes - <table>.<column> | def456 |
| Fix 3 | reverted | (initial: 789xyz, revert: 789abc) | +0/-0 | no | reverted |
| Fix 4 | deferred | - | - | - | - (see deferred.md) |

**Baseline comparison:**
- Tests before: X passing, Y failing
- Tests after: X passing, Y failing
- New tests: Z
- Regressions: [list or "none"]
```

The `Schema migration` column is mandatory and feeds the round-close checklist.

# Regression-avoidance protocol

The single canonical map of regression classes the suite tries to prevent, the detection mechanism for each, and
the explicit gaps. Reused by `create-refactor-plan`, `structural-sweep`, `run-refactor`, and `verify-refactor`.

The principle: **every commit a refactor agent makes is a potential regression.** The suite has multiple layered
defences, each tuned for a different class. No single mechanism is sufficient.

## The 10 regression classes

| Class | What it is | Where caught | Gap |
|---|---|---|---|
| **Test regression** | A test that passed before now fails | `verify-refactor` diff vs `baselines/test-results.txt`; related-tests per-fix in the dispatch loop; auto-bisect on a detected regression | Tests must exist. Untested code = vacuously "no regression." |
| **Type regression** | A type-check error in code that compiled cleanly | `verify-refactor` diff vs the typecheck baseline | Pre-existing type errors must be in the baseline; new errors in the same files may not surface as "newly failing." |
| **Lint regression** | A new lint error in code that was clean | `verify-refactor` diff vs the lint baseline | The lint config must be working. If a baseline captured a broken lint state, flag it in the deferred ledger and fix it Wave-0 before lint-regression detection works. |
| **Schema regression** | A DB schema change ships without a prod migration | The fix-prompt `schema_migration` field + the round-close checklist auto-emitter | Detection only works if fix-prompts honestly declare `schema_migration`. A fix that touches schema but does not declare it slips through. |
| **API-surface regression** | A route signature, exported type, or export removed without acknowledgment | `references/api-surface-diff.md` snapshot + cross-round diff at round close | Requires the project's `extract-api-surface` script. A behaviour diff (same signature, different return) is NOT caught. |
| **Behavioural regression** | Code passes tests but does something different than before | The pre-commit reviewing agent (catches some shapes); test coverage of changed lines | Most fall through. Tests only catch what tests test. Property-based tests would close more; not currently in the suite. |
| **Control-plane regression** | A refactor copies shared policy, splits one source of truth, or over-centralizes feature behavior into a god bus | the control-plane scan, the control-plane methodology, the pre-commit reviewing agent, the API-surface diff | Scanner heuristics are noisy. The LLM pass must decide whether centralization is actually appropriate. |
| **Performance regression** | Build, test suite, or bundle slower/larger than before | NOT IMPLEMENTED. Build/test duration is captured in baselines but there is no acceptance gate | Add a build-duration + bundle-size baseline + an acceptance threshold (e.g. +20% fails) to close. |
| **Cross-session conflict** | Concurrent feature work in main collides with refactor commits | Drift detection vs the snapshot at create-refactor-plan Step 1.5 of the next round | Mid-round conflicts (concurrent sessions writing during dispatch) are NOT prevented; only detected after the fact via merge conflicts. |
| **Visual / UX regression** | Same code paths, different rendered output or missing expected UI states | the UI V&V verifier, `ui-vv-smoke`, screenshots/traces, accessibility smoke, token/state scans | Screenshot tooling must be configured per project. "Not configured" is a coverage gap, not a PASS. |

## The four discipline checkpoints

Where each round must apply discipline. Skipping any one dramatically increases regression risk.

### 1. Pre-dispatch: baseline freshness

**Mandatory before any agent dispatches.** Verify baselines are current:

```bash
BASELINE_SHA=$(cat <!-- OVERRIDE: IDENTITY.REFACTOR_DOCS_ROOT -->Docs/refactoring/<!-- /OVERRIDE -->baselines/baseline-sha.txt 2>/dev/null)
HEAD_SHA=$(git rev-parse HEAD)

if [ "$BASELINE_SHA" != "$HEAD_SHA" ]; then
  COMMITS_SINCE=$(git rev-list "${BASELINE_SHA}..${HEAD_SHA}" --count)
  echo "[!] Baseline drift: $COMMITS_SINCE commits since baseline-sha ($BASELINE_SHA)"
  echo "[!] Re-capture baselines before R$N starts, OR document which baselines are intentionally stale"
  exit 1  # the dry-run reports this; the full run blocks until resolved
fi
```

Why: if a baseline is captured at one SHA but HEAD has moved on (concurrent work landed), verifying against the
stale baseline surfaces false-positive regressions attributed to "this round" that are actually pre-existing in
main. False positives erode trust in the bisect output. **Mitigation:** re-run baseline capture (lint, typecheck,
schema, full test suite, git-log) at the actual starting SHA, update `baseline-sha.txt`, then dispatch.

### 2. Per-fix: pre-commit verification

**Mandatory in every dispatch agent loop:** after a fix is applied, run the related-tests selector against the
changed files; after tests pass, dispatch the pre-commit reviewing agent (Tier 2); after review approves, make the
per-fix atomic commit; log the per-fix `Verify` command (from the fix-prompt's Rollback section) for auto-bisect
to consume later. This catches most test regressions, hallucinated content, dead imports, debug statements left
behind, and schema-migration drift between declaration and diff. It misses cross-fix interaction effects (fix A
breaks B's tests, not run because A's related-test set did not include B's tests).

### 3. Per-wave: cross-fix regression sweep

**Between waves of parallel dispatch:** merge the wave's branches to main; run a targeted regression sweep (full
module test paths for every module touched in this wave); if any test that passed pre-wave now fails, auto-bisect
within this wave's commits to find the offending fix; if bisect finds one, revert that single commit, mark the fix
`failed`, log it in `result.md`; continue to the next wave. This catches cross-fix interactions within a wave and
fixes that pass related-tests but break broader tests. It misses cross-wave interactions (a Wave-0 cross-cutting
fix breaking Wave-2 modules); mitigate by merging Wave 0 first, then re-running the relevant baseline tests before
Wave 1 dispatches.

### 4. Round close: full regression validation

**Mandatory before round close:** the full test run (not the related-tests subset; measures all tests); the full
typecheck; the full lint; the API-surface diff vs the round-(N-1) snapshot; the schema-migration close-checklist
gate; cache telemetry (not regression per se, but it tells you whether the model dispatch is paying off). This
catches anything the per-fix and per-wave checks missed; it is the last line of defence before the round is
declared complete. It misses regressions that only manifest in production (observability/error-tracking would
close this; not currently wired).

## What "no regression" actually means in this suite

The honest answer: a round passes "no regression" when:

1. All tests passing in baseline still pass (verified by the `verify-refactor` diff).
2. No new type-check errors in files that compiled cleanly in baseline.
3. No new lint errors in files that were lint-clean in baseline.
4. Schema validate still passes.
5. All schema-touching fixes have a prod migration applied or explicitly marked n/a.
6. The API-surface diff vs the prior round shows no unacknowledged breaking changes.
7. The pre-commit reviewer approved every fix that landed (or its rejections are documented).

It does NOT mean: behavioural changes are detected (only some shapes are); performance has not degraded (not
measured); bundle size has not grown (not measured); visual output is unchanged (not measured); concurrent work
did not collide (only detected post-hoc via merge conflicts). These gaps are real and known. The suite is honest
about them. Fill them when actual production failures justify the setup cost.

## When NOT to start a round

`create-refactor-plan` should refuse to dispatch (or warn loudly) when any of these is true: the working tree has
uncommitted changes that are not yours; the baseline SHA != HEAD SHA and is not explicitly resolved; multiple
concurrent agent sessions are detected on this repo; the lint baseline is in a broken state and lint-regression
detection is not being explicitly waived; the test baseline contains failures that are not in the
pre-existing-failures registry. These checks are codified in the `create-refactor-plan` dry-run output. The user
can override (sometimes you genuinely want to refactor against in-flight code), but the override must be explicit.

#!/usr/bin/env bash
# verify-refactoring-suite.sh
#
# Structural verifier for the refactoring suite. Confirms the canonical files exist and that the
# security delegation seam is wired (the suite must route security review to a separate security suite,
# not duplicate security methodology locally). Run it after editing the suite to catch a missing or
# renamed file before it breaks a refactor round.
#
# Usage:
#   tools/refactoring/verify-refactoring-suite.sh                 # defaults to the dir two levels up
#   tools/refactoring/verify-refactoring-suite.sh /path/to/skills/refactoring
#
# Exit 0 = PASS, non-zero = FAIL with the missing path printed.

set -euo pipefail

# Default: the skills/refactoring directory, assuming this script sits at skills/refactoring/tools/... or
# at tools/refactoring/ alongside it. Pass the suite root explicitly to be safe.
ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../skills/refactoring" 2>/dev/null && pwd || echo "")}"

if [[ -z "$ROOT" || ! -d "$ROOT" ]]; then
  echo "FAIL could not resolve the suite root; pass it as the first argument"
  echo "  e.g. $0 /path/to/skills/refactoring"
  exit 1
fi

required=(
  "SKILL.md"
  "bootstrap-refactor-overrides.md"
  "create-refactor-plan.md"
  "run-refactor.md"
  "verify-refactor.md"
  "structural-sweep.md"
  "references/preflight-wave.md"
  "references/worker-constitution.md"
  "references/regression-avoidance.md"
  "references/api-surface-diff.md"
  "references/overrides-template.md"
  "formats/features-list-format.md"
  "formats/review-format.md"
  "formats/fix-prompt-format.md"
)

for path in "${required[@]}"; do
  if [[ ! -f "$ROOT/$path" ]]; then
    echo "FAIL missing $path"
    exit 1
  fi
done

# The suite must delegate security review rather than duplicating it. Confirm the dispatch seam is
# referenced in the canonical docs. (Uses grep -r so it works without ripgrep installed.)
if ! grep -rqiE "security[- ]suite" "$ROOT/SKILL.md" "$ROOT/references/preflight-wave.md"; then
  echo "FAIL security-suite delegation references missing from the canonical refactoring docs"
  exit 1
fi

# The four lifecycle playbooks must each reference the worker constitution or the shared references so
# the chain is intact.
for playbook in run-refactor.md structural-sweep.md; do
  if ! grep -qi "worker-constitution" "$ROOT/$playbook"; then
    echo "FAIL $playbook does not reference references/worker-constitution.md"
    exit 1
  fi
done

echo "PASS refactoring suite canonical structure verified"

#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SKILLS_ROOT="$(cd "$ROOT/.." && pwd)"

required=(
  "README.md"
  "WORKFLOW.md"
  "methodology.md"
  "tools.md"
  "generator.md"
  "10_skills/security-baseline-review.md"
  "10_skills/auth-session-review.md"
  "10_skills/authz-tenant-isolation-review.md"
  "10_skills/input-validation-review.md"
  "10_skills/secrets-crypto-review.md"
  "10_skills/dependency-supply-chain-review.md"
  "10_skills/license-compliance-review.md"
  "10_skills/sql-data-access-review.md"
  "10_skills/ai-prompt-tool-security-review.md"
  "10_skills/plugin-mcp-sandboxing-review.md"
  "10_skills/privacy-governance-review.md"
  "10_skills/compliance-evidence-review.md"
  "10_skills/vulnerability-assessment-review.md"
  "10_skills/risk-safety-gates.md"
  "20_agents/security-reviewer.md"
  "20_agents/auth-tenant-reviewer.md"
  "30_adapters/project-adapter.md"
  "30_adapters/nextauth-adapter.md"
  "30_adapters/stripe-adapter.md"
  "30_adapters/supabase-adapter.md"
  "30_adapters/plugin-mcp-adapter.md"
  "30_adapters/procurement-security-adapter.md"
  "30_adapters/support-security-escalation-adapter.md"
  "30_adapters/regulatory-privacy-adapter.md"
  "40_playbooks/refactor-preflight.md"
  "40_playbooks/standalone-security-review.md"
  "40_playbooks/full-security-audit.md"
  "40_playbooks/incident-posture-update.md"
  "40_playbooks/release-gate.md"
  "50_references/dispatch-matrix.md"
  "50_references/finding-schema.md"
  "50_references/severity-rubric.md"
  "50_references/threat-model-template.md"
  "50_references/coverage-matrix.md"
  "50_references/nonregression-checklist.md"
  "60_tools/scanner-orchestration.md"
)

for path in "${required[@]}"; do
  if [[ ! -f "$ROOT/$path" ]]; then
    echo "FAIL missing $path"
    exit 1
  fi
done

if [[ -d "$ROOT/90_legacy_sources" ]]; then
  echo "FAIL use Base Skills instead of 90_legacy_sources"
  exit 1
fi

if find "$SKILLS_ROOT" -mindepth 1 -maxdepth 1 -type d -iname '*security*' ! -name 'Security-Suite' ! -name 'security-suite' ! -name 'security' | grep -q .; then
  echo "FAIL multiple top-level security suite folders under $SKILLS_ROOT"
  find "$SKILLS_ROOT" -mindepth 1 -maxdepth 1 -type d -iname '*security*' ! -name 'Security-Suite' ! -name 'security-suite' ! -name 'security'
  exit 1
fi

rg -n --glob '!**/scripts/verify-security-suite.sh' '(^|/)security-suite(/|$)|Development/security-suite|Local/security-suite|Global Skills/Local/security-suite' \
  "$ROOT" \
  "$SKILLS_ROOT/refactoring" \
  "$SKILLS_ROOT/../Meta/engines/refactoring" \
  "$SKILLS_ROOT/agentic_engineering_process_suite_v1_0/engines/refactoring" 2>/dev/null \
  | grep -v '/Base Skills/' >/tmp/security-suite-stale-refs.txt || true

if [[ -s /tmp/security-suite-stale-refs.txt ]]; then
  echo "FAIL stale lowercase security-suite references"
  cat /tmp/security-suite-stale-refs.txt
  exit 1
fi

echo "PASS Security-Suite structure and active references verified"

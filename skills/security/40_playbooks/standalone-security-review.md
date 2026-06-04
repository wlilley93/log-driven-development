---
name: standalone-security-review
type: playbook
domain: security
summary: Targeted standalone Security-Suite workflow for bounded security reviews.
---

# Standalone Security Review

Use this playbook when Security-Suite runs alone but the request is narrower than a full codebase audit.

## Procedure

1. Run `../WORKFLOW.md` with `mode=standalone`.
2. Capture the requested target as `scope`: diff, PR, file list, directory, route group, service, integration, evidence set, or user-reported vulnerability.
3. Fingerprint only enough repo context to choose skills and adapters.
4. Use `../50_references/dispatch-matrix.md` to dispatch matching skills.
5. Read direct evidence for every claim.
6. Produce findings with `../50_references/finding-schema.md`.
7. Return exact verification required before close.

## Output

```json
{
  "mode": "standalone",
  "scope": "",
  "repo_fingerprint": {},
  "dispatched_skills": [],
  "dispatched_adapters": [],
  "findings": [],
  "required_verification": [],
  "skips": [],
  "residual_risk": []
}
```

## Boundary

Do not widen a targeted review into a full audit unless the evidence shows a shared security boundary or systemic control is affected. If widening is required, switch to `full-security-audit.md` and record why.

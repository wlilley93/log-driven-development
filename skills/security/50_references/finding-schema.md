# Security Finding Schema

Use this schema for every substantive finding.

```json
{
  "id": "SEC-001",
  "title": "Short finding title",
  "severity": "Critical | High | Medium | Low | Info",
  "confidence": "Confirmed | Likely | Hypothesis | False-positive-risk",
  "surface": "auth-session | authz-tenant | input-validation | secrets-crypto | dependency-supply-chain | payment | storage | plugin-mcp | privacy | compliance",
  "evidence": ["file:line", "command output", "test result"],
  "exploit_scenario": "How an attacker or misuse path reaches the bug.",
  "suggested_fix": "Concrete remediation.",
  "required_verification": "Tests, scans, or manual checks required before close.",
  "adapter_notes": "Project/framework checks applied.",
  "residual_risk": "Remaining uncertainty or deferral."
}
```

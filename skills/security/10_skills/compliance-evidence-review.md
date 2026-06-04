---
name: compliance-evidence-review
type: skill
domain: security
summary: Validate security/compliance evidence without treating checklists as behavioral proof.
outputs: [compliance-evidence-report.md]
---

# Compliance Evidence Review

## Required Checks

- Static compliance scripts are mapped to actual controls and known blind spots.
- Behavioral security properties have tests, not only grep coverage.
- Exceptions are documented with owner, rationale, expiry, and compensating controls.
- Audit evidence is reproducible and points to exact commands, files, and dates.
- Findings distinguish policy/documentation gaps from exploitable product defects.

## Output

Produce control coverage, failed checks, false positives, blind spots, and required behavioral regression tests.

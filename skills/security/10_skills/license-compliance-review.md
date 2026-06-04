---
name: license-compliance-review
type: skill
domain: security
summary: Review dependency license compliance and security-adjacent supply-chain obligations.
outputs: [license-compliance-report.md]
---

# License Compliance Review

## Use When

Use when dependency manifests, vendored code, generated assets, procurement evidence, release gates, or customer redistribution obligations are in scope.

## Required Checks

- Dependency license inventory is generated from manifests and lockfiles.
- Copyleft, source-available, commercial, unknown, and unlicensed packages are flagged.
- Vendored, copied, generated, image, font, and model assets are included when present.
- License obligations are separated from vulnerability risk.
- Any customer-facing compliance claim has evidence.

## Output

Return license findings, affected packages/assets, obligation, risk, suggested action, and verification command or evidence source.

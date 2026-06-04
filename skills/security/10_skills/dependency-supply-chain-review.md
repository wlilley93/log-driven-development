---
name: dependency-supply-chain-review
type: skill
domain: security
summary: Assess dependencies, provenance, lockfiles, package scripts, and slopsquatting risk.
outputs: [dependency-review.md]
---

# Dependency Supply Chain Review

## Use When

Use when package manifests, lockfiles, build tooling, install scripts, CI images, plugin manifests, or vendored code changes.

## Required Checks

- New packages are necessary, maintained, correctly named, and from expected publishers.
- Lockfile changes match manifest intent.
- Install/build/postinstall scripts are reviewed.
- Known vulnerabilities are triaged with severity and exploitability.
- Package usage does not move secrets or privileged APIs client-side.
- License or compliance constraints are captured when relevant.

## Output

Document added/removed packages, provenance evidence, vulnerability findings, and safer alternatives if a dependency is not justified.

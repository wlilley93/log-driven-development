---
name: secrets-crypto-review
type: skill
domain: security
summary: Review secrets, encryption, signing, token handling, and redaction.
outputs: [secrets-crypto-findings.json]
---

# Secrets Crypto Review

## Required Checks

- Secrets are loaded from environment or secret stores, never committed or logged.
- Production does not silently fall back to development secrets.
- Signing and encryption keys are separated where practical and support rotation.
- Tokens include purpose, expiry, subject, and integrity protection.
- Comparisons for secrets, signatures, and tokens use safe verification helpers.
- Logs, errors, traces, screenshots, and generated artifacts redact secret-shaped values.
- Crypto libraries are used according to their documented return semantics.

## Output

Include scanner commands used, evidence for any exposure, and rotation or invalidation requirements if a secret may have leaked.

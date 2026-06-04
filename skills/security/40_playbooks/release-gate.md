---
name: release-gate
type: playbook
domain: security
summary: Security release gate workflow.
---

# Release Gate

Run before production release of security-sensitive changes.

Require:

- Dispatch through `../WORKFLOW.md` with `change_intent=release gate`.
- Passing relevant automated checks or explicit skip reasons.
- Fresh behavioral tests for touched auth/session/MFA, tenant, payment, storage, public endpoint, AI/tool, plugin/MCP, and privacy flows.
- Scanner or project audit output for changed dependencies, secrets, and compliance surfaces.
- Adapter checks for matching frameworks.
- Risk gate notes for destructive, production, permissions, secrets, or customer-facing claim changes.
- Documented residual risk and owner.

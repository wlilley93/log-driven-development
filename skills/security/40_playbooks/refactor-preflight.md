---
name: refactor-preflight
type: playbook
domain: security
summary: Security dispatch workflow for refactoring engines.
---

# Refactor Preflight

Use this playbook when Security-Suite is called as a subworkflow of the refactoring suite.

1. Receive `scope`, `change_intent`, `security_surfaces`, and `repo_fingerprint` from the refactoring engine.
2. If `security_surfaces` is empty, verify the classification evidence. Return `no-security-dispatch-required` only when the scope has no auth/session, authz/tenant, input, secrets, dependency, payment, storage, plugin/MCP, AI/tool, privacy, compliance, SQL/data-access, or release-risk surface.
3. Use `../50_references/dispatch-matrix.md` to select only matching skills and adapters.
4. Run evidence collection with the smallest sufficient scope. Do not widen from a refactor surface to a full audit unless the evidence shows a shared security boundary is affected.
5. Return findings in `../50_references/finding-schema.md` shape.
6. Return `required_verification` for every touched security surface. Auth/session/MFA, tenant isolation, secrets/crypto, payments, public endpoints, and tool/MCP changes require explicit abuse-case verification before refactoring close.
7. Return `adapter_notes`, `residual_risk`, and `skips`.

## Refactoring Response Shape

```json
{
  "findings": [],
  "required_verification": [],
  "adapter_notes": [],
  "residual_risk": [],
  "skips": []
}
```

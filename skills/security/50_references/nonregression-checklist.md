# Nonregression Checklist

Use before claiming the suite, a security review, or a refactoring run is complete.

## Suite Structure

- Exactly one canonical active suite folder exists: `Skills/Development/Security-Suite`.
- Standalone workflow is documented in `WORKFLOW.md`.
- Refactoring subworkflow is documented in `40_playbooks/refactor-preflight.md`.
- Full audit workflow is documented in `40_playbooks/full-security-audit.md`.
- Dispatch matrix, finding schema, severity rubric, threat model, and coverage matrix exist.

## Coverage

- Each previously scattered security skill is incorporated, adapted, preserved as legacy source, or explicitly excluded as a duplicate/archive.
- Core engineering coverage includes auth/session/MFA, authz/tenant, input validation, secrets/crypto, SQL/data access, dependencies/supply chain, license compliance, AI/tool security, plugin/MCP, privacy, compliance evidence, vulnerability assessment, and risk gates.
- Project/framework coverage includes SOC2, NextAuth, Stripe, Supabase, plugin/MCP, procurement, regulatory-privacy, and support escalation adapters.

## Refactoring Integration

- Refactoring classification records Security-Suite dispatch payloads or explicit `no-security-dispatch-required` evidence.
- Refactoring review captures Security-Suite findings, required verification, adapter notes, and residual risk.
- Refactoring plan resolves, defers, or excludes confirmed Security-Suite findings explicitly.
- Refactoring verify runs or records Security-Suite-required verification.

## Evidence Quality

- Findings use the shared schema.
- Static scans and compliance scripts are not treated as behavioral proof.
- HIGH+ findings include a concrete fix and failing test or verification scenario.
- Hypotheses are not implemented as confirmed defects.

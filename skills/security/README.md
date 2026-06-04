---
name: Security-Suite
type: suite
domain: security
summary: Canonical security review, audit, adapter, and verification suite for engineering work.
status: live
---

# Security-Suite

Security-Suite is the single authoritative folder for security review and audit workflows. Other engines, including the refactoring suite, call this suite instead of duplicating security methodology.

## Use When

- A change touches authentication, sessions, MFA/2FA, authorization, tenant or workspace scoping.
- A change accepts external input, parses uploads, handles webhooks, mutates browser-backed state, or changes CSRF/CORS behavior.
- A change modifies secrets, encryption, signing, token handling, logging, audit trails, dependency manifests, payments, storage policies, plugins, MCP tools, or compliance evidence.
- A full security audit, release gate, incident review, or SOC2/security posture update is requested.

## Dispatch Contract

Callers provide:

- `scope`: files, routes, services, components, schemas, or dependencies under review.
- `change_intent`: refactor, feature, fix, cleanup, release gate, incident response, audit.
- `security_surfaces`: detected surfaces such as auth-session, authz-tenant, input-validation, secrets-crypto, dependency-supply-chain, payment, storage, plugin-mcp, privacy, compliance.
- `repo_fingerprint`: framework and product indicators such as NextAuth, Stripe, Supabase, SOC2 scripts, plugin/MCP.

Security-Suite returns:

- `findings`: severity, confidence, evidence, exploit scenario, suggested fix, and required verification.
- `required_verification`: exact tests, scripts, scans, or manual checks needed before close.
- `adapter_notes`: project or framework-specific checks applied.
- `residual_risk`: unresolved risk, false-positive risk, or explicitly deferred findings.

## Structure

- `WORKFLOW.md`: standalone and refactoring-subworkflow execution model.
- `10_skills/`: reusable review skills.
- `20_agents/`: reviewer roles used by engines.
- `30_adapters/`: project, framework, and vendor adapters.
- `40_playbooks/`: full workflows for audits, refactor preflight, incident posture, and release gates.
- `50_references/`: shared schemas, severity rubric, threat model template, and coverage matrix.
- `60_tools/`: scanner and tooling orchestration.
- `scripts/`: suite self-verification checks.
- `methodology.md`, `tools.md`, `generator.md`: canonical full-audit methodology and tooling references.

## Workflow

Run `WORKFLOW.md` for every invocation. It defines the shared stages:

1. Intake.
2. Fingerprint.
3. Dispatch.
4. Evidence.
5. Synthesis.
6. Verification.
7. Close.

Standalone mode uses `40_playbooks/standalone-security-review.md` for bounded reviews or `40_playbooks/full-security-audit.md` for broad audits. Refactoring-subworkflow mode returns `findings`, `required_verification`, `adapter_notes`, `residual_risk`, and `skips` to the refactoring suite.

## Default Skill Dispatch

| Surface | Core skills | Optional adapters |
|---|---|---|
| Auth, sessions, MFA/2FA | `auth-session-review`, `security-baseline-review` | `nextauth-adapter`, `house-framework-adapter` |
| Authorization, RBAC, tenant isolation | `authz-tenant-isolation-review` | `house-framework-adapter`, `supabase-adapter` |
| External input, uploads, webhooks | `input-validation-review`, `security-baseline-review` | `stripe-adapter`, `supabase-adapter`, `house-framework-adapter` |
| SQL, ORM, analytics, migrations | `sql-data-access-review`, `authz-tenant-isolation-review` | `supabase-adapter`, `house-framework-adapter` |
| Secrets, crypto, signing, tokens | `secrets-crypto-review` | `project-soc2-adapter` |
| Dependencies, licenses and supply chain | `dependency-supply-chain-review`, `license-compliance-review` | `plugin-mcp-adapter` |
| AI, prompt injection, agents, tools | `ai-prompt-tool-security-review`, `plugin-mcp-sandboxing-review` | `plugin-mcp-adapter`, `house-framework-adapter` |
| Payments | `security-baseline-review`, `input-validation-review` | `stripe-adapter` |
| Storage, RLS, signed URLs | `authz-tenant-isolation-review`, `secrets-crypto-review` | `supabase-adapter` |
| Plugin or MCP permissions | `plugin-mcp-sandboxing-review`, `secrets-crypto-review` | `plugin-mcp-adapter` |
| Privacy and governance | `privacy-governance-review` | `procurement-security-adapter`, `regulatory-privacy-adapter` |
| Support or customer security escalation | `privacy-governance-review`, `compliance-evidence-review` | `support-security-escalation-adapter` |
| Compliance or SOC2 evidence | `compliance-evidence-review`, `vulnerability-assessment-review` | `project-soc2-adapter`, `regulatory-privacy-adapter` |
| Destructive or production security-sensitive action | `risk-safety-gates` | matching project adapter |
| Exploit validation / triage AI-pentest output (release-candidate gate) | `exploit-validation-review`, `vulnerability-assessment-review` | uses `60_tools/shannon-ai-pentester` |

## Output Standard

Every substantive finding must use `50_references/finding-schema.md`. Findings without direct evidence are hypotheses and must not be implemented as confirmed issues.

## Self-Verification

Run:

```bash
bash "Skills/Development/Security-Suite/scripts/verify-security-suite.sh"
```

The verifier checks required suite files, the single canonical top-level security folder, and stale lowercase `security-suite` references in active refactoring paths.

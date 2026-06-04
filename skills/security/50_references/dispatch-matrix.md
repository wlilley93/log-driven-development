# Dispatch Matrix

| Detected surface | Dispatch | Adapters |
|---|---|---|
| Auth, sessions, MFA/2FA, cookies, route protection | `auth-session-review`, `security-baseline-review` | `nextauth-adapter`, `project-adapter` |
| Roles, permissions, tenant/workspace/org scoping | `authz-tenant-isolation-review`, `sql-data-access-review` | `project-adapter`, `supabase-adapter` |
| Public endpoints, webhooks, forms, uploads, parsers | `input-validation-review`, `security-baseline-review` | `stripe-adapter`, `supabase-adapter`, `project-adapter` |
| SQL, ORM, analytics, exports, migrations | `sql-data-access-review`, `authz-tenant-isolation-review` | `supabase-adapter`, `project-adapter` |
| Secrets, crypto, signing, tokens, reset links | `secrets-crypto-review`, `risk-safety-gates` | `nextauth-adapter`, `project-adapter` |
| Dependencies, packages, vendored code, license | `dependency-supply-chain-review`, `license-compliance-review` | `plugin-mcp-adapter` |
| Agents, RAG, prompt injection, MCP, tool calling | `ai-prompt-tool-security-review`, `plugin-mcp-sandboxing-review` | `plugin-mcp-adapter`, `project-adapter` |
| Payments, billing, subscriptions, invoices | `security-baseline-review`, `input-validation-review` | `stripe-adapter` |
| Storage, RLS, signed URLs, realtime | `authz-tenant-isolation-review`, `secrets-crypto-review` | `supabase-adapter` |
| Privacy, PII, deletion/export, confidentiality | `privacy-governance-review`, `risk-safety-gates` | `support-security-escalation-adapter`, `procurement-security-adapter`, `regulatory-privacy-adapter` |
| SOC2, ISO, audit evidence, security claims | `compliance-evidence-review`, `vulnerability-assessment-review` | `project-adapter`, `procurement-security-adapter` |
| Release gate, incident, broad audit | `vulnerability-assessment-review`, `exploit-validation-review`, all matching surface skills | all matching adapters |
| Exploit validation, AI-pentest output, prove-by-exploitation, triage scanner findings | `exploit-validation-review`, `vulnerability-assessment-review` |  -  (uses `../60_tools/shannon-ai-pentester`) |
| Multi-tenant agent platform (shared Docker net, per-tenant brokers, SSO subdomains) | `authz-tenant-isolation-review`, `shared-secret-scoping-review`, `plugin-mcp-sandboxing-review`, `ai-prompt-tool-security-review`, `security-baseline-review`, `dns-domain-security-review` | `project-adapter` |

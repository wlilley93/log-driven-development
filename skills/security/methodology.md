---
tags:
  - claude
  - skills
  - global
  - security
  - methodology
created: '2026-04-30'
updated: '2026-04-30'
scope: global
status: live
parent: Security-Suite
---
# Security Audit Methodology (codebase-neutral)

The reusable 70% of the rev 4 audit prompt. Imports nothing project-specific - those bits come from a generated `security-audit.md` per repo (see `generator.md`).

Use this directly when running an ad-hoc audit on a codebase that doesn't yet have a generated skill. Otherwise, the project-specific skill imports this file and adds its own §0/§1/§8/§9/§10 parameter blocks.

---

## How to use this file

This is the codebase-neutral methodology. It references the running codebase via named parameters (`repo_root`, `schema_path`, `encryption_module`, capability flags like `has_agents`). Two ways to supply them:

- **With a project skill**: read the project's `security-audit-<name>.md` first; it has a Project context table and per-section substitutions. Then walk this methodology, mentally substituting as you go.
- **Without one**: fill the table below inline before starting. Then walk this methodology with those values held in working memory.

Either way, **the project skill never duplicates this body** - it provides parameters, per-section substitutions, and reasoning extensions only. If a project skill repeats methodology prose, it's gone stale; re-run `generator.md`.

### Required parameters

| Parameter | Description | Example |
|---|---|---|
| `repo_root` | Absolute path to the repo | `/path/to/repo` |
| `package_manager` | npm / pnpm / yarn / pip / poetry / cargo / go / bundler | `npm` |
| `schema_path` | ORM schema file or migrations dir | `prisma/schema.prisma` |
| `env_example` | Declared-env file | `.env.example` |
| `encryption_module` | File defining `encrypt`/`decrypt` primitives | `src/lib/encryption.ts` |
| `internal_docs_dir` | SOC 2 / spec / runbook root | `internal-docs/` |
| `public_docs_url` | Public docs URL if any | `https://docs.example.com` |
| `marketing_urls` | Landing pages with security claims (list) | `https://example.com` |
| `soc2_evidence_dir` | SOC 2 evidence path if any | `internal-docs/security/` |

### Capability flags (drive the applicability matrix below)

| Flag | Meaning |
|---|---|
| `multi_tenant` | App has tenant isolation (workspace_id / org_id / account_id on most models). |
| `has_agents` | App has AI agents, MCP bridge, or tool-calling LLMs. |
| `has_signing` | App has e-signatures or tamper-evident workflows. |
| `has_sso` | App has SAML/OIDC/SCIM. |
| `has_byok` | App stores per-user/org provider credentials. |
| `has_file_uploads` | App accepts user file uploads. |

## Section applicability matrix

| Section | Always | Skip when |
|---|---|---|
| §0 dependency posture | yes | - |
| §1 secrets handling | yes | - |
| §2 agent/API key bridge | - | `has_agents=false` |
| §3 tenant isolation | - | `multi_tenant=false` |
| §4 agent autonomy | - | `has_agents=false` |
| §5 prompt injection | - | `has_agents=false` (classical input validation merges into §6) |
| §6 authn/authz | yes | - |
| §7 file upload / parsing | - | `has_file_uploads=false` |
| §8 SOC 2 gaps | yes | - |
| §9 public docs leakage | - | `public_docs_url` not set |
| §10 claim vs code | yes | - |
| §11 ranking | yes | - |
| §12 plan | yes | - |
| §13 self-verification | yes | - |

For skipped sections, state explicitly in the output: `§N skipped - <flag>=false` so the deliverable is auditable.

---

## META - failure modes from prior audits, fix in your workflow

1. **ACCEPTED "CONFIRM X" AS A FIX.** Every claim that names a route, function, or env var must be backed by an inline read of that file in this session. If you write "verify X" or "confirm X" in a FIX, the finding is unfinished.

2. **CROSSED SUBSYSTEM BOUNDARIES WITHOUT TRACING THE CALL GRAPH.** Before claiming a multi-subsystem vulnerability, identify the specific call site where subsystem A invokes subsystem B. If you can't cite the call site, you are speculating.

3. **RANKED TOP-N BY (likelihood × blast × time-to-fix).** Time-to-fix produces a fix-order, not a risk-order. Split: §11 = exploitation risk; §12 = this-week plan.

4. **DIDN'T SWEEP CLAIMED-BUT-ABSENT FEATURES.** Features named in docs/marketing but never implemented are silent procurement landmines. §8c (internal docs) and §10 (external claims) make this a deliberate sweep.

5. **NO CHOKEPOINT-BYPASS SWEEP.** A chokepoint that's PASS in isolation can be bypassed by a caller that goes around it. For each chokepoint cited as PASS, enumerate every caller of the underlying primitives. Bypassed callers are findings.

6. **NO FINAL SELF-VERIFICATION.** Peer review catches real errors. §13 bakes that in.

---

## THREAT MODEL ASSUMPTIONS (state before starting)

Customise the in-scope and out-of-scope lists for the codebase. State both explicitly.

**Default in scope:**
- External attackers (network, credential theft, phishing of admins).
- Insider attackers (rogue admin, exfil via legitimate access).
- Lower-privilege end users (free tier, portal users, customers of customers).
- Prompt injection via documents, webhooks, KB content, tool results (skip if `{has_agents}=false`).

**Default out of scope (state explicitly so the auditor doesn't waste cycles):**
- Package-registry supply-chain compromise (npm/PyPI publishing pipeline).
- Cloud control-plane compromise (assume hosting provider is honest).
- Physical access to operator devices.
- Compromise of the operator's identity provider (covered by SSO threat model separately).

If a vulnerability's only exploit path requires an out-of-scope precondition, mark it INFO not HIGH.

---

## DELIVERABLE FORMAT

Per finding: `SEVERITY [CRITICAL|HIGH|MED|LOW|INFO] | FILE:LINE | ISSUE | FIX`

Section closes with ≥1 finding or `PASS - <one-line evidence with file:line>`.

For HIGH+ findings, the FIX must include:
- Either (a) concrete code change writable in <1 day, OR (b) explicitly flagged "project-scoped, ~X weeks, prerequisites: [list]". No hand-waving.
- The test name or one-line test description that would fail without the fix. Untested fixes are barely worth more than untested vulnerabilities.

For findings under §5 (prompt injection) where bypasses succeed, the FIX must be STRUCTURAL (envelope tags + system prompt update), not pattern-additive. Adding more regex patterns to a blocklist is not an acceptable fix.

Total cap: 3000 lines.

---

## SECTION 0 - DEPENDENCY POSTURE

Run last (after §1-§9). Mechanical work; don't burn reasoning budget at the start.

**Before reasoning, run vibescan** (`tools.md`) for the OSS multi-scanner pass. Use its output as input to this section rather than re-running each tool.

a) Run the package-manager audit (`{package_manager} audit --omit=dev --audit-level=moderate` for npm; equivalent for others). List every advisory with severity. For each, grep the codebase for the vulnerable surface and answer "is this exploitable in our deployment?" Downgrade severity if the surface isn't reached. Cite the grep.
b) For each unfixable advisory: practical exposure in one sentence; recommend swap dep / accept with mitigation / wait for upstream.
c) Outdated check (`{package_manager} outdated` or equivalent) for security-relevant packages (auth, crypto, parsers, serialisation). Flag anything >2 majors behind.

---

## SECTION 1 - SECRETS HANDLING

**SECRET DISCOVERY (run first):**
Before applying the per-class checks, enumerate the actual secret surface:
- Grep `{schema_path}` for encrypted columns (ORM-specific markers - `encrypted` prefix, `@encrypted` annotation, `EncryptedString` types, etc.).
- Grep `{env_example}` for declared secret env vars (pattern: `^[A-Z_]+_(SECRET|KEY|TOKEN|PASSWORD)=`).
- Grep the source tree for `process.env.*_(SECRET|KEY|TOKEN|PASSWORD)` (or language equivalent) - any secret read at runtime that doesn't appear in `{env_example}` is drift, itself a finding.

The list below is a starting point, not a ceiling. If discovery turns up a secret class not enumerated here, add it and run the per-class checks against it.

**Common classes to look for:**
- Cloud-provider tokens (AWS/GCP/Azure/Cloudflare).
- BYOK provider credentials (Anthropic/OpenAI/etc.).
- Inbound integration keys (API keys customers paste in).
- SSO/SCIM credentials.
- DB connection strings, Redis URLs, queue credentials.
- Webhook signing secrets (every integration).
- JWT signing keys / session secrets.
- Tamper-evidence keys (e-signature, audit log) - if `{has_signing}=true`.

**Per secret class:**
a) Storage: DB column / env var / KMS / secrets manager.
b) Encryption algorithm + key location. Envelope encryption with per-tenant DEKs, or single global key?
c) Master/wrapping key location. Same process / same VPC / KMS HSM?
d) Every code path that calls the decryption function. List them. Flag any that decrypt-then-cache beyond a single request lifecycle.
e) Secret leakage paths: logs, error messages, observability, stack traces, audit log entries, response bodies, redirect URLs, queue payloads. Grep for variable name and decrypted-value path.
f) Rotation: documented + tested? Find the code that would change. None = HIGH.
g) Scope (per-secret): what permissions does the live token actually carry? If not assessable from code, mark NOT ASSESSABLE FROM REPO and list the dashboard check that must run out-of-band.
h) For EACH decryption call site, trace the plaintext: returned to client? logged? stored unhashed? cached beyond request? Cite each.
i) Observability: search for Sentry / Datadog / Honeycomb / etc. integrations. If present, find the scrub config; confirm secret-shaped fields redacted. If absent, that itself is a finding (no centralised error capture = SOC 2 CC7.2 gap).
j) Console-log sweep over auth / encryption / agent / signing modules - flag any log statement that includes credential/key/token/email identifiers.

---

## SECTION 2 - AGENT / API KEY BRIDGE

*Applicability: requires `has_agents=true`.*

For any tool-calling bridge endpoint (MCP, custom agent API, etc.):
a) Bearer token validation per request - constant-time compare?
b) Autonomy level checked PER TOOL CALL or only at session start? Find the enforcement code. Single-check session-cached enforcement = CRITICAL.
c) Spend caps - enforced where? TOCTOU between cap check and LLM call? Can a single request exceed cap if it triggers a long agent loop?
d) Tool surface - does the bridge key inherit the user's full workspace permissions, or is there a separate principal? Inheritance = exfil = full workspace compromise.
e) Rate limiting per key - distributed (Redis) or per-instance (bypassable by hitting different pods)?
f) Key revocation - in-flight agent sessions die immediately, or run to completion?
g) Logging - every tool call logged with key ID, tenant, tool name, args hash? Args hashed/redacted (may contain PII)?

**CHOKEPOINT-BYPASS SWEEP (mandatory):**
The enforcement chain is typically `executeBridgeTool() -> enforceAccess() -> checkRateLimit() -> logSecurityEvent()`. List every other caller of the underlying tool-execution primitive in the codebase. Classify each: "goes through bridge gates" (PASS) or "bypasses bridge gates" (finding). Don't assume - grep and read.

---

## SECTION 3 - TENANT ISOLATION

*Applicability: requires `multi_tenant=true`.*

a) Every ORM query touching a tenant-scoped model - does it have a workspace_id/org_id filter? Grep all `findMany`/`findFirst`/`findUnique` (or language equivalent) without tenant filter. List every offender.
b) Middleware/guard that injects tenant filter automatically, or does every query author have to remember? Latter = HIGH (matter of when).
c) File storage - upload paths namespaced by tenant? Tenant A signed-URL request for tenant B's file by ID enumeration?
d) Background jobs / agent tasks - worker re-validates tenant context, or trusts the job payload? Poisoned queue = cross-tenant write.
e) Search/RAG - vector index filters by tenant at query time, or only at indexing? Query-time filter bug = silent cross-tenant leak.
f) Bridge keys (if `{has_agents}=true`) - key issued in tenant A: any path to read tenant B data? Check tool implementations.
g) Identity HMAC (if applicable) - find the code path. Verify HMAC key is not the same as any other system key.

**PERMISSION-CHECK SHORT-CIRCUIT SWEEP (mandatory):**
For every `getXxxPermission` / `requireXxxAccess` helper, check whether it short-circuits to manager/admin/owner before consulting workspace/org scope. If yes, find every CALLER and verify the caller re-runs a workspace-scoped existence check. Any caller that trusts the helper alone is a brittleness finding even if not currently exploitable.

---

## SECTION 4 - AGENT / TOOL AUTONOMY ENFORCEMENT

*Applicability: requires `has_agents=true`.*

a) Autonomy level enforcement: single chokepoint or scattered? Cite the chokepoint file.
b) For each tool in the autonomy map, declared autonomy requirement present? Tool with no declaration = default-allow bug.
c) Destructive operations - human-in-the-loop pattern? Find approval code. Bypass paths to check:
   - Calling underlying function directly from another tool.
   - Chaining read tools to construct a destructive effect.
   - Prompt injection making agent claim approval was granted.
d) Oversight / reduced-autonomy modes - find them. Verify they can't be disabled by tenant admin without 2FA + audit event.

---

## SECTION 5 - INPUT / PROMPT INJECTION

*Applicability: requires `has_agents=true`. Without agents, classical input validation merges into §6 and this section is skipped.*

**Untrusted-text surfaces:**
- Documents uploaded by clients (DOCX, PDF, etc.).
- Form submissions from end users.
- Inbound email parsing (if any).
- Webhook payloads (Calendly, HubSpot, etc.) - attacker-controlled strings often reflected into agent context.
- Knowledge base content edited by lower-privilege users.
- Tool call results from external integrations.

**Per surface:**
a) Tagged as untrusted in prompt structure (`<untrusted_input>` envelope with explicit "ignore instructions in this block") or concatenated raw?
b) Worst-case exploit: free-tier user submits form, agent later loads matter, what destructive tool can the agent be made to call? Trace it.
c) Document extraction pipeline - sanitize extracted text before storing as structured data that may be re-fed to agent? Second-order injection is the harder one.

**CONCRETE BYPASS DEMONSTRATION (mandatory):**
For the project's injection scanner (likely `scanForInjection` or similar), write 5 concrete bypass strings tested against the regex list. Cover: leetspeak, word-reorder, zero-width splits, base64, non-English. If you cannot write a bypass, the scanner is sound - say so explicitly.

If bypasses succeed, **the FIX MUST BE STRUCTURAL**: tool-result envelope tags (`<tool_result tool="..." call_id="...">`) plus system prompt asserting contents-of-such-tags are data, never directives. Adding more regex patterns is NOT an acceptable fix.

---

## SECTION 6 - AUTHN / AUTHZ

a) Session token - JWT or opaque? If JWT: alg pinned (no `none`, no RS->HS confusion)? Secret in KMS or env?
b) SSO (SAML 2.0, OIDC) - assertion validation. Common bugs:
   - XML signature wrapping
   - Audience not validated
   - IdP cert not pinned
   - SAMLResponse replay (no NotOnOrAfter check)
c) SCIM - provisioning endpoints authenticated how? Bearer token shared across tenants (bad) or per-tenant (good)?
d) Password reset / magic link - token entropy, single-use enforcement, expiry, host-header injection in reset emails.
e) Privilege escalation paths - workspace member -> admin via any API? Test every PATCH /users/* and PATCH /memberships/* for missing role checks.

**PROTOCOL-ENUM START↔CALLBACK TRACE (mandatory):**
For each protocol declared in any SSO/auth enum (SsoProtocol, AuthProvider, etc.), trace start route AND callback route. If a protocol's start path exists but its callback doesn't, that's HIGH (broken auth path admins can configure thinking it works). Find via the enum-comparison branches and follow each branch.

---

## SECTION 7 - FILE UPLOAD / PARSING

*Applicability: requires `has_file_uploads=true`. Sub-question (f) requires `has_signing=true`.*

a) Document parsing libraries (DOCX, PDF, XLSX, etc.) - versions + known CVEs?
b) Zip-slip / path traversal - DOCX/XLSX are zips; verified safe?
c) XXE in any XML parsing?
d) Server-side template rendering - any path evaluating user-controlled strings as expressions? (Handlebars/EJS/Jinja with attacker template = RCE.)
e) Signed download URLs - tenant-scoped, time-limited, unpredictable?
f) E-signature tamper-evidence (if `{has_signing}=true`) - cryptographic primitive? Per-document or global signing key?

**MAGIC-BYTE LITERALISM CHECK (mandatory):**
For the project's file-content validation function, read the implementation. Verify it actually inspects binary signatures (`\x89PNG`, `%PDF`, `PK\x03\x04`, `\xFF\xD8\xFF`). Substring-search for `<svg`, `<html` in a UTF-8-decoded prefix is NOT magic-byte validation - flag and recommend the `file-type` package (or language equivalent).

---

## SECTION 8 - SOC 2 TYPE 2 GAPS (CODE-LEVEL EVIDENCE)

If the project has a dedicated SOC 2 audit skill (e.g. `project-soc2-audit`), invoke it for the mechanical control checks and treat its output as input to this section. Otherwise run inline.

**Security:**
- Audit log: EVERY mutation logged with actor, tenant, timestamp, before/after? Grep write paths missing audit calls.
- Access reviews: query exists for "all users with role X across all tenants"?

**Availability:**
- Health checks (must check ALL critical dependencies, not just primary DB).
- Graceful shutdown / SIGTERM handlers for all worker processes.

**Processing Integrity:**
- Idempotency on side-effecting endpoints (especially webhooks and signing).
- Input validation: schema validators (Zod/Pydantic/etc.) on every endpoint?

**Confidentiality:**
- Data classification - PII tagged in schema for retention/deletion?
- Right-to-erasure - find GDPR delete endpoint. Does it actually delete from backups, vector index, audit logs (or are audit logs exempt + documented)?

**Privacy:**
- Cookie consent, retention enforcement (find the cron + the per-tenant retention config).

a) **BACKUP CRITICALITY** (own check, not a sub-bullet):
   Search scripts/, cron-runner/, infra/, app/api/cron/ for any automated DB export/dump targeting durable storage outside the primary DB provider. None exists = HIGH-bordering-existential. Provider PITR is RPO not BCP. A provider-account compromise has no recovery path.

b) **CASCADE-DELETE AUDIT SWEEP:**
   Grep for `auditLog.delete*` (or equivalent) - confirm every call routes through audit-retention-service (archive-before-delete). The retention cron is fine; workspace/org deletion paths often forget to use it.

c) **MISSING-FEATURE SWEEP (INTERNAL DOCS):**
   Grep `{internal_docs_dir}` and `CLAUDE.md`/`README.md` for: "GDPR", "right to erasure", "Art. 17", "user delete", "data export", "RoPA", "DPA", "SAML", "MFA", "WebAuthn", "audit retention", "automated backup". For each hit, verify implementation exists. Claimed-but-absent = HIGH.

d) **DEAD-CODE / UNADVERTISED-SURFACE SWEEP:**
   Grep for `process.env.NODE_ENV !== 'production'`, `x-internal`, `TODO.*remove`, `FIXME.*before prod` in route handlers. Half-built features that bypass normal auth, debug endpoints, dev fallbacks active in prod = findings.

---

## SECTION 9 - PUBLIC DOCS LEAKAGE

*Applicability: requires `public_docs_url` to be set.*

Fetch each page under `public_docs_url` (focus on `/api/*`, `/security/*`, `/architecture/*`). For each, flag:
a) Internal endpoint paths not meant to be public.
b) Specific security control descriptions giving attackers a roadmap (e.g. "rate limit is 100 req/min" - useful for tuning attack speed).
c) Architecture pages revealing runtime details beyond what an attacker needs to integrate.
d) Error message catalogues revealing internal logic.
e) Internal hostnames, S3 bucket names, queue names, deployment IDs.
f) Code samples with real (even rotated) keys, tenant IDs, user IDs.

---

## SECTION 10 - CLAIM VS CODE (EXTERNAL CLAIMS)

§8c covers internal docs. This section covers external/customer-facing claims - because those carry contractual and procurement consequences, not just engineering-discipline ones.

**Sources:**
a) `{public_docs_url}` - every page mentioning security, auth, autonomy, compliance, encryption, SSO, MFA, SOC 2.
b) `{marketing_urls}` - landing copy (claims like "SOC 2 Type 2 ready", "SAML 2.0", "BYOK", "scoped tokens", "per-key spend caps", "tenant isolation").

Per claim: matches code (PASS), partial (MED), absent (HIGH - procurement blocker), contradicted (CRITICAL - misrepresentation).

---

## SECTION 11 - TOP N BY EXPLOITATION RISK

Rank by (likelihood × blast radius). Time-to-fix is §12's concern.

Per finding:
- One sentence.
- Exploit chain in 3 bullets (preconditions, action, blast).
- Why this beats the next-ranked finding.

`N = max(5, ceil(0.15 × HIGH+_findings))`. Don't pad beyond what the audit warrants; don't truncate if there are 15 HIGH+ findings worth ranking.

---

## SECTION 12 - THIS-WEEK PLAN

Separate decision from §11. Order findings by (risk / time-to-fix).
- Day 1: items <2 hours each. Cap at 6 - above that, context-switch overhead ships none of them.
- Day 2-5: items <1 day each.
- Larger items: scheduled as "project-scoped, week N+1, prerequisites: [list]".

---

## SECTION 13 - SELF-VERIFICATION (mandatory final pass)

Pick HIGH+ findings most likely to be wrong. Quantity: ≥10% of HIGH+ findings, minimum 3, maximum 8.

**Selection criteria** (state which applies for each):
- Crossed subsystem boundaries.
- Based on a single grep result.
- Hedged language ("appears to", "likely", "presumably").
- Fix would be most embarrassing to ship if wrong.

Re-read the relevant code paths inline. Per finding:
- **Confirmed**: keep, note "self-verified at file:line".
- **Wrong**: remove, replace with one-line note explaining why.
- **Partially wrong**: downgrade severity, narrow the claim.

Empty self-verification = audit not finished.

---

## RULES OF ENGAGEMENT

- Read code before claiming. Cite file:line for every finding.
- "Verify X" / "confirm X" in a FIX = unfinished finding.
- For chokepoints cited as PASS: enumerate callers; bypassed callers are findings.
- For HIGH+ findings: FIX must include code change (or project-scope) AND test name/description that would fail without the fix.
- For §5 prompt-injection findings where bypasses succeed: FIX must be structural (envelope tags + system prompt), not pattern-additive.
- Severity reflects production exposure. Out-of-scope-precondition findings = INFO not HIGH.
- §0 runs last in execution despite numbering - mechanical work, don't burn reasoning budget.
- §13 must contain its full self-verification quota. Don't skip.
- Stop conditions stand. PASS lines stand. No padding, no frameworks, no "next steps" essays.

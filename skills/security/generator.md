---
tags:
  - claude
  - skills
  - global
  - security
  - generator
created: '2026-04-30'
updated: '2026-04-30'
scope: global
status: live
parent: Security-Suite
---
# Security Audit Skill Generator

A meta-skill that produces a project-specific security audit skill by inspecting a repo and emitting the 30% project-specific layer that pairs with `methodology.md`.

Run **once per project** at adoption time. Re-run when the repo's auth/schema/docs surface changes materially (new ORM, new public docs URL, addition of agent/signing subsystems).

## When to use

- "Set up security tooling for this repo"
- "Generate a security audit skill for [project]"
- "We just adopted [methodology] - tailor it for this codebase"

## Output

A single markdown file at `skills/security-audit-<repo>.md` in the project repo, with:
1. Frontmatter (`name`, `description`, `tags`, `project`, `scope`, `status`, `parent: Security-Suite`).
2. **Invocation runbook** - the steps the auditor executes.
3. **Threat model** - in-scope / out-of-scope (replaces the methodology defaults).
4. **Project context** - parameter table populated from discovery.
5. **Per-section substitutions** - one row per methodology section with concrete file/function/path values.
6. **Reasoning extensions** - 3-7 project-specific exploit shapes the methodology can't anticipate.
7. **Convergence rationale** - link back to `methodology.md` for rev history.

The output **never duplicates the methodology body**. If a generated skill repeats prose from `methodology.md`, the generator regressed - fix it.

## Discovery sweep

Run these commands against `repo_root`. Replace `$ROOT` with the absolute path. Adapt to language (defaults are Node/TS - see "Language adaptations" at the bottom).

### Stack basics

```bash
# Package manager
ls "$ROOT" | grep -E "package-lock\.json|pnpm-lock\.yaml|yarn\.lock|pyproject\.toml|Cargo\.toml|go\.mod|Gemfile\.lock"

# Runtime + framework (Node)
jq -r '.engines.node // "unset", (.dependencies | keys[])' "$ROOT/package.json" | head -20
```

### Schema and secrets

```bash
# Schema location
ls "$ROOT/prisma/schema.prisma" "$ROOT/alembic" "$ROOT/db/schema.rb" "$ROOT/migrations" 2>/dev/null

# Encrypted columns (Prisma example - adapt for SQLAlchemy / ActiveRecord / etc.)
grep -nE "encrypted[A-Z]|@encrypted|EncryptedString" "$ROOT/prisma/schema.prisma"

# Declared secret env vars
grep -E "^[A-Z_]+_(SECRET|KEY|TOKEN|PASSWORD)=" "$ROOT/.env.example"

# Runtime secret reads (the drift detector)
grep -rnE "process\.env\.[A-Z_]+_(SECRET|KEY|TOKEN|PASSWORD)" "$ROOT/src" "$ROOT/app" 2>/dev/null

# Encryption module
grep -rln "function encrypt\b\|export function encrypt\|export const encrypt" "$ROOT/src/lib" 2>/dev/null
```

### Docs and claims

```bash
# Internal docs root
ls -d "$ROOT/internal-docs" "$ROOT/docs/internal" "$ROOT/private-docs" 2>/dev/null | head -1

# Public docs URL (grep CLAUDE.md, README, deploy configs)
grep -hoE "https://docs\.[a-z0-9.-]+" "$ROOT/CLAUDE.md" "$ROOT/README.md" "$ROOT/package.json" 2>/dev/null | sort -u

# Marketing URLs (adapt the product-name token to the project)
grep -hoE "https://[a-z0-9.-]+\.(app|com|io|ai)" "$ROOT/CLAUDE.md" "$ROOT/README.md" 2>/dev/null | sort -u

# SOC 2 evidence dir
ls -d "$ROOT/internal-docs/security" "$ROOT/internal-docs/compliance" "$ROOT/internal-docs/audits" "$ROOT/audits" "$ROOT/soc2" 2>/dev/null | head -1

# SOC 2 audit runner (project-specific scripts)
ls "$ROOT/scripts/audit-"*".sh" 2>/dev/null
```

### Capability flags

```bash
# multi_tenant - schema has workspaceId / organizationId / tenantId / accountId
grep -cE "workspaceId|organizationId|tenantId|accountId" "$ROOT/prisma/schema.prisma"

# has_agents - look for agent loops, MCP, tool-calling SDK
grep -rln "executeAgent\|runAgentLoop\|@anthropic-ai/sdk\|@modelcontextprotocol\|/api/mcp" "$ROOT/src" "$ROOT/app" 2>/dev/null | head -5

# has_signing - hash-chain, e-sign, tamper-evident
grep -rln "hash-chain\|hashChain\|Merkle\|tamper-evident\|e-sign\|docusign" "$ROOT/src" "$ROOT/app" 2>/dev/null | head -5

# has_sso
grep -rln "SAML\|OIDC\|SCIM\|SsoProtocol\|SsoConfig" "$ROOT/src" "$ROOT/app" 2>/dev/null | head -5

# has_byok - per-user/org provider creds
grep -rln "BYOK\|AiCredential\|UserAiConfig\|WorkspaceAiConfig" "$ROOT/src" "$ROOT/prisma" 2>/dev/null | head -5

# has_file_uploads
grep -rln "multer\|busboy\|formidable\|UploadedFile\|multipart" "$ROOT/src" "$ROOT/app" 2>/dev/null | head -5
```

After the mechanical sweep, **read CLAUDE.md (and key architecture specs) end to end**. The reasoning extensions live there - they're the part the discovery commands cannot find.

## Reasoning extension extraction

Reasoning extensions are project-specific exploit shapes that the methodology cannot anticipate generically. Strong candidates:

1. **Domain-specific abuse paths** - what does this app *do* that creates a non-generic exploit shape? E.g. cross-workspace consent (CSP-style), tamper-evident audit chains, public document portals, RAG over user uploads.
2. **Bidirectional integrations** - partner systems that authenticate inbound calls *as* an internal principal (a shared outbound bearer secret that also authenticates inbound calls is the canonical pattern).
3. **Half-built features in CLAUDE.md** marked deferred - if marketing/docs claim them but code lacks them, that's the highest-leverage finding class. The methodology's §8c sweep catches some of these; the extension elevates the most procurement-critical to top-of-mind.
4. **Recent migration scars** (last 6 months of CLAUDE.md / git log). Recently moved code is over-represented in security findings.
5. **Operational risk dressed as compromise risk** - admin-error wipe, missing BCP, misconfigured rotation. These don't fit the threat model's "external attacker" framing but they cause real outages.

Each extension must name: subsystems involved; exploit shape (preconditions -> action -> blast); methodology integration (which §N it slots into and why); concrete code paths to check; a test name that would fail without the fix.

Aim for 3-7 extensions. More than 7 means the methodology is missing something - propose a methodology update instead. Fewer than 3 means you didn't read CLAUDE.md carefully enough.

## Procedure

1. Run the discovery sweep. Produce a key=value summary.
2. Walk CLAUDE.md / specs to draft 3-7 reasoning extensions.
3. Show the user the discovery summary + extensions. Ask whether to write the skill or refine first.
4. On confirmation, write `skills/security-audit-<repo>.md` in the project repo using the template below.
5. If the project has a SOC 2 / compliance script suite (`scripts/audit-*.sh` or similar), generate or update a companion `soc2-audit-<project>.md` skill that wraps the runner. Methodology §8 will dispatch to it.
6. After write, register the new skill wherever the project indexes its skills so the auditor can find it.

## Output template

```markdown
---
name: security-audit-<repo>
description: Full-codebase security audit for <project>. Project-specific layer over the Security-Suite methodology. Adds <repo> parameters and N reasoning extensions for <list of extension topics>. Invoke for quarterly audits, before procurement, or after major auth/agent/data-flow changes.
type: project
tags: [claude, skills, security, audit, <repo>]
project: <project>
scope: project
status: live
created: '<YYYY-MM-DD>'
updated: '<YYYY-MM-DD>'
generator_version: rev4
parent: Security-Suite
imports:
  - 'Skills/Development/Security-Suite/methodology.md'
  - 'Skills/Development/Security-Suite/tools.md'
---

# Security Audit (<project>)

Project-specific layer. The methodology lives at `Skills/Development/Security-Suite/methodology.md` - read it first, then apply the substitutions and reasoning extensions below.

## Invocation runbook

1. Read `methodology.md`. State the threat model (in-scope / out-of-scope).
2. Apply per-section substitutions from the table below.
3. Apply reasoning extensions between methodology pass and §11 ranking.
4. Dispatch underlying tools per the table.
5. Output per the methodology's deliverable format. §13 self-verification mandatory. Cap 3000 lines.

## Threat model

**In scope:** [...customise per project, anchored on the actual abuse profiles...]

**Out of scope:** [...explicit, with one-line reason each...]

Out-of-scope-precondition findings = INFO not HIGH.

## Project context

| Field | Value |
|---|---|
| repo_root | `<absolute path>` |
| package_manager | `<value>` |
| ... | ... |
| has_file_uploads | `<true/false>` |

## Per-section substitutions

| Methodology section | <project> specifics |
|---|---|
| §1 secret discovery | <encryption module path + any project-specific gotchas> |
| §1 secret classes | <add project-specific classes beyond the methodology defaults> |
| §2 chokepoint chain | <name the actual chain: A() -> B() -> C(); name the underlying primitive> |
| §3 helpers to sweep | <list the requireXxx / hasYyyAccess helpers> |
| §4 autonomy map | <where it lives, what levels exist> |
| §5 scanner | <name the function, name the bypass-test target> |
| §6 protocol enums | <list the enums to trace> |
| §7 file validation | <where the magic-byte check lives> |
| §8 SOC 2 runner | <command to invoke> |
| §8a backup | <state the BCP situation honestly> |
| §9/§10 URLs | <public_docs_url, marketing_urls> |

## Reasoning extensions

### Extension 1: <name>
**Subsystems:** ...
**Exploit shape:** preconditions -> action -> blast
**Methodology integration:** §N - reason
**What to check:** specific files / chokepoints
**Test name:** <test that would fail without the fix>

### Extension 2: <name>
...

## Convergence rationale

Methodology rev history (lives in `methodology.md`):
- rev 1 -> rev 2: deps + claim-vs-code + self-verification.
- rev 2 -> rev 3: threat model + structural-fix mandate + dynamic Top-N + §13 quota.
- rev 3 -> rev 4: secret-discovery sweep at §1.

When a future audit catches a class of failure not covered, **update `methodology.md` first**, then re-run `generator.md` to refresh this file.
```

## Worked example: extension authoring (generic)

For reference - a generated `security-audit-<repo>.md` is authored by reading CLAUDE.md and surfacing 5 exploit shapes the generic methodology missed. These archetypes recur across projects:

1. **Consent-gated cross-tenant reads** - a feature lets one tenant read another's data through an explicit consent relationship. Generic §3 sweep would miss this because it's not a tenant-isolation bug, it's a tenant-isolation feature with a fragile chokepoint. The extension forces explicit verification of that chokepoint.

2. **Bidirectional auth** - the "bidirectional auth" pattern (an outbound bearer secret also authenticates inbound calls) is rare enough that it's not in the methodology. When CLAUDE.md spells out such a pattern, the extension makes it a §2 chokepoint sweep target.

3. **Form -> record -> agent second-order injection** - methodology §5 covers prompt injection generically. The extension names the *specific chain* in the codebase (a submission-write handler -> stored submission data -> context-gathering helper -> agent context). Without naming the chain, an auditor would test the scanner regex but not the end-to-end propagation.

4. **Operational backup risk** - methodology §8a says "no backup outside primary DB = HIGH". The extension shifts framing: the threat model assumes the DB provider is honest, but admin-error is in scope and produces the same blast radius. The extension forces the honest framing.

5. **Cloud-dispatch subsystem** - a new subsystem introduces a bearer-secured cloud fire-and-forget call. It adds a secret class to §1, a chokepoint to §2, and an injection surface to §5 simultaneously. The extension consolidates the cross-section concern.

The pattern: each extension is a *named exploit shape* with a clear methodology integration point. They're not "things to also check" - they're "this is how to interpret the methodology for this codebase."

## Language adaptations

The discovery commands above are Node/TS-defaulted. For other stacks:

| Concern | Python | Rust | Go | Ruby |
|---|---|---|---|---|
| Schema | `alembic/versions/`, `models.py`, SQLAlchemy decls | `migrations/`, sea-orm derives | `migrations/`, `gorm:"..."` tags | `db/schema.rb`, ActiveRecord decls |
| Env file | `.env`, `config.example.yml` | `.env`, `config.toml` | `.env` | `.env`, `config/secrets.yml` |
| Encryption module | `app/lib/crypto.py` | `crates/<name>/src/crypto.rs` | `internal/crypto/` | `app/lib/crypto.rb` |
| Secret env reads | `os.environ.get` / `os.getenv` | `std::env::var` | `os.Getenv` | `ENV[]` |
| Agent SDK | `anthropic`, `openai` | `anthropic-sdk` | `anthropic-sdk-go` | `ruby-anthropic` |
| Web framework markers | FastAPI / Django routers | Axum / Actix routes | net/http / chi | Rails routes.rb |

If the project uses a stack not listed, the discovery commands' *intent* still applies; substitute the equivalent file/grep patterns and document the substitution in the generated skill (so the next regeneration knows what was assumed).

## Maintenance

- When CLAUDE.md grows a new subsystem (auth provider, signing scheme, oversight relationship), re-run the generator and diff the output. New reasoning extensions go in; obsolete ones come out.
- The methodology itself is stable - changes there are rev N+1 events, not per-project. If you find yourself wanting to edit `methodology.md` for one project, that's a sign the neutral 70% needs an addition.
- When a finding from a project audit reveals a class of failure not covered by the methodology, propose a methodology update *before* patching the project skill. The point of the suite is convergence.

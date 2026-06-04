---
name: security-suite-workflow
type: workflow
domain: security
summary: Standalone and refactoring-subworkflow execution model for Security-Suite.
---

# Security-Suite Workflow

Security-Suite runs in two modes:

- **Standalone mode:** a user or agent invokes Security-Suite directly for an audit, release gate, incident/posture update, or targeted review.
- **Refactoring subworkflow mode:** the refactoring suite classifies security surfaces and calls Security-Suite with a bounded dispatch payload.

Both modes use the same stages and output contract.

## Stage 0: Intake

Capture:

- `scope`: repo, diff, files, route surface, service, plugin, vendor integration, or documentation/evidence set.
- `change_intent`: audit, refactor, feature, fix, incident, release gate, procurement, support escalation.
- `mode`: `standalone` or `refactoring-subworkflow`.
- `constraints`: production, no network, no destructive commands, compliance deadlines, customer-facing claim review.
- `security_surfaces`: if unknown, leave empty and derive during fingerprinting.

## Stage 1: Fingerprint

Inspect the target for:

- Frameworks: NextAuth/Auth.js, Supabase, Stripe, Prisma/ORM, plugin/MCP, browser app, worker/job system.
- Product flags: multi-tenant, agents/tool calling, SSO/SCIM, BYOK, file uploads, payments, public portals, compliance evidence, customer support or procurement workflows.
- Native commands: security scripts, test scripts, audit scripts, scanner configs.

Output `repo_fingerprint` and detected adapters.

## Stage 2: Dispatch

Use `50_references/dispatch-matrix.md` to select:

- Core skills from `10_skills/`.
- Reviewer agents from `20_agents/`.
- Adapters from `30_adapters/`.
- Playbooks from `40_playbooks/`.

Do not dispatch every skill by default. Dispatch by detected surface and record explicit skips.

## Stage 3: Evidence

For each dispatched skill:

- Read the smallest sufficient code, config, docs, policy, or artifact surface.
- Run non-destructive checks where available.
- Classify each claim as `Confirmed`, `Likely`, `Hypothesis`, or `False-positive-risk`.
- Use `50_references/finding-schema.md` for every substantive finding.

Static scanners, compliance scripts, and grep checks are evidence inputs, not behavioral proof.

## Stage 4: Synthesis

Deduplicate findings by root cause and affected boundary. Rank by exploitability and blast radius, not ease of fix. Split fix ordering from risk ordering.

Every finding must include:

- Evidence.
- Exploit scenario.
- Suggested fix.
- Required verification.
- Residual risk.

## Stage 5: Verification

Use `50_references/nonregression-checklist.md` plus each skill's required verification. For refactoring-subworkflow mode, return verification requirements to the refactoring suite so it can carry them into stage 60.

## Stage 6: Close

Standalone mode closes with a security report. Refactoring-subworkflow mode closes by returning:

- `findings`
- `required_verification`
- `adapter_notes`
- `residual_risk`
- `skips`

No completion claim is valid unless required verification is fresh or explicitly blocked with residual risk.

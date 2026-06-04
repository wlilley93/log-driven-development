---
tags:
  - claude
  - skills
  - global
  - security
  - tools
created: '2026-04-30'
updated: '2026-04-30'
scope: global
status: live
parent: Security-Suite
---
# Security Tools Catalogue

Underlying tools the methodology dispatches to. Use this as a reference when running an audit.

## Selection guide (read this first)

| Situation | First tool | Then |
|---|---|---|
| Ad-hoc PR review | `/security-review` | (stop) |
| New project adopting the suite | `generator.md` | (produces the project-specific skill) |
| Quarterly full audit | project-specific `security-audit-<repo>.md` (which imports `methodology.md`) | dispatches to vibescan + vibeaudit + soc2-audit-* per section |
| Procurement security questionnaire | `methodology.md` §10 (claim vs code) | full audit if claims diverge |
| "Find auth bugs in this PR" | vibeaudit `--deep` against the changed routes | adjudicate with `/security-review` reasoning |
| "Is my dev machine compromised?" | vibecyber | (separate from codebase work) |
| Release-candidate exploit-validation gate ("prove the Highs are real / find exploitable ones") | shannon (on a throwaway target) | triage with `10_skills/exploit-validation-review.md` |

## /security-review (built-in)

**Source:** Anthropic plugin, loaded automatically.
**Best for:** PR-scoped review of pending changes on the current branch.
**Methodology dispatch:** none. `/security-review` is the lightweight per-PR version; the methodology is the heavyweight version. Run `/security-review` on every PR, run the methodology quarterly or before procurement.

## vibescan

**Source:** `tools/vibe/vibescan/` (vendored).
**What it does:** Orchestrates 13 OSS tools (gitleaks, trufflehog, detect-secrets, semgrep, bandit, codeql, trivy, grype, npm-audit, pip-audit, snyk, kics, licence scanner) in parallel. Deduplicates findings. Single pass/fail verdict for CI gating.
**Methodology dispatch:** §0 (dependency posture). Run before reasoning starts; use its CVE list as input rather than re-running each scanner.
**Invocation:** `vibescan {repo_root}` or `vibescan install --check` to verify tool availability.
**Notes:** Mechanical sweep. The methodology's §0 still does the "is this exploitable in our deployment?" downgrade reasoning that vibescan can't do.

## vibeaudit

**Source:** `tools/vibe/vibeaudit/` (vendored).
**What it does:** AI-powered business-logic vulnerability scanner. Two modes:
- **Extraction** (default) - static parse of code regions, structured JSON output.
- **Agentic deep scan** (`--deep`) - LLM autonomously explores the codebase, reads files, traces middleware chains. Slow, deep.

**Vulnerability classes:** auth bypass, authorization failures, race conditions, mass assignment, data exposure, IDOR, privilege escalation, session management.

**Methodology dispatch:**
- §1.j console-log sweep over auth/encryption modules - vibeaudit `--deep` supplements.
- §2 / §6 chokepoint-bypass and privilege-escalation sweeps - run extraction mode against route handlers, escalate to `--deep` for paths flagged uncertain.
- §3 tenant-isolation grep - supplemented by vibeaudit's IDOR detector.

**Invocation:** `vibeaudit scan {target}` or `vibeaudit scan {target} --deep --provider anthropic`.
**Notes:** Findings need methodology-style adjudication. Vibeaudit produces findings; the methodology determines exploitability and severity.

## shannon (autonomous white-box AI pentester  -  exploit-proof)

**Source:** `KeygraphHQ/shannon` (AGPL-3.0, `npx @keygraph/shannon`). **Doc:** `60_tools/shannon-ai-pentester.md`.
**What it does:** reads source white-box, maps attack surface, then **executes real exploits** against a running target to prove vulnerabilities ("No Exploit, No Report"). Runs as a Temporal workflow in Docker; four phases (pre-recon → recon → exploitation → reporting).
**Methodology dispatch:** the exploit-validation gate  -  run after the static methodology, on a **throwaway/sandbox** target only (it's mutative), with written authorization. Any Anthropic-compatible model works (custom base URL); use a non-expiring API key, not a Claude OAuth token (it expires mid-run).
**Invocation + provider/auth specifics:** see `60_tools/shannon-ai-pentester.md`.
**Notes:** AGPL → referenced tool, never vendored. Its findings still need adjudication  -  triage every one (false-positive / by-design / reachability) per `10_skills/exploit-validation-review.md`; only proven-live or clearly-reasoned findings drive remediation.

## soc2-audit-<project> (project-specific example)

**Source:** a project's own `scripts/audit-soc2-compliance.sh` and its sibling scripts.
**What it does:** ripgrep-driven static checks validating ISO 27001 / SOC 2 controls for the project. A master runner aggregates output. Targets: API business logic, application runtime, authn/authz, CI/CD, data handling, encryption, etc.
**Methodology dispatch:** §8 (SOC 2 gaps). Dispatch when the project has a dedicated SOC 2 suite.
**Invocation:** `bash scripts/audit-soc2-compliance.sh` from the repo root.
**Notes:** Template for *project-specific* SOC 2 skills. The generator (`generator.md`) produces analogous skills for other projects when their SOC 2 evidence lives in scripts.

## vibecyber

**Source:** `tools/vibe/vibecyber/` (vendored).
**What it does:** 122-check macOS endpoint scanner. Rootkits, rogue LLMs, supply-chain compromises, persistence mechanisms, prompt injection, Claude Code hooks integrity.
**Methodology dispatch:** none. Out of scope for codebase audits. Listed for completeness - if an audit produces findings under "operator machine integrity", vibecyber is the right follow-up.
**Invocation:** `vibecyber scan` (full scan, ~70s).

## Tool gaps

The suite has no:
- **Runtime fuzzer** - fuzz is a deploy-time concern, run separately.
- **Network scanner** - infrastructure team owns this.
- **DAST** - methodology is SAST + reasoning.
- **Compliance evidence aggregator** - SOC 2 audits dispatch to project-specific scripts; evidence shapes vary too much per audit.

These gaps are deliberate. Don't add tools to fill them without a concrete audit failure showing the gap matters.

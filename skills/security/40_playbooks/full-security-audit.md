---
name: full-security-audit
type: playbook
domain: security
summary: Full codebase security audit workflow.
---

# Full Security Audit

Use this playbook when Security-Suite runs alone for a full or broad audit.

1. Run `../WORKFLOW.md` in standalone mode.
2. Use `../50_references/threat-model-template.md` to state in-scope and out-of-scope attackers and trust boundaries.
3. Fingerprint the repo and select adapters with `../50_references/dispatch-matrix.md`.
4. Use `../methodology.md` as the full-audit spine.
5. Run scanner/tooling guidance from `../tools.md` and `../60_tools/scanner-orchestration.md`.
6. Dispatch all core skills that match the fingerprinted surfaces.
7. Apply project/framework adapters only when their fingerprint matches.
8. Synthesize findings with `../50_references/finding-schema.md` and `../50_references/severity-rubric.md`.
9. Run or prescribe verification from `../50_references/nonregression-checklist.md` plus each finding's required tests.
10. Close with an executive summary, findings, fix plan, required verification, skipped sections, and residual risk.

Do not use a full audit when a refactoring subworkflow only needs a bounded preflight review.

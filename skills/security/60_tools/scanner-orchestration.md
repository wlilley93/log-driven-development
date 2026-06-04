# Scanner Orchestration

Prefer project-native commands first. When available, use:

- secret scanning: gitleaks, trufflehog, detect-secrets.
- SAST: semgrep or project security lint rules.
- dependency scanning: npm audit, pnpm audit, yarn audit, snyk, grype.
- container/filesystem scanning: trivy.
- IaC scanning: kics or equivalent.
- application-specific scripts: SOC2/security audit scripts checked into the repo.

Scanner findings are input, not final truth. Triage with code evidence and required behavioral tests where scanners cannot prove runtime behavior.

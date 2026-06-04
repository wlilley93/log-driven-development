---
name: security-baseline-review
type: skill
domain: security
summary: Review code for baseline application security controls.
outputs: [security-findings.json]
---

# Security Baseline Review

## Use When

Use for any security-sensitive code change or as the default lane for broad security review.

## Required Checks

- Authentication and authorization are enforced server-side.
- Browser mutations have CSRF protection or an explicit non-browser threat model.
- External inputs are parsed with runtime validation before use.
- Errors do not leak stack traces, secrets, SQL, tokens, or internal implementation details.
- Logs and audit events redact sensitive values.
- CORS and redirect behavior are constrained to expected origins.
- Raw SQL, shell execution, file paths, and URLs are parameterized or constrained.
- Security-sensitive mutations are auditable.

## Output

Write findings using `../50_references/finding-schema.md`. Include exact verification required before close.

## Added checks  -  control-attestation drift + service-account privilege separation
- **Control-attestation drift.** Do the **shipped** runtime flags actually match
  the hardening docs + any verifier script? Inspect the real artifact (e.g.
  `docker inspect` HostConfig, the deployed sudoers) and flag any control the
  docs/verifier *assert* that the provisioning code does **not** apply (a verifier
  that lies is worse than none).
- **Service-account privilege separation.** The account running the
  internet-facing service must not also hold host-root-equivalent (`NOPASSWD:ALL`
  sudo, docker-group membership). If a daemon RCE = instant host root, that's a
  finding  -  enumerate scoped grants + a dedicated low-priv service account.
- **Container privilege.** Containers running untrusted workloads: non-root +
  `--cap-drop ALL` + `--no-new-privileges` + read-only rootfs + userns-remap, or
  an explicit, documented reason they can't (and the doc must not claim otherwise).
- **Emergency containment / kill switch.** Is there a fast, authenticated control
  to (a) kill/quarantine one workload, (b) suspend a tenant, and (c) fleet-wide
  cut egress / pause all + revoke the control-plane secret + rotate the signing
  key? Untrusted-agent platforms especially need this; verify it exists, is
  scoped, audited, and **tested**.

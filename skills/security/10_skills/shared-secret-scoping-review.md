# Skill: shared-secret / shared-channel scoping review

**Surface:** multi-principal systems (multi-tenant SaaS, agent platforms, shared
hosts) where multiple principals share a network, host, or env.

**Root-cause pattern this catches:** *possession, not registration, is the real
boundary.* Authority is gated by **holding a shared secret / shared bind / shared
channel** that co-resident principals also have  -  so per-principal scoping
(roles, ACLs, "this tool is only registered for X") is cosmetic. Whoever can read
the shared thing wins, regardless of the intended scope.

## Why it's high-value
It is a single root cause behind many distinct-looking findings. Reviewers tend
to verify the *intended* scoping (the ACL, the role check, the MCP-tool gating)
and miss that the underlying credential/endpoint is shared.

## Checks
1. **Shared env files.** Is a privileged secret written to an env file that
   *every* worker/process sources (e.g. a group-readable `global.env`)? Then the
   secret's scope = everyone who sources it, not the one principal meant to hold
   it. → Confine to a 0600 file the single principal reads, or inject per-principal.
2. **Shared bearer + broad bind.** A service bound to `0.0.0.0` (all interfaces
   in a shared network namespace) behind a *tenant/cluster-shared* bearer: any
   co-resident workload can reach it with the shared bearer. → Bind loopback if a
   local proxy is the only consumer, or issue per-principal keys.
3. **Shared cookie / parent-domain scope.** A session cookie scoped to a parent
   domain (`Domain=.example.com`) across tenant subdomains: any subdomain (incl. a
   rogue/compromised tenant) receives it → cross-tenant session harvest. → Scope
   per-tenant, or use a redirect-with-token handoff instead of a cross-domain cookie.
4. **Identity inferred from a shared attribute.** Is "who you are" derived from
   something forgeable/shared (a string-prefix role name, a bind address, an IP)
   rather than a non-spoofable per-principal credential? (See also
   `authz-tenant-isolation-review`.)
5. **Shared signing key for revocable assertions.** One key signs tokens for all
   principals with no per-principal kid/rotation → can't revoke one without all.

## Verification
For each shared secret/endpoint/cookie: enumerate *every* principal that can
read/reach it, and confirm that set equals the intended scope. If it's larger,
the scoping is cosmetic  -  finding.

## Finding shape
Use the standard finding schema; `surface: authz-tenant` or `secrets-crypto`;
exploit scenario must name the *co-resident principal* that gains the authority.

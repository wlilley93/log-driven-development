---
name: auth-session-review
type: skill
domain: security
summary: Review authentication, session, logout, MFA/2FA, cookies, and browser auth behavior.
outputs: [auth-session-findings.json]
---

# Auth Session Review

## Use When

Use when work touches login, logout, session refresh, JWT/cookie fields, MFA/2FA, account linking, route protection, or auth UI flows.

## Required Checks

- Invalid credentials and invalid MFA/2FA codes fail closed with behavioral tests.
- Success and failure paths assert exact library return semantics instead of truthiness of objects.
- Session state cannot be promoted permanently from one successful MFA/2FA verification unless explicitly intended.
- Cookies carrying auth state are signed, httpOnly, secure in production, sameSite constrained, scoped, and bounded by expiry.
- Logout, disable-MFA, account reset, and role/tenant changes revoke or invalidate relevant security state.
- Protected pages and APIs reject unauthenticated and partially-authenticated sessions.
- Browser tests cover protected-route redirect, login, refresh persistence, logout clearing, and stale content after logout.

## Output

Return findings and `required_verification`, including unit tests for auth helpers and browser/session tests when UI or cookie behavior changes.

## Added checks  -  session revocation lifecycle + multi-tenant cookie scope
- **Revocation tied to credential/account state.** Does changing a password or
  removing/disabling an account **revoke active sessions AND stop token minting**
  (e.g. SSO JWTs)? Is there a per-principal session-purge primitive? A 30-day
  opaque token that self-renews short JWTs and survives a password change/removal
  is a finding.
- **Logout/restart semantics.** Does logout revoke the token **server-side** (not
  just clear the cookie)? Does a session survive a server restart only via an
  intended durable store (not accidental in-memory persistence)?
- **Cookie attributes by default.** Secure + HttpOnly + SameSite present by
  default (opt-out, not opt-in)?
- **Multi-tenant cookie scope.** A session cookie scoped to a **parent domain**
  across tenant subdomains is sent to *every* subdomain → cross-tenant harvest by
  a rogue/compromised tenant. Prefer per-tenant scope or a redirect-with-token
  handoff. (See `shared-secret-scoping-review`.)

## Added checks  -  distributed-attack resistance + MFA
- **Per-IP limiting is bypassable.** An attacker rotating IPs (botnet/proxies)
  stays under any per-IP threshold. Defend by keying on the **target**: a
  per-account failure counter (across all IPs) + a fleet-wide aggregate ceiling,
  and on a spike **require a human challenge** (e.g. Cloudflare Turnstile) rather
  than a hard lock (a hard per-account lock is a victim-DoS). The edge sees the
  whole botnet  -  push rate-limit rules + bot management + challenge there too.
  Emit anomaly events (`*_under_attack`) for alerting.
- **Second factor.** Is MFA available (TOTP/WebAuthn), and is it *opt-in without
  breaking existing accounts* (a non-enrolled user logs in unchanged)? Does the
  factor gate AFTER the password verifies? MFA is the durable answer to
  credential-stuffing; rate-limiting is only a speed bump.
- **Breached-password rejection** at set-time (HIBP k-anonymity range API  -  only
  the SHA-1 prefix leaves the box; fail-open on outage).

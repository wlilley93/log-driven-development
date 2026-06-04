# Skill: DNS / domain security review

**Surface:** any product whose trust anchors to a domain (SSO portals, multi-
tenant subdomains, edge/CDN/tunnel ingress, OAuth redirect URIs).

**Why:** domain/DNS control sits *below* the app  -  an attacker who gets it can
serve a pixel-perfect fake at the real origin (and a valid DV cert), defeating
every app-layer control. Most app security reviews skip this layer entirely.

## Checks
1. **Registrar + DNS account hardening.** 2FA on the registrar and the DNS/CDN
   account; **registrar transfer-lock** enabled; least-privilege, **rotated** API
   tokens (a leaked DNS/CDN token = zone control = full hijack). Flag any DNS/CDN
   API token that has been exposed (committed, pasted, broadly scoped).
2. **DNSSEC** enabled on the zone (signed records → spoofed DNS rejected by
   validating resolvers).
3. **CAA records** restricting which CAs may issue, + **Certificate Transparency**
   monitoring for unexpected certs.
4. **Dangling-subdomain / takeover.** Every dynamically-created subdomain (per
   tenant, per env) must be **de-registered on teardown**  -  no DNS record or
   ingress rule left pointing at a claimable/again-provisionable target. Verify
   the deprovision path removes DNS + ingress, not just the app.
5. **Origin exposure.** Is there a public origin IP an attacker can flood/scan
   directly, or is ingress outbound-only (tunnel) + host-firewalled? No-public-origin
   (e.g. a cloudflared tunnel + default-deny) removes direct-to-origin attacks.
6. **HSTS (incl. preload) + redirect hygiene** so a hijack can't trivially
   downgrade to HTTP; validate OAuth/redirect allowlists can't be widened via a
   new attacker-controlled subdomain.
7. **Cross-subdomain blast radius.** Cookies/CORS/`postMessage` scoped to a parent
   domain across tenant subdomains amplify a single subdomain takeover into
   cross-tenant compromise (see `shared-secret-scoping-review`).

## Verification
Enumerate every name in the zone + every dynamically-created subdomain; confirm
each maps to an intended, operator-controlled target and is torn down on
deprovision. Confirm DNSSEC + CAA present; confirm no exposed/over-scoped tokens.

## Note
Most remediations here are **operator/account actions, not code**  -  the review
should produce an explicit operator checklist, and code findings only where the
*app* fails to clean up its own DNS (dangling subdomains) or over-scopes cookies.

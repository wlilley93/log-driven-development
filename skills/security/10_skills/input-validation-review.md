---
name: input-validation-review
type: skill
domain: security
summary: Ensure external inputs are validated, bounded, and parsed safely at runtime.
outputs: [input-validation-report.md]
---

# Input Validation Review

## Use When

Use for route handlers, server actions, uploads, webhooks, portal/public endpoints, JSON parsing, query params, forms, CSV/document parsing, and third-party callbacks.

## Required Checks

- Inputs cross a runtime schema or structured parser before use.
- Body size, file size, item count, and nesting depth are bounded.
- URL, path, redirect, and origin values are allowlisted or normalized safely.
- User input is never passed directly to SQL, shell, filesystem, template rendering, LLM tools, or outbound HTTP without constraints.
- Validation errors are safe, actionable, and do not expose internals.

## Output

Record missing validation, unsafe parser use, and exact tests required for malformed, oversized, and adversarial inputs.

## Added check  -  output encoding / XSS sinks + CSP
- **HTML sinks.** Every `dangerouslySetInnerHTML` / `v-html` / `innerHTML` /
  server-rendered-HTML-from-user-or-agent-content sink must be **sanitised**
  (DOMPurify or equivalent)  -  especially **agent output / recalled memory / chat
  markdown**, which is attacker-influenceable (stored/indirect XSS). React/Vue
  auto-escaping covers the default path; the sinks are the gap.
- **CSP.** Is a `Content-Security-Policy` set as defense-in-depth? For a built SPA
  with only external scripts, `script-src 'self'` is safe and blocks injected
  inline JS; `object-src 'none'`, `base-uri 'self'`, `frame-ancestors 'none'`.
  Confirm the cookie is `HttpOnly` so an XSS can't read the session.

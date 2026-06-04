# Severity Rubric

- Critical: authentication bypass, MFA bypass, cross-tenant data exposure, secret key exposure, arbitrary code execution, payment mutation without authorization, service-role exposure, or production destructive action without guardrails.
- High: broken authorization on sensitive objects, exploitable CSRF on sensitive mutations, unsafe webhook verification, privilege escalation, broad data exfiltration, or insecure crypto/token handling.
- Medium: missing validation with bounded impact, weak logging/redaction, incomplete audit evidence, dependency risk with limited exploitability, or security control drift.
- Low: hardening gaps, unclear docs, observability gaps, non-sensitive policy drift, or low-impact misconfiguration.
- Info: out-of-scope precondition, documentation note, or defense-in-depth improvement.

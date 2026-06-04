# Threat Model Template

## In Scope

- External attackers.
- Authenticated users at lower privilege.
- Cross-tenant customers or workspace members.
- Public endpoint users and webhook senders.
- Malicious uploaded content, documents, tool outputs, prompts, and third-party callbacks.
- Insider/operator mistakes when the system has no guardrail.

## Out of Scope

- Cloud provider control-plane compromise unless the project owns a mitigation.
- Physical device compromise unless the project stores secrets locally.
- Identity provider compromise unless the project controls the identity boundary.

## Required Notes

Record trust boundaries, sensitive data classes, privileged operations, public endpoints, and any project-specific adapter assumptions.

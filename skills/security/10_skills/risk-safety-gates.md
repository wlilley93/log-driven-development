---
name: risk-safety-gates
type: skill
domain: security
summary: Gate destructive, production, legal, financial, privacy, or security-impacting actions.
outputs: [risk-gate.md]
---

# Risk Safety Gates

## Gate Triggers

Require explicit risk handling before:

- Deleting data or files.
- Running production migrations.
- Changing permissions, roles, secrets, encryption, signing, session, MFA/2FA, or tenant isolation.
- Spending money or creating paid resources.
- Sending external messages or customer-facing security claims.
- Making legal, financial, privacy, medical, or compliance determinations as final advice.
- Force-pushing, rewriting shared history, or running destructive scripts.

## Risk Note Format

```markdown
# Risk Gate

Action:
Why needed:
Potential impact:
Rollback:
Safer alternative:
Approval required from:
```

## Exit Condition

Risk is mitigated by a safer path, accepted with explicit approval, or deferred with owner and residual risk.

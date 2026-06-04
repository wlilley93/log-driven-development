---
description: Convene an adversarial deliberation council on a high-stakes decision (or escalate to the Appeals / Supreme Council)
argument-hint: <the decision or question to deliberate> [| appeal | supreme]
---

Convene **the council** (see the `council` skill) on this question:

**$ARGUMENTS**

Run it as a single parallel fan-out:
1. **Pick 3-5 distinct-lens seats** (not redundant) appropriate to the question - e.g. project-health,
   process/method critic, devil's-advocate/pre-mortem, plus a domain lens (security · cost · UX · the advocate
   of a named alternative). For an architecture fork, include a seat that ruthlessly separates shipped-vs-assumed
   and a seat that steelmans the principal's own instinct before others stress-test it.
2. **Each seat MUST ground-truth first** (greps, file reads, counts, test runs) and **lead with the blunt truth**,
   not a hedge. Seats run independently (do not see each other mid-run).
3. **Synthesise** into one ratifiable recommendation that **ends in a build action or a kill** - never a deferral.
   Preserve the strongest surviving dissent (it is the standing of any future appeal). Record the verdict in the
   ledger and act on it the same beat.

**If the argument contains `appeal` or `supreme`:** run the corresponding higher court instead - hand every seat
the **full record of the court(s) below**, and scope the remit: *Appeals* re-weighs the merits (points of spec)
engaging the lower reasoning and may uphold or overturn; *Supreme* reviews **only how the invariants + method
were applied** (points of law, not the merits) and its ruling becomes **spec law** (append it to the spec-law
register as an immutable precedent). Escalation needs *standing* - a real basis, not mere disagreement.

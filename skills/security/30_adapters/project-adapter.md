# project-adapter (the per-project adapter slot)

This is the generic slot for **your project's own security adapter**: the codebase-specific exploit shapes,
trust boundaries, and conventions that the generic review skills (`../10_skills/`) cannot know in advance. You
author it once per project (the `../generator.md` worked example shows how), and the dispatch matrix routes
project-specific surfaces here.

Keep it small and concrete. Capture only what is true of THIS codebase and would otherwise be missed:

- **The trust boundaries that matter here.** Where this system enforces authz, tenant/workspace scoping,
  and the externally-reachable entry points (the verbs/routes/handlers that an attacker can reach).
- **The project's own exploit shapes.** The 3 to 6 attack patterns specific to this architecture that a
  generic review would miss (for example: a privilege-escalation path unique to how this codebase mints
  capabilities, or a tenant-isolation bypass unique to its data model).
- **SOC 2 / compliance specifics, if any.** If the project carries SOC 2 / ISO obligations, record the
  control-to-code-evidence mapping here (or in a sibling `project-soc2-adapter.md`); otherwise omit it.
- **The conventions a reviewer must know.** The logging/audit call shape, the encryption helper, the
  error-handling pattern, so a finding cites the right mechanism.

A fresh project starts with this template empty and fills it from the first security pass. The generic review
skills do the heavy lifting; this adapter is the thin, project-true layer on top.

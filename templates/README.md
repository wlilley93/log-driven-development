# LDD templates

Copy-paste skeletons for the artefacts Log-Driven Development produces. Each file is a clean page-or-less
form with inline guidance in comments and `<placeholders>`. To use one, copy it into your project, rename it
for the area or sequence, delete the leading `<!-- ... -->` guidance comment, and fill every section with
real, grounded content (provenance or it does not go in). The filled examples all reference one running
scenario, "Tasky" (a vibe-coded task tracker being rebuilt with LDD), so the artefacts cross-reference and
read as one project. For the method these serve, read `skills/log-driven-development/SKILL.md` and
`skills/council/SKILL.md`; for a fully worked set, see the example directory.

## The templates

- `intent-ledger.md` : the harvest artefact, one per area: the precious rules (with file:line provenance),
  the data shapes, and what to drop and why.
- `metacognition-entry.md` : one journal beat: what / why (chosen, alternatives, why) / outcome, with the
  one-writer and supersede-never-rewrite rules.
- `adr.md` : an Architecture Decision Record, for when a journal decision graduates to load-bearing:
  status, context, decision, consequences (plus and minus).
- `spec-skeleton.md` : the distilled minimal spec: primitives, numbered testable invariants, deliberately
  dropped behaviour, and the closure-sweep definition of done.
- `milestone-signoff.md` : the 5-phase close record (BUILD, STRUCTURE, SECURITY, VERIFY, PLAN) with a
  verdict, reproduced evidence, deferred items, and the mandatory next-steps plan.
- `council-verdict.md` : the deliberation record: the seats and their distinct lenses, each grounded in
  evidence, the synthesis (ends in a build action or a kill), the surviving dissent, and the appeal path.

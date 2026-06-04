# Agnostic-findings propagation: coherence verification report

Verifier pass over the three agnostic findings + two practical harvest lessons across the six method
surfaces (invariants, anti-patterns, playbook, methodology, systems, SKILL) plus the intent-ledger template.
Date: 2026-06-04.

## Per-finding coverage

### Finding 1 - Two-leg closure (LDD-INV-5: internal coherence AND source -> spec coverage)
Carried in all six prose surfaces:
- `docs/invariants.md` (LDD-INV-5, the register entry, rewritten two-legged)
- `docs/anti-patterns.md` (#18 "The spec graded its own homework", + #2 note + smell line 493)
- `docs/playbook.md` (beat-loop step 5, section 4c the FREEZE both-legs gate, section 6 the three-level DoD, the quick-ref card)
- `docs/methodology.md` (Step 4 the two-leg subtlety, + the closing headline, now fixed)
- `docs/systems.md` (system 2 arc loop, system 6 closure-gate, system 9 decisions-of-record)
- `skills/log-driven-development/SKILL.md` (Rules-you-do-not-break + the arc loop)
- NOT in `templates/intent-ledger.md` - correct: two-leg closure is a project-FREEZE definition, not a per-ledger field.

### Finding 2 - Both-altitudes harvest (LDD-INV-18: SYSTEM and PROCESS)
Carried in all seven surfaces including the template:
- `docs/invariants.md` (LDD-INV-18, the register entry)
- `docs/anti-patterns.md` (#17 "System captured, process withheld", + smell line 492)
- `docs/playbook.md` (the harvest brief, HARVEST AT BOTH ALTITUDES block)
- `docs/methodology.md` (Step 1 "Harvest at two altitudes, not one")
- `docs/systems.md` (system 1 spine, system 2 harvest exit criterion)
- `skills/log-driven-development/SKILL.md` (the spine, ledger #1)
- `templates/intent-ledger.md` (the REQUIRED `## The process / procedure` section)

### Finding 3 - Distil adversary (LDD-INV-13: drop-list adversary + retained-claim fidelity + security-complete)
Carried in six prose surfaces:
- `docs/invariants.md` (LDD-INV-13, the register entry, two-permission rewrite)
- `docs/anti-patterns.md` (#19 "The write-only drop-list", + #12 note + smell line 494)
- `docs/playbook.md` (the distil-adversary brief, section "run BEFORE harvest done")
- `docs/methodology.md` (Step 2 "Distil is the one step that must carry its own adversary")
- `docs/systems.md` (system 2 distil exit criterion)
- `skills/log-driven-development/SKILL.md` (the arc, distil step)
- NOT in `templates/intent-ledger.md` as a named field - acceptable: the DROP-with-reason section is what the
  adversary re-opens; the adversary itself is a process step, not a fill-in field.

### Practical lessons (archived/backup copies; enumerate ALL copies)
Carried where the source-coverage re-walk and the harvest are defined:
- `docs/methodology.md` Step 1 ("Before you call a surface empty, look harder for the source")
- `docs/anti-patterns.md` #18 ("Two practical lessons for that re-walk")
- `docs/playbook.md` harvest brief (the SOURCES line: enumerate ALL copies, check archives before "empty/lost")

## Stale definitions fixed

1. `docs/methodology.md:457-458` - the doc's CLOSING headline stated `"done" means the sweep is clean` as the
   final word, single-leg, with no acknowledgement of the source-coverage leg. Rewritten to require BOTH legs
   and cite LDD-INV-5. (This was the one surviving stale single-leg done-definition at a load-bearing surface;
   the body of Step 4 was already two-legged.)
2. `skills/log-driven-development/SKILL.md:83` - cross-reference said the register runs `LDD-INV-1..17`; it
   now runs through 18. Corrected to `LDD-INV-1..18` so the reference resolves over the full register.

## Cross-reference repairs (bidirectional resolution)

The new anti-patterns #17/#18/#19 mapped FORWARD to LDD-INV-18/5/13 correctly, but the invariant register's
"Enforced at" lines did not point BACK at them (one-directional). Repaired so each invariant cites its new
anti-pattern, matching the register's existing convention (INV-5 cites #2, INV-13 cites #12, etc.):
- LDD-INV-5 "Enforced at" now cites anti-pattern #18 + smell 493.
- LDD-INV-13 "Enforced at" now cites the distil-adversary brief (playbook 315-345) + anti-pattern #19 + smell 494.
- LDD-INV-18 "Enforced at" now cites methodology/systems/playbook surfaces + anti-pattern #17 + smell 492
  (previously cited only SKILL, template, artifacts, and the INV-5 leg). All cited line ranges spot-verified.

## Contradiction / hygiene checks

- No stale single-leg "done = zero gaps / sweep is clean / tests pass" survives unqualified. Every remaining
  "tests pass" mention is a negated framing ("not / never / alone"). Arc one-liners and the SKILL frontmatter
  pitch retain "zero gaps" as shorthand; each is expanded two-legged in its own body, so no contradiction.
- Anti-pattern -> invariant maps all resolve: #17 -> INV-18, #18 -> INV-5, #19 -> INV-13.
- No em/en dashes in any touched file.

## Verdict

CLEAN. The three findings + two practical lessons are present in every surface that should carry them, in that
surface's register, with no inter-doc contradiction; the two stale references are fixed; the #17-19 mappings and
the invariant back-references resolve bidirectionally.

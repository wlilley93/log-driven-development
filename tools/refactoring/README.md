# Refactoring suite tools

Runnable helpers the refactoring suite expects to find in a project. They are parameterised for a generic
codebase: no project-specific paths, no embedded secrets. The suite degrades gracefully when a tool is absent
(the playbooks write a stub artefact and continue), so the suite is usable with or without these.

## `extract-api-surface.ts`

The export-extraction helper used by the round-close API-surface diff (`references/api-surface-diff.md`). Walks a
TypeScript source tree, parses it with `ts-morph`, and emits one tab-separated line per exported public symbol
with its first-line signature, sorted, on stdout. The diff machinery snapshots this at each round close and diffs
the current round against the prior one, so a behaviour-preserving fix cannot silently break a public signature,
remove an export, or narrow a type while tests stay green.

```bash
npm install --save-dev ts-morph
npx tsx tools/refactoring/extract-api-surface.ts > round-N-exports.txt

# Override the source glob / tsconfig for non-standard layouts:
GLOB="lib/**/*.{ts,tsx}" TSCONFIG="tsconfig.build.json" \
  npx tsx tools/refactoring/extract-api-surface.ts > round-N-exports.txt
```

The bootstrap (`bootstrap-refactor-overrides`) writes a copy of this script into a new project's `scripts/`
directory. For non-TypeScript stacks, write the equivalent against your language's parser or symbol-index tooling.
The only contract the shared diff depends on is "one line per exported public symbol, tab-separated as
`<path>\t<name>\t<kind>\t<first-line-signature>`, sorted, on stdout."

## `verify-refactoring-suite.sh`

Structural verifier for the suite itself. Confirms the canonical files exist and that the security-delegation seam
is wired (the suite routes security review to a separate security suite rather than duplicating security
methodology locally). Run it after editing the suite to catch a missing or renamed file before it breaks a round.

```bash
tools/refactoring/verify-refactoring-suite.sh                 # auto-resolves the suite root
tools/refactoring/verify-refactoring-suite.sh /path/to/skills/refactoring   # explicit root
```

Exit 0 = PASS; non-zero = FAIL with the missing path printed.

## The deterministic scanners (vibescan / vibeaudit / vibeclean)

The preflight wave (`references/preflight-wave.md`) dispatches three external scanners by name:

- **vibescan** - a CVE / secret / SAST aggregator that normalizes a panel of open-source scanners into one report.
- **vibeaudit** - an AST security extractor (static mode) plus an agentic deep-scan mode (`--deep`).
- **vibeclean** - a maintainability / atomization / duplication / slop scanner whose slop detector backs the
  structural floor's slop-ratio check.

Those scanners are coded tools in their own right and ship separately (see the plugin's `tools/` tree for their
runnable cleanroom implementations and configs). The refactoring suite only depends on their output contracts (a
normalized JSON findings report), and the wave writes a stub artefact and continues if a scanner is not installed,
so the refactoring suite runs with or without them.

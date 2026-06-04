# API-surface diff (cross-round verification)

Captures the public API surface of a codebase at round close, then diffs against the prior round on the next round
close. Catches accidentally-broken signatures that test-passing alone misses: a fix can keep tests green while
changing a route signature, removing an exported symbol, or altering a public type's shape.

Reused by `create-refactor-plan` Step 10 (NORMAL round close) and `structural-sweep` Step S4a (sweep round close).

## What gets captured

| Surface | What's captured | Why |
|---|---|---|
| **Routes** | One line per route file, plus exported HTTP method names | Detects deleted routes, renamed paths, removed methods |
| **Public exports** | One line per exported symbol with its full signature | Detects deleted exports, renamed symbols, signature changes (param/return types) |
| **Database schema** (when the project uses a schema engine) | One line per model + field with type | Detects removed columns, renamed fields, type changes (the schema-migration incident class) |
| **Workflow / step / tool registries** (project-specific) | Registry entries by name | Detects renamed/removed registered handlers |

## Capture command

```bash
ARC_OR_ROUND_DIR="<round-or-arc-snapshot-dir>"
mkdir -p "$ARC_OR_ROUND_DIR/api-surface-snapshots"

# Routes (adapt the find to your routing convention)
find <routes-dir> -name "<route-file-pattern>" 2>/dev/null | sort > "$ARC_OR_ROUND_DIR/api-surface-snapshots/round-N-routes.txt"

# Public exports - requires the project-provided extract-api-surface script
# (walks the source tree, parses it, emits one line per exported symbol with signature)
<!-- OVERRIDE: COMMANDS.EXTRACT_API_SURFACE -->npx tsx scripts/extract-api-surface.ts<!-- /OVERRIDE --> \
  > "$ARC_OR_ROUND_DIR/api-surface-snapshots/round-N-exports.txt" 2>/dev/null \
  || echo "[skip] extract-api-surface script not found - add it to enable surface diff"

# Schema (when applicable)
if [ -f <schema-file> ]; then
  cat <schema-file> > "$ARC_OR_ROUND_DIR/api-surface-snapshots/round-N-schema.txt"
fi
```

## Diff against the prior round

```bash
PRIOR_ROUND="$((N - 1))"
SNAP_DIR="$ARC_OR_ROUND_DIR/api-surface-snapshots"

for kind in routes exports schema; do
  if [ -f "$SNAP_DIR/round-$PRIOR_ROUND-$kind.txt" ]; then
    diff "$SNAP_DIR/round-$PRIOR_ROUND-$kind.txt" "$SNAP_DIR/round-N-$kind.txt" \
      > "$SNAP_DIR/round-N-arc-diff-$kind.md" 2>&1 || true
  fi
done
```

## Acceptance gate

If any diff shows:
- **Removed routes** - fail close until acknowledged in the changelog and confirmed intentional.
- **Removed exports** - same.
- **Signature changes** (param-count change, return-type change, type narrowing) - same.
- **Removed schema columns or model-name changes** - fail close, prompt for a migration plan.
- **Type widening** (e.g. `string` to `string | null`) - informational; flag for review but do not block.

Round close cannot pass until either: the diff is empty (no surface change); OR each surface change is documented
in the round's `completion-report.md` with reasoning; OR surface changes that should be reverted are reverted
before close.

## Why this is shared

Both NORMAL and STRUCTURAL_SWEEP rounds need this. Keeping it shared means one canonical capture script across
modes, improvements propagate automatically, and the acceptance gate is consistent so neither mode can ship
breaking changes by accident.

## Project-specific extension: the export-extraction script

The public-exports capture requires a project-provided script. The only contract is "one tab-separated line per
exported public symbol (path, name, kind, first-line signature), sorted, on stdout." A Node/TypeScript reference
implementation (using `ts-morph`) ships under `tools/refactoring/extract-api-surface.ts`. For other stacks, write
the equivalent against your language's parser or symbol-index tooling. Each project owns its surface-extraction
script; the shared diff machinery just consumes the output.

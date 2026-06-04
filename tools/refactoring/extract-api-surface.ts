// extract-api-surface.ts
//
// Refactoring-suite helper. Walks a TypeScript source tree, parses it, and emits one tab-separated
// line per exported public symbol with its first-line signature. The output is consumed by the
// round-close API-surface diff acceptance gate (see references/api-surface-diff.md), which diffs this
// round's surface against the prior round's to catch a behaviour-preserving fix that silently broke a
// public signature, removed an export, or narrowed a type while tests stayed green.
//
// This is the canonical Node/TypeScript reference implementation. For other stacks, write the
// equivalent against your language's parser or symbol-index tooling. The ONLY contract the shared diff
// machinery depends on is:
//   one line per exported public symbol, tab-separated as: <path>\t<name>\t<kind>\t<first-line-signature>
//   sorted, on stdout.
//
// Usage:
//   npx tsx tools/refactoring/extract-api-surface.ts                 # defaults: tsconfig.json, src/**
//   GLOB="lib/**/*.{ts,tsx}" TSCONFIG="tsconfig.build.json" npx tsx tools/refactoring/extract-api-surface.ts
//
// Dependency: ts-morph  (npm install --save-dev ts-morph)
//
// Parameterised, no project-specific paths or secrets. Override the source glob and tsconfig path via
// the GLOB and TSCONFIG environment variables.

import { Project } from "ts-morph";

const TSCONFIG = process.env.TSCONFIG ?? "tsconfig.json";
const GLOB = process.env.GLOB ?? "src/**/*.{ts,tsx}";
// Cap the captured signature so the snapshot stores enough signal for a diff without the full body.
const SIGNATURE_MAX = Number(process.env.SIGNATURE_MAX ?? 200);

function main(): void {
  const project = new Project({ tsConfigFilePath: TSCONFIG });
  const lines: string[] = [];
  const cwd = process.cwd();

  for (const file of project.getSourceFiles(GLOB)) {
    const path = file.getFilePath().replace(cwd + "/", "");
    for (const [name, declarations] of file.getExportedDeclarations()) {
      for (const decl of declarations) {
        const kind = decl.getKindName();
        // First line of the declaration text, capped: sufficient signal for a diff without storing
        // the full body. A param-count change, return-type change, or type narrowing all show up here.
        const signature = decl.getText().split("\n")[0].slice(0, SIGNATURE_MAX);
        lines.push([path, name, kind, signature].join("\t"));
      }
    }
  }

  // Sort so the diff is stable across runs (declaration order is not guaranteed).
  process.stdout.write(lines.sort().join("\n") + "\n");
}

main();

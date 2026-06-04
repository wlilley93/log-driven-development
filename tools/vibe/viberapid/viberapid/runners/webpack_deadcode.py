"""Runner for webpack dead code detection — finds unused files and exports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.webpack_deadcode import WebpackDeadcodeNormaliser
from viberapid.runners.base import AsyncToolRunner


class WebpackDeadcodeRunner(AsyncToolRunner):
    """Detect unused files and exports in webpack-based projects.

    Uses webpack-deadcode-plugin via npx if available, or falls back to
    analysing a webpack stats.json to find modules not in the dependency graph.

    Strategy:
    1. Look for existing deadcode report (from webpack-deadcode-plugin)
    2. If a stats.json is available, analyse it for unreachable modules
    3. Fall back to comparing source files against webpack module references
    """

    name = "webpack-deadcode"
    requires_node = True

    def should_run(self) -> bool:
        if not self._file_exists("package.json"):
            self.skip_reason = "no package.json found"
            return False

        # Require a webpack config to identify this as a webpack project
        has_webpack = self._file_exists(
            "webpack.config.js",
            "webpack.config.ts",
            "webpack.config.cjs",
            "webpack.config.mjs",
        )

        # Also accept next.js or CRA projects (which use webpack internally)
        has_next = self._file_exists("next.config.js", "next.config.mjs", "next.config.ts")
        has_cra = False
        pkg_path = Path(self.target) / "package.json"
        try:
            pkg_data = json.loads(pkg_path.read_text())
            scripts = pkg_data.get("scripts", {})
            if "react-scripts" in json.dumps(scripts):
                has_cra = True
        except (json.JSONDecodeError, OSError):
            pass

        if not has_webpack and not has_next and not has_cra:
            self.skip_reason = "no webpack configuration found"
            return False

        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        target = Path(self.target)

        # Strategy 1: Try to find an existing deadcode report
        report = self._find_deadcode_report(target)

        # Strategy 2: Analyse stats.json if available
        if report is None:
            report = self._analyse_stats_json(target)

        # Strategy 3: Run webpack-deadcode-plugin via npx
        if report is None:
            report = self._run_deadcode_plugin(target)

        # Strategy 4: Basic source-vs-module comparison
        if report is None:
            report = self._basic_deadcode_analysis(target)

        if report is None:
            return self._make_error_result(
                "Could not perform dead code analysis. Ensure the project has "
                "a webpack stats.json or install webpack-deadcode-plugin."
            )

        normaliser = WebpackDeadcodeNormaliser()
        findings = normaliser.normalise(report)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "unused_files": report.get("total_unused_files", len(report.get("unused_files", []))),
                "unused_exports": report.get("total_unused_exports", 0),
                "total_findings": len(findings),
            },
        )

    def _find_deadcode_report(self, target: Path) -> dict[str, Any] | None:
        """Look for a pre-generated deadcode report."""
        candidates = [
            target / "deadcode.json",
            target / ".deadcode.json",
            target / "reports" / "deadcode.json",
        ]

        for path in candidates:
            if path.exists():
                try:
                    data = json.loads(path.read_text())
                    if isinstance(data, dict) and (
                        "unused_files" in data or "unused_exports" in data
                    ):
                        return data
                except (json.JSONDecodeError, OSError):
                    continue

        return None

    def _analyse_stats_json(self, target: Path) -> dict[str, Any] | None:
        """Analyse a webpack stats.json to find unused source files."""
        stats_data = None

        for name in ("stats.json", "dist/stats.json", "build/stats.json"):
            path = target / name
            if path.exists():
                try:
                    stats_data = json.loads(path.read_text())
                    break
                except (json.JSONDecodeError, OSError):
                    continue

        if stats_data is None or not isinstance(stats_data, dict):
            return None

        # Collect all modules referenced in the webpack build
        referenced_modules: set[str] = set()
        chunks = stats_data.get("chunks", [])
        modules = stats_data.get("modules", [])

        # From top-level modules
        for mod in modules:
            if isinstance(mod, dict):
                name = mod.get("name", "")
                if name and not name.startswith("(webpack)"):
                    referenced_modules.add(self._normalise_module_name(name))

        # From chunk modules
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            for mod in chunk.get("modules", []):
                if isinstance(mod, dict):
                    name = mod.get("name", "")
                    if name and not name.startswith("(webpack)"):
                        referenced_modules.add(self._normalise_module_name(name))

        if not referenced_modules:
            return None

        # Find source files NOT in the webpack module graph
        src_dir = target / "src"
        if not src_dir.is_dir():
            return None

        source_files = set()
        for ext in ("*.ts", "*.tsx", "*.js", "*.jsx"):
            for f in src_dir.rglob(ext):
                rel = str(f.relative_to(target))
                # Skip test/spec files
                if any(p in rel for p in (".test.", ".spec.", "__tests__", "__mocks__")):
                    continue
                source_files.add(rel)

        unused_files = []
        for src_file in sorted(source_files):
            normalised = self._normalise_module_name(src_file)
            # Check if this file appears in any form in the webpack graph
            is_used = any(
                normalised in ref or ref in normalised
                for ref in referenced_modules
            )
            if not is_used:
                unused_files.append(src_file)

        return {
            "unused_files": unused_files,
            "unused_exports": {},
            "total_unused_files": len(unused_files),
            "total_unused_exports": 0,
        }

    def _run_deadcode_plugin(self, target: Path) -> dict[str, Any] | None:
        """Try to run webpack-deadcode-plugin to generate a report."""
        npx = self._npx_path()

        # Use webpack with deadcode plugin via a minimal config injection
        cmd = [
            npx, "webpack-deadcode-plugin",
            "--outputFile", ".viberapid-deadcode.json",
        ]

        try:
            self._exec(cmd, timeout=120)
            report_path = target / ".viberapid-deadcode.json"
            if report_path.exists():
                data = json.loads(report_path.read_text())
                report_path.unlink(missing_ok=True)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass

        return None

    def _basic_deadcode_analysis(self, target: Path) -> dict[str, Any] | None:
        """Fall back to basic analysis: find source files not imported anywhere."""
        src_dir = target / "src"
        if not src_dir.is_dir():
            return None

        # Collect all source files
        source_files: dict[str, Path] = {}
        for ext in ("*.ts", "*.tsx", "*.js", "*.jsx"):
            for f in src_dir.rglob(ext):
                rel = str(f.relative_to(target))
                if any(p in rel for p in (".test.", ".spec.", "__tests__", "__mocks__", ".d.ts")):
                    continue
                source_files[rel] = f

        if not source_files:
            return None

        # Build a simple import graph by scanning file contents
        imported_files: set[str] = set()
        for rel, filepath in source_files.items():
            try:
                content = filepath.read_text(errors="ignore")
            except OSError:
                continue

            # Scan for import/require statements and extract file references
            for line in content.split("\n"):
                stripped = line.strip()
                if not (stripped.startswith("import") or "require(" in stripped):
                    continue

                # Extract paths from import statements
                for quote in ('"', "'", "`"):
                    parts = stripped.split(quote)
                    for i in range(1, len(parts), 2):
                        import_path = parts[i]
                        if import_path.startswith("."):
                            # Resolve relative import
                            resolved = self._resolve_import(
                                filepath.parent, import_path, target
                            )
                            if resolved:
                                imported_files.add(resolved)

        # Entry points are always "used"
        entry_patterns = (
            "src/index.", "src/main.", "src/app.", "src/App.",
            "src/pages/", "src/routes/",
        )
        unused_files = []
        for rel in sorted(source_files.keys()):
            if any(rel.startswith(p) or p in rel for p in entry_patterns):
                continue
            if rel not in imported_files:
                unused_files.append(rel)

        if not unused_files:
            return None

        return {
            "unused_files": unused_files,
            "unused_exports": {},
            "total_unused_files": len(unused_files),
            "total_unused_exports": 0,
        }

    @staticmethod
    def _normalise_module_name(name: str) -> str:
        """Normalise a webpack module name for comparison."""
        # Remove webpack loader prefixes (e.g., "!./src/index.ts")
        if "!" in name:
            name = name.split("!")[-1]
        # Remove leading ./
        if name.startswith("./"):
            name = name[2:]
        return name

    @staticmethod
    def _resolve_import(from_dir: Path, import_path: str, root: Path) -> str | None:
        """Resolve a relative import to a project-relative path."""
        try:
            resolved = (from_dir / import_path).resolve()
        except (ValueError, OSError):
            return None

        # Try with extensions
        extensions = ("", ".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.tsx", "/index.js")
        for ext in extensions:
            candidate = Path(str(resolved) + ext)
            if candidate.exists() and candidate.is_file():
                try:
                    return str(candidate.relative_to(root))
                except ValueError:
                    return None

        return None

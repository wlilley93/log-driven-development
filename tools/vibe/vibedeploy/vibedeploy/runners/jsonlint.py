"""jsonlint runner — validate JSON config files for syntax errors."""

from __future__ import annotations

import json
from pathlib import Path

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.jsonlint import JsonlintNormaliser
from vibedeploy.runners.base import AsyncToolRunner

# JSON files to validate (config-oriented, not data dumps)
CONFIG_JSON_PATTERNS = [
    "package.json",
    "tsconfig.json",
    "tsconfig.*.json",
    "jsconfig.json",
    ".eslintrc.json",
    ".prettierrc.json",
    ".babelrc.json",
    "nest-cli.json",
    "angular.json",
    "composer.json",
    "appsettings.json",
    "appsettings.*.json",
    ".stylelintrc.json",
    "renovate.json",
    "vercel.json",
    "fly.toml",
    "firebase.json",
]


class JsonlintRunner(AsyncToolRunner):
    name = "jsonlint"

    def should_run(self) -> bool:
        json_files = self._scan_files("**/*.json")
        if not json_files:
            self.skip_reason = "no JSON files found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        target = Path(self.target)

        # Collect config JSON files
        json_files: list[Path] = []
        for pattern in CONFIG_JSON_PATTERNS:
            json_files.extend(self._scan_files(pattern))

        # Also check top-level .json files
        for f in target.glob("*.json"):
            if f not in json_files:
                json_files.append(f)

        # Check config directories
        for config_dir in ("config", ".github", ".vscode"):
            dir_path = target / config_dir
            if dir_path.is_dir():
                for f in dir_path.rglob("*.json"):
                    if f not in json_files:
                        json_files.append(f)

        # Filter out node_modules, dist, etc.
        skip_dirs = {"node_modules", ".venv", "venv", "vendor", ".git", "dist", "build", "coverage"}
        filtered_files = []
        for f in json_files:
            parts = set(f.parts)
            if not parts & skip_dirs:
                filtered_files.append(f)

        if not filtered_files:
            return ToolResult(tool=self.name, status=ToolStatus.SKIPPED)

        all_findings = []
        normaliser = JsonlintNormaliser()

        for json_file in filtered_files:
            try:
                rel_path = str(json_file.relative_to(target))
                content = json_file.read_text(errors="replace")

                try:
                    json.loads(content)
                except json.JSONDecodeError as e:
                    findings = normaliser.normalise({
                        "file": rel_path,
                        "error": str(e),
                        "line": e.lineno,
                        "col": e.colno,
                        "msg": e.msg,
                    })
                    all_findings.extend(findings)
            except OSError:
                continue

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=all_findings,
        )

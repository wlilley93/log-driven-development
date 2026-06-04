"""yamllint runner — lint YAML files for syntax and formatting issues."""

from __future__ import annotations

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.yamllint import YamllintNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class YamllintRunner(AsyncToolRunner):
    name = "yamllint"

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "yamllint not installed"
            return False
        yaml_files = self._scan_files("**/*.yml", "**/*.yaml")
        if not yaml_files:
            self.skip_reason = "no YAML files found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        yaml_files = self._scan_files("**/*.yml", "**/*.yaml")
        if not yaml_files:
            return ToolResult(tool=self.name, status=ToolStatus.SKIPPED)

        # Filter out node_modules, .venv, vendor directories
        skip_dirs = {"node_modules", ".venv", "venv", "vendor", ".git", "dist", "build"}
        filtered_files = []
        for f in yaml_files:
            parts = set(f.parts)
            if not parts & skip_dirs:
                filtered_files.append(f)

        if not filtered_files:
            return ToolResult(tool=self.name, status=ToolStatus.SKIPPED)

        all_findings = []
        normaliser = YamllintNormaliser()

        for yaml_file in filtered_files:
            try:
                rel_path = str(yaml_file.relative_to(self.target))
                cmd = [self.bin_path, "-f", "parsable", str(yaml_file)]
                result = self._exec(cmd, timeout=30)

                output = result.stdout.strip() or result.stderr.strip()
                if output:
                    findings = normaliser.normalise({
                        "output": output,
                        "file": rel_path,
                    })
                    all_findings.extend(findings)
            except Exception:
                continue

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=all_findings,
        )

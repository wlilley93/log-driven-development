"""hadolint runner — lint Dockerfiles for best practices."""

from __future__ import annotations

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.hadolint import HadolintNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class HadolintRunner(AsyncToolRunner):
    name = "hadolint"
    requires_docker = True

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "hadolint not installed"
            return False
        if not self._file_exists("Dockerfile"):
            self.skip_reason = "no Dockerfile found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        dockerfiles = self._scan_files("Dockerfile", "Dockerfile.*", "*.Dockerfile")
        if not dockerfiles:
            return ToolResult(tool=self.name, status=ToolStatus.SKIPPED)

        all_findings = []
        normaliser = HadolintNormaliser()

        for dockerfile in dockerfiles:
            try:
                cmd = [self.bin_path, "--format", "json", str(dockerfile)]
                data, stderr = self._exec_json(cmd)

                if data is not None:
                    # hadolint JSON output is a list of findings
                    # Inject the file path so the normaliser knows which file
                    if isinstance(data, list):
                        for item in data:
                            if "file" not in item:
                                item["file"] = str(dockerfile.relative_to(self.target))
                    findings = normaliser.normalise(data)
                    all_findings.extend(findings)
            except Exception:
                continue

        status = ToolStatus.SUCCESS
        return ToolResult(tool=self.name, status=status, findings=all_findings)

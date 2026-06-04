"""Detect .map files that may be served publicly."""

from __future__ import annotations

from pathlib import Path

from vibedeploy.models import Category, Effort, Finding, Severity


class SourceMapsServedRule:
    """Flag .map files in public build directories."""

    rule_id = "js-source-maps-public"
    rule_name = "Source Maps Served"

    _BUILD_DIRS = ["build", "dist", "public", ".next/static", "out", "www"]

    def scan(self, target: str) -> list[Finding]:
        findings = []
        target_path = Path(target)

        for build_dir in self._BUILD_DIRS:
            dir_path = target_path / build_dir
            if not dir_path.exists():
                continue

            map_files = list(dir_path.rglob("*.map"))
            if map_files:
                # Report first few, not all
                for map_file in map_files[:5]:
                    rel = str(map_file.relative_to(target))
                    findings.append(Finding(
                        tool="ast",
                        severity=Severity.HIGH,
                        category=Category.AST,
                        file=rel,
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        message=f"Source map file in build output — exposes original source code",
                        blocks_deploy=True,
                        effort=Effort.LOW,
                        fix_hint="Remove .map files from build or configure server to block *.map requests",
                        fix_command=f"find {build_dir} -name '*.map' -delete",
                    ))

                if len(map_files) > 5:
                    findings.append(Finding(
                        tool="ast",
                        severity=Severity.HIGH,
                        category=Category.AST,
                        file=str(dir_path.relative_to(target)),
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        message=f"... and {len(map_files) - 5} more .map files in {build_dir}/",
                        blocks_deploy=True,
                        effort=Effort.LOW,
                    ))

        return findings

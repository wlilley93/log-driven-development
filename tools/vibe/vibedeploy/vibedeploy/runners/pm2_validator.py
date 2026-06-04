"""pm2_validator — custom runner validating PM2 ecosystem config."""

from __future__ import annotations

import json
import re
from pathlib import Path

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner

PM2_CONFIG_FILES = [
    "ecosystem.config.js",
    "ecosystem.config.cjs",
    "pm2.json",
    "pm2.config.js",
    "pm2.config.cjs",
    "process.json",
    "process.yml",
]


class Pm2ValidatorRunner(AsyncToolRunner):
    name = "pm2_validator"

    def should_run(self) -> bool:
        for filename in PM2_CONFIG_FILES:
            if self._file_exists(filename):
                return True
        self.skip_reason = "no PM2 config file found"
        return False

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        findings: list[Finding] = []
        target = Path(self.target)

        config_file = None
        config_name = ""
        for filename in PM2_CONFIG_FILES:
            if (target / filename).exists():
                config_file = target / filename
                config_name = filename
                break

        if not config_file:
            return ToolResult(tool=self.name, status=ToolStatus.SKIPPED)

        content = self._read_file(config_file)

        # For JSON config files, parse and validate
        if config_name.endswith(".json"):
            try:
                config_data = json.loads(content)
                self._validate_json_config(config_data, config_name, findings)
            except json.JSONDecodeError:
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.HIGH,
                    category=Category.PROCESS,
                    file=config_name,
                    rule_id="pm2-invalid-json",
                    rule_name="Invalid PM2 JSON Config",
                    message=f"{config_name} contains invalid JSON",
                    blocks_deploy=True,
                    effort=Effort.LOW,
                ))
            return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=findings)

        # For JS config files, use regex-based heuristic checks
        self._validate_js_config(content, config_name, findings)

        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=findings)

    def _validate_json_config(
        self, data: dict | list, config_name: str, findings: list[Finding]
    ) -> None:
        apps = data if isinstance(data, list) else data.get("apps", [])
        if not apps:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.HIGH,
                category=Category.PROCESS,
                file=config_name,
                rule_id="pm2-no-apps",
                rule_name="No PM2 Apps Defined",
                message="PM2 config has no apps defined",
                blocks_deploy=True,
                effort=Effort.LOW,
            ))
            return

        for i, app in enumerate(apps):
            app_name = app.get("name", f"app-{i}")
            self._check_app_config(app, app_name, config_name, findings)

    def _validate_js_config(
        self, content: str, config_name: str, findings: list[Finding]
    ) -> None:
        # Check instances
        if re.search(r"""instances\s*:\s*['"]?1['"]?""", content):
            findings.append(Finding(
                tool=self.name,
                severity=Severity.MEDIUM,
                category=Category.PROCESS,
                file=config_name,
                rule_id="pm2-single-instance",
                rule_name="PM2 Single Instance",
                message=(
                    "PM2 config sets instances to 1. For production, use 'max' or a higher "
                    "number to leverage multiple CPU cores."
                ),
                blocks_deploy=False,
                effort=Effort.LOW,
                fix_hint="Set instances: 'max' or instances: os.cpus().length",
            ))

        # Check exec_mode
        if "exec_mode" not in content:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.MEDIUM,
                category=Category.PROCESS,
                file=config_name,
                rule_id="pm2-no-exec-mode",
                rule_name="PM2 Missing exec_mode",
                message=(
                    "PM2 config does not set exec_mode. Use 'cluster' mode for "
                    "zero-downtime reloads and multi-core utilization."
                ),
                blocks_deploy=False,
                effort=Effort.LOW,
                fix_hint="Add exec_mode: 'cluster' to your PM2 config",
            ))
        elif re.search(r"""exec_mode\s*:\s*['"]fork['"]""", content):
            findings.append(Finding(
                tool=self.name,
                severity=Severity.LOW,
                category=Category.PROCESS,
                file=config_name,
                rule_id="pm2-fork-mode",
                rule_name="PM2 Fork Mode",
                message=(
                    "PM2 is in 'fork' mode. Cluster mode is recommended for production "
                    "to enable zero-downtime reloads."
                ),
                blocks_deploy=False,
                effort=Effort.LOW,
                fix_hint="Change exec_mode to 'cluster'",
            ))

        # Check max_memory_restart
        if "max_memory_restart" not in content:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.MEDIUM,
                category=Category.PROCESS,
                file=config_name,
                rule_id="pm2-no-memory-limit",
                rule_name="PM2 No Memory Limit",
                message=(
                    "PM2 config does not set max_memory_restart. Without a memory limit, "
                    "memory leaks can crash the host."
                ),
                blocks_deploy=False,
                effort=Effort.LOW,
                fix_hint="Add max_memory_restart: '1G' (adjust to your needs)",
            ))

        # Check for production env
        if "env_production" not in content and "env.production" not in content:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.LOW,
                category=Category.PROCESS,
                file=config_name,
                rule_id="pm2-no-env-production",
                rule_name="PM2 No Production Environment",
                message=(
                    "PM2 config does not define env_production. Production environment "
                    "variables should be explicitly configured."
                ),
                blocks_deploy=False,
                effort=Effort.LOW,
                fix_hint="Add env_production: { NODE_ENV: 'production' } to your PM2 config",
            ))

    def _check_app_config(
        self, app: dict, app_name: str, config_name: str, findings: list[Finding]
    ) -> None:
        instances = app.get("instances", 1)
        if instances == 1:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.MEDIUM,
                category=Category.PROCESS,
                file=config_name,
                rule_id="pm2-single-instance",
                rule_name=f"PM2 Single Instance ({app_name})",
                message=f"App '{app_name}' has instances=1. Use 'max' or more for production.",
                blocks_deploy=False,
                effort=Effort.LOW,
                fix_hint="Set instances to 'max' or a number matching available CPU cores",
            ))

        exec_mode = app.get("exec_mode", "fork")
        if exec_mode != "cluster":
            findings.append(Finding(
                tool=self.name,
                severity=Severity.MEDIUM,
                category=Category.PROCESS,
                file=config_name,
                rule_id="pm2-no-cluster-mode",
                rule_name=f"PM2 Not Cluster Mode ({app_name})",
                message=f"App '{app_name}' exec_mode is '{exec_mode}', not 'cluster'",
                blocks_deploy=False,
                effort=Effort.LOW,
                fix_hint="Set exec_mode: 'cluster'",
            ))

        if "max_memory_restart" not in app:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.MEDIUM,
                category=Category.PROCESS,
                file=config_name,
                rule_id="pm2-no-memory-limit",
                rule_name=f"PM2 No Memory Limit ({app_name})",
                message=f"App '{app_name}' has no max_memory_restart set",
                blocks_deploy=False,
                effort=Effort.LOW,
                fix_hint="Add max_memory_restart: '1G' (adjust to your needs)",
            ))

        if "env_production" not in app:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.LOW,
                category=Category.PROCESS,
                file=config_name,
                rule_id="pm2-no-env-production",
                rule_name=f"PM2 No Production Env ({app_name})",
                message=f"App '{app_name}' has no env_production defined",
                blocks_deploy=False,
                effort=Effort.LOW,
                fix_hint="Add env_production: { NODE_ENV: 'production' }",
            ))

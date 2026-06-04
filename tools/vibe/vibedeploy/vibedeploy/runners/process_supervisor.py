"""process_supervisor — custom runner checking for process supervisor usage."""

from __future__ import annotations

import re
from pathlib import Path

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner

# Files that indicate a process supervisor is configured
SUPERVISOR_FILES = [
    "supervisord.conf",
    "supervisor.conf",
    "ecosystem.config.js",
    "ecosystem.config.cjs",
    "pm2.json",
    "pm2.config.js",
    "Procfile",
    "process.yml",
    "process.json",
]

# Systemd service file patterns
SYSTEMD_PATTERNS = ["*.service"]

# Patterns indicating multi-process apps
MULTI_PROCESS_INDICATORS = [
    re.compile(r"""cluster\.fork"""),                       # Node cluster
    re.compile(r"""multiprocessing\.(Process|Pool)"""),     # Python multiprocessing
    re.compile(r"""celery\s+worker""", re.IGNORECASE),     # Celery
    re.compile(r"""sidekiq""", re.IGNORECASE),              # Sidekiq
    re.compile(r"""rq\s+worker""", re.IGNORECASE),         # RQ
    re.compile(r"""background.*worker""", re.IGNORECASE),   # Generic background worker
    re.compile(r"""WorkerThread|ThreadPoolExecutor"""),     # Java/Python thread pools
]


class ProcessSupervisorRunner(AsyncToolRunner):
    name = "process_supervisor"

    def should_run(self) -> bool:
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        findings: list[Finding] = []
        target = Path(self.target)

        # Check which supervisor files exist
        supervisor_found = False
        for filename in SUPERVISOR_FILES:
            if (target / filename).exists():
                supervisor_found = True
                break

        # Check for systemd service files
        systemd_files = self._scan_files("**/*.service")
        if systemd_files:
            supervisor_found = True

        # Check if app appears to be multi-process
        is_multi_process = False
        multi_process_file = ""
        source_exts = ("**/*.py", "**/*.js", "**/*.ts", "**/*.rb", "**/*.go", "**/*.java")
        for ext_pattern in source_exts:
            for src_file in self._scan_files(ext_pattern):
                try:
                    content = src_file.read_text(errors="replace")
                except OSError:
                    continue
                for pattern in MULTI_PROCESS_INDICATORS:
                    if pattern.search(content):
                        is_multi_process = True
                        try:
                            multi_process_file = str(src_file.relative_to(target))
                        except ValueError:
                            multi_process_file = str(src_file)
                        break
                if is_multi_process:
                    break
            if is_multi_process:
                break

        # Multi-process app without a supervisor is a problem
        if is_multi_process and not supervisor_found:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.MEDIUM,
                category=Category.PROCESS,
                file=multi_process_file or ".",
                rule_id="no-process-supervisor",
                rule_name="Missing Process Supervisor",
                message=(
                    "Multi-process application detected but no process supervisor found. "
                    "Use supervisord, PM2, systemd, or a Procfile to manage multiple processes "
                    "and ensure they restart on failure."
                ),
                blocks_deploy=False,
                effort=Effort.MEDIUM,
                fix_hint=(
                    "Add a Procfile (for Heroku/Dokku), ecosystem.config.js (for PM2), "
                    "or supervisord.conf to manage processes"
                ),
            ))

        # Check for Dockerfile running multiple processes without supervisor
        dockerfile = target / "Dockerfile"
        if dockerfile.exists():
            content = self._read_file(dockerfile)
            # Detect multiple CMD/ENTRYPOINT with && or shell scripts
            cmd_lines = [
                line for line in content.split("\n")
                if re.match(r"^\s*(CMD|ENTRYPOINT)\s+", line)
            ]
            for cmd_line in cmd_lines:
                if "&&" in cmd_line and ("&" in cmd_line.replace("&&", "")):
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.MEDIUM,
                        category=Category.PROCESS,
                        file="Dockerfile",
                        rule_id="dockerfile-multi-process-no-supervisor",
                        rule_name="Dockerfile Multi-Process Without Supervisor",
                        message=(
                            "Dockerfile CMD/ENTRYPOINT appears to run multiple processes "
                            "without a supervisor. Background processes won't be monitored "
                            "or restarted on failure."
                        ),
                        blocks_deploy=False,
                        effort=Effort.MEDIUM,
                        fix_hint="Use supervisord or tini as PID 1 to manage child processes",
                    ))
                    break

        # If supervisor is found, check for basic misconfiguration
        if (target / "supervisord.conf").exists():
            content = self._read_file("supervisord.conf")
            if "autorestart" not in content:
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.LOW,
                    category=Category.PROCESS,
                    file="supervisord.conf",
                    rule_id="supervisor-no-autorestart",
                    rule_name="Supervisor Missing Autorestart",
                    message="supervisord.conf does not set autorestart — processes won't recover from crashes",
                    blocks_deploy=False,
                    effort=Effort.TRIVIAL,
                    fix_hint="Add autorestart=true under [program:x] sections",
                ))

        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=findings)

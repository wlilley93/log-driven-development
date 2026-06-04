"""log_level_checker — custom runner checking logging configuration."""

from __future__ import annotations

import re
from pathlib import Path

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner

# Structured logging library patterns
STRUCTURED_LOGGING_PATTERNS = [
    re.compile(r"""import\s+(?:winston|pino|bunyan|log4js|morgan|loglevel)"""),
    re.compile(r"""require\s*\(\s*['"](?:winston|pino|bunyan|log4js|morgan|loglevel)['"]"""),
    re.compile(r"""from\s+(?:winston|pino|bunyan|log4js)"""),
    re.compile(r"""import\s+logging"""),                      # Python stdlib
    re.compile(r"""from\s+loguru\s+import"""),                 # Python loguru
    re.compile(r"""import\s+structlog"""),                     # Python structlog
    re.compile(r"""log\s*(?:::|\.)\s*(?:New|Logger)"""),       # Go
    re.compile(r"""Logger\.getLogger"""),                      # Java
    re.compile(r"""Rails\.logger|Logger\.new"""),              # Ruby
    re.compile(r"""use\s+(?:tracing|log|env_logger)"""),       # Rust
    re.compile(r"""import\s+.*(?:zerolog|zap|logrus)"""),      # Go structured
]

# console.log as primary logging (no structured logger)
CONSOLE_LOG_PATTERN = re.compile(r"""\bconsole\.(log|warn|error|info|debug)\s*\(""")

# Debug log level in production config
DEBUG_IN_PROD_PATTERNS = [
    re.compile(r"""LOG_LEVEL\s*[=:]\s*['"]?debug['"]?""", re.IGNORECASE),
    re.compile(r"""level\s*[=:]\s*['"]?debug['"]?""", re.IGNORECASE),
    re.compile(r"""logging\.DEBUG"""),
    re.compile(r"""DJANGO_LOG_LEVEL\s*=\s*['"]?DEBUG['"]?"""),
    re.compile(r"""FLASK_DEBUG\s*=\s*['"]?(?:1|true)['"]?""", re.IGNORECASE),
]

# Log aggregation config patterns
LOG_AGGREGATION_PATTERNS = [
    re.compile(r"""fluentd|fluent-bit|filebeat|logstash|vector""", re.IGNORECASE),
    re.compile(r"""PAPERTRAIL|LOGGLY|DATADOG|SPLUNK|ELASTIC""", re.IGNORECASE),
    re.compile(r"""CloudWatch|stackdriver""", re.IGNORECASE),
    re.compile(r"""rsyslog|syslog""", re.IGNORECASE),
    re.compile(r"""loki|grafana""", re.IGNORECASE),
]

NODE_EXTENSIONS = {".js", ".ts", ".mjs", ".cjs", ".jsx", ".tsx"}
PYTHON_EXTENSIONS = {".py"}
SOURCE_EXTENSIONS = NODE_EXTENSIONS | PYTHON_EXTENSIONS | {".go", ".rb", ".java", ".rs"}


class LogLevelCheckerRunner(AsyncToolRunner):
    name = "log_level_checker"

    def should_run(self) -> bool:
        for ext in SOURCE_EXTENSIONS:
            if self._scan_files(f"**/*{ext}", max_files=1):
                return True
        self.skip_reason = "no source files found"
        return False

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        findings: list[Finding] = []
        target = Path(self.target)

        # Detect if project is Node.js based
        is_node = (target / "package.json").exists()
        is_python = (target / "requirements.txt").exists() or (target / "pyproject.toml").exists()

        # Scan for structured logging usage (cap file reads for large projects)
        has_structured_logging = False
        console_log_count = 0
        console_log_files: list[str] = []

        # Phase 1: Check config/entry files for structured logging (fast path)
        _LIKELY_NAMES = ("*logger*", "*logging*", "*log*", "*server*", "*app*", "*index*", "*main*")
        for name_pat in _LIKELY_NAMES:
            if has_structured_logging:
                break
            for ext in SOURCE_EXTENSIONS:
                for f in self._scan_files(f"**/{name_pat}{ext}", max_files=50):
                    try:
                        content = f.read_text(errors="replace")
                    except OSError:
                        continue
                    for pattern in STRUCTURED_LOGGING_PATTERNS:
                        if pattern.search(content):
                            has_structured_logging = True
                            break
                    if has_structured_logging:
                        break

        # Phase 2: Broader scan (capped) if not found yet + count console.log
        source_files: list[Path] = []
        for ext in SOURCE_EXTENSIONS:
            source_files.extend(self._scan_files(f"**/*{ext}", max_files=500))

        for src_file in source_files:
            try:
                content = src_file.read_text(errors="replace")
            except OSError:
                continue

            if not has_structured_logging:
                for pattern in STRUCTURED_LOGGING_PATTERNS:
                    if pattern.search(content):
                        has_structured_logging = True
                        break

            # Count console.log usage in Node files (cap at 10 files)
            if is_node and src_file.suffix in NODE_EXTENSIONS and len(console_log_files) < 10:
                matches = CONSOLE_LOG_PATTERN.findall(content)
                if matches:
                    console_log_count += len(matches)
                    try:
                        console_log_files.append(str(src_file.relative_to(target)))
                    except ValueError:
                        console_log_files.append(str(src_file))

        # No structured logging at all
        if not has_structured_logging:
            if is_node and console_log_count > 0:
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.MEDIUM,
                    category=Category.LOGGING,
                    file=console_log_files[0] if console_log_files else ".",
                    rule_id="console-log-only",
                    rule_name="Only console.log Logging",
                    message=(
                        f"Found {console_log_count} console.log/warn/error calls across "
                        f"{len(console_log_files)} files but no structured logging library. "
                        f"Structured logging with levels, timestamps, and JSON format is "
                        f"essential for production log aggregation."
                    ),
                    blocks_deploy=False,
                    effort=Effort.MEDIUM,
                    fix_hint="Install a structured logging library (pino, winston) and replace console.log calls",
                ))
            elif not is_node:
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.MEDIUM,
                    category=Category.LOGGING,
                    file=".",
                    rule_id="no-structured-logging",
                    rule_name="No Structured Logging",
                    message=(
                        "No structured logging library detected. Production applications "
                        "need structured logging with levels, timestamps, and correlation IDs."
                    ),
                    blocks_deploy=False,
                    effort=Effort.MEDIUM,
                    fix_hint="Add a structured logging library appropriate for your stack",
                ))

        # Check for DEBUG log level in production configs
        prod_configs = [
            ".env.production", ".env.prod", ".env",
            "config/production.json", "config/production.yml",
        ]
        for config_name in prod_configs:
            config_path = target / config_name
            if config_path.exists():
                content = self._read_file(config_path)
                for i, line in enumerate(content.split("\n"), 1):
                    for pattern in DEBUG_IN_PROD_PATTERNS:
                        if pattern.search(line):
                            findings.append(Finding(
                                tool=self.name,
                                severity=Severity.MEDIUM,
                                category=Category.LOGGING,
                                file=config_name,
                                line=i,
                                rule_id="debug-level-production",
                                rule_name="Debug Log Level in Production",
                                message=(
                                    f"Debug log level detected in {config_name}. "
                                    f"Debug logging in production creates excessive log volume "
                                    f"and may leak sensitive data."
                                ),
                                blocks_deploy=False,
                                effort=Effort.TRIVIAL,
                                fix_hint="Set log level to 'info' or 'warn' for production",
                            ))
                            break

        # Check for log aggregation
        has_aggregation = False
        check_files = [
            "docker-compose.yml", "docker-compose.yaml", ".env", ".env.production",
            "fluent.conf", "filebeat.yml", "vector.toml", "fluentd.conf",
        ]
        for check_name in check_files:
            check_path = target / check_name
            if check_path.exists():
                content = self._read_file(check_path)
                for pattern in LOG_AGGREGATION_PATTERNS:
                    if pattern.search(content):
                        has_aggregation = True
                        break
            if has_aggregation:
                break

        if not has_aggregation:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.LOW,
                category=Category.LOGGING,
                file=".",
                rule_id="no-log-aggregation",
                rule_name="No Log Aggregation Config",
                message=(
                    "No log aggregation service detected (Fluentd, Filebeat, Datadog, etc.). "
                    "Centralized logging is important for production debugging."
                ),
                blocks_deploy=False,
                effort=Effort.MEDIUM,
                fix_hint="Configure a log aggregation pipeline (ELK, Loki, Datadog, etc.)",
            ))

        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=findings)

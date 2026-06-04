"""debug_mode_checker — custom runner checking for debug mode in production config."""

from __future__ import annotations

import re
from pathlib import Path

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner

# Patterns that indicate debug/dev mode in production
# (pattern, rule_id, description, severity, blocks_deploy, file_globs)
_DEBUG_PATTERNS: list[tuple[re.Pattern, str, str, Severity, bool, tuple[str, ...]]] = [
    (
        re.compile(r'\bDEBUG\s*=\s*True\b', re.IGNORECASE),
        "debug-true",
        "DEBUG=True found — application running in debug mode",
        Severity.CRITICAL,
        True,
        ("*.py", "*.cfg", "*.ini", "*.env*", "*.toml"),
    ),
    (
        re.compile(r'\bapp\.debug\s*=\s*True\b', re.IGNORECASE),
        "flask-debug",
        "Flask app.debug=True found — debug mode enabled",
        Severity.CRITICAL,
        True,
        ("*.py",),
    ),
    (
        re.compile(r'FLASK_ENV\s*=\s*["\']?development["\']?', re.IGNORECASE),
        "flask-env-dev",
        "FLASK_ENV=development found — Flask running in development mode",
        Severity.CRITICAL,
        True,
        ("*.env*", "*.py", "*.cfg", "*.ini", "*.yml", "*.yaml", "docker-compose*"),
    ),
    (
        re.compile(r'FLASK_DEBUG\s*=\s*["\']?[1tTyY]', re.IGNORECASE),
        "flask-debug-env",
        "FLASK_DEBUG enabled — debug mode exposes interactive debugger",
        Severity.CRITICAL,
        True,
        ("*.env*", "*.py", "*.cfg", "*.yml", "*.yaml", "docker-compose*"),
    ),
    (
        re.compile(r'DJANGO_DEBUG\s*=\s*["\']?[1tTyY]', re.IGNORECASE),
        "django-debug",
        "DJANGO_DEBUG enabled — stack traces exposed to users",
        Severity.CRITICAL,
        True,
        ("*.env*", "*.py", "*.cfg", "*.yml", "*.yaml"),
    ),
    (
        re.compile(r'NODE_ENV\s*=\s*["\']?development["\']?'),
        "node-env-dev",
        "NODE_ENV=development found in config — not production optimized",
        Severity.HIGH,
        True,
        ("*.env*", "*.yml", "*.yaml", "docker-compose*", "Dockerfile*"),
    ),
    (
        re.compile(r'NEXT_PUBLIC_DEBUG\s*=\s*["\']?[1tTyY]', re.IGNORECASE),
        "nextjs-debug",
        "NEXT_PUBLIC_DEBUG enabled — debug info exposed to client",
        Severity.HIGH,
        True,
        ("*.env*", "*.yml", "*.yaml"),
    ),
    (
        re.compile(r'RAILS_ENV\s*=\s*["\']?development["\']?'),
        "rails-env-dev",
        "RAILS_ENV=development found — Rails not in production mode",
        Severity.CRITICAL,
        True,
        ("*.env*", "*.yml", "*.yaml", "docker-compose*"),
    ),
    (
        re.compile(r'APP_DEBUG\s*=\s*["\']?true["\']?', re.IGNORECASE),
        "laravel-debug",
        "APP_DEBUG=true found — Laravel debug mode exposes stack traces",
        Severity.CRITICAL,
        True,
        ("*.env*", "*.yml", "*.yaml"),
    ),
    (
        re.compile(r'spring\.profiles\.active\s*=\s*["\']?dev', re.IGNORECASE),
        "spring-dev-profile",
        "Spring development profile active in config",
        Severity.HIGH,
        True,
        ("*.properties", "*.yml", "*.yaml", "*.env*"),
    ),
]

# Patterns for console.log/print statements in source (lower severity)
_CONSOLE_PATTERNS: list[tuple[re.Pattern, str, str, tuple[str, ...]]] = [
    (
        re.compile(r'\bconsole\.(log|debug|trace)\s*\(', re.IGNORECASE),
        "console-log",
        "console.log/debug/trace statement found — remove or guard for production",
        ("*.js", "*.ts", "*.jsx", "*.tsx"),
    ),
    (
        re.compile(r'\bprint\s*\(\s*f?["\']', re.MULTILINE),
        "python-print",
        "print() statement found — use logging module instead",
        ("*.py",),
    ),
]

# Directories to skip (vendor, node_modules, test files, etc.)
_SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".next", "venv", ".venv",
    "vendor", "dist", "build", ".tox", ".eggs", "coverage",
}

# Maximum file size to scan (skip huge generated files)
_MAX_FILE_SIZE = 512 * 1024  # 512 KB


class DebugModeCheckerRunner(AsyncToolRunner):
    name = "debug_mode_checker"

    def should_run(self) -> bool:
        # Always runs — custom checker, no binary needed
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        findings: list[Finding] = []
        target = Path(self.target)

        # Step 1: Check for debug mode in config files
        for pattern, rule_id, description, severity, blocks, file_globs in _DEBUG_PATTERNS:
            for glob in file_globs:
                for filepath in self._rglob_safe(target, glob, max_files=200):
                    self._scan_file_for_pattern(
                        filepath, pattern, rule_id, description, severity, blocks, findings
                    )

        # Step 2: Check for excessive console.log/print (INFO level, non-blocking)
        # Only scan a reasonable number of files
        console_finding_count = 0
        max_console_findings = 10  # Cap to avoid noise

        for pattern, rule_id, description, file_globs in _CONSOLE_PATTERNS:
            if console_finding_count >= max_console_findings:
                break
            for glob in file_globs:
                if console_finding_count >= max_console_findings:
                    break
                for filepath in self._rglob_safe(target, glob, max_files=300):
                    if console_finding_count >= max_console_findings:
                        break
                    count = self._count_pattern_in_file(filepath, pattern)
                    if count > 0:
                        rel = str(filepath.relative_to(self.target))
                        findings.append(Finding(
                            tool=self.name,
                            severity=Severity.INFO,
                            category=Category.BUILD,
                            file=rel,
                            rule_id=rule_id,
                            rule_name=rule_id.replace("-", " ").title(),
                            message=f"{description} ({count} occurrence{'s' if count != 1 else ''} in {rel})",
                            blocks_deploy=False,
                            effort=Effort.TRIVIAL,
                            fix_hint="Remove debug logging or guard with environment check",
                        ))
                        console_finding_count += 1

        # Step 3: Check Docker/compose files for dev-specific settings
        self._check_docker_debug(target, findings)

        status = ToolStatus.SUCCESS
        return ToolResult(tool=self.name, status=status, findings=findings)

    def _scan_file_for_pattern(
        self,
        filepath: Path,
        pattern: re.Pattern,
        rule_id: str,
        description: str,
        severity: Severity,
        blocks: bool,
        findings: list[Finding],
    ) -> None:
        """Scan a single file for a debug pattern and add findings."""
        try:
            content = filepath.read_text(errors="replace")
        except OSError:
            return

        rel = str(filepath.relative_to(self.target))

        for i, line in enumerate(content.split("\n"), 1):
            # Skip commented lines
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("*"):
                continue

            if pattern.search(line):
                findings.append(Finding(
                    tool=self.name,
                    severity=severity,
                    category=Category.BUILD,
                    file=rel,
                    line=i,
                    rule_id=rule_id,
                    rule_name=rule_id.replace("-", " ").title(),
                    message=f"{description} (line {i})",
                    blocks_deploy=blocks,
                    effort=Effort.TRIVIAL,
                    fix_hint="Set to production values before deploying",
                ))
                # One finding per file per pattern is enough
                return

    def _count_pattern_in_file(self, filepath: Path, pattern: re.Pattern) -> int:
        """Count occurrences of a pattern in a file."""
        try:
            content = filepath.read_text(errors="replace")
        except OSError:
            return 0
        return len(pattern.findall(content))

    def _rglob_safe(self, root: Path, pattern: str, max_files: int = 1000) -> list[Path]:
        """rglob that skips vendor/node_modules/test dirs and large files."""
        results = []
        try:
            for filepath in root.rglob(pattern):
                # Skip excluded directories
                parts = set(filepath.parts)
                if parts & _SKIP_DIRS:
                    continue
                # Skip test files
                if any(p.startswith("test") or p == "tests" or p == "__tests__" for p in filepath.parts):
                    continue
                # Skip large files
                try:
                    if filepath.stat().st_size > _MAX_FILE_SIZE:
                        continue
                except OSError:
                    continue
                if filepath.is_file():
                    results.append(filepath)
                    if len(results) >= max_files:
                        return results
        except OSError:
            pass
        return results

    def _check_docker_debug(self, target: Path, findings: list[Finding]) -> None:
        """Check Docker-related files for development configurations."""
        compose_files = list(target.glob("docker-compose*.yml")) + list(target.glob("docker-compose*.yaml"))
        for compose_file in compose_files:
            try:
                content = compose_file.read_text(errors="replace")
            except OSError:
                continue

            rel = str(compose_file.relative_to(self.target))

            # Check for volume mounts of source code (dev pattern)
            if re.search(r'volumes:\s*\n\s*-\s*\./[^:]+:/[^:]+', content):
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.MEDIUM,
                    category=Category.BUILD,
                    file=rel,
                    rule_id="docker-compose-dev-volumes",
                    rule_name="Docker Compose Dev Volumes",
                    message=f"docker-compose has source code volume mounts — likely dev configuration",
                    blocks_deploy=False,
                    effort=Effort.LOW,
                    fix_hint="Use a separate docker-compose.prod.yml without source mounts for production",
                ))

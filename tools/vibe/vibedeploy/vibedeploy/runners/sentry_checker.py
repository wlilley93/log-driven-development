"""sentry_checker — custom runner checking error tracking setup."""

from __future__ import annotations

import re
from pathlib import Path

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner

# Sentry SDK patterns in source code
SENTRY_PATTERNS = [
    re.compile(r"""@sentry/"""),
    re.compile(r"""import\s+\*\s+as\s+Sentry"""),
    re.compile(r"""require\s*\(\s*['"]@sentry/"""),
    re.compile(r"""import\s+sentry_sdk"""),
    re.compile(r"""from\s+sentry_sdk"""),
    re.compile(r"""sentry_sdk\.init"""),
    re.compile(r"""Sentry\.init\s*\("""),
    re.compile(r"""Raven\."""),                     # Legacy Sentry client
    re.compile(r"""sentry\.io"""),
]

# Sentry DSN pattern
SENTRY_DSN_PATTERN = re.compile(r"""SENTRY_DSN|NEXT_PUBLIC_SENTRY_DSN|REACT_APP_SENTRY_DSN""")

# Alternative error tracking services
ALT_ERROR_TRACKING_PATTERNS = [
    re.compile(r"""bugsnag""", re.IGNORECASE),
    re.compile(r"""rollbar""", re.IGNORECASE),
    re.compile(r"""airbrake""", re.IGNORECASE),
    re.compile(r"""honeybadger""", re.IGNORECASE),
    re.compile(r"""raygun""", re.IGNORECASE),
    re.compile(r"""trackjs""", re.IGNORECASE),
    re.compile(r"""logrocket""", re.IGNORECASE),
]

# Error boundary patterns (React)
ERROR_BOUNDARY_PATTERNS = [
    re.compile(r"""ErrorBoundary"""),
    re.compile(r"""componentDidCatch"""),
    re.compile(r"""getDerivedStateFromError"""),
    re.compile(r"""Sentry\.ErrorBoundary"""),
]

# Unhandled rejection handler patterns
UNHANDLED_REJECTION_PATTERNS = [
    re.compile(r"""process\.on\s*\(\s*['"]unhandledRejection['"]"""),
    re.compile(r"""process\.on\s*\(\s*['"]uncaughtException['"]"""),
    re.compile(r"""window\.addEventListener\s*\(\s*['"]unhandledrejection['"]"""),
    re.compile(r"""window\.onerror"""),
    re.compile(r"""sys\.excepthook"""),
    re.compile(r"""threading\.excepthook"""),
]

SOURCE_EXTENSIONS = {".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs", ".py", ".go", ".rb", ".java"}


class SentryCheckerRunner(AsyncToolRunner):
    name = "sentry_checker"

    def should_run(self) -> bool:
        for ext in SOURCE_EXTENSIONS:
            if self._scan_files(f"**/*{ext}", max_files=1):
                return True
        self.skip_reason = "no source files found"
        return False

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        findings: list[Finding] = []
        target = Path(self.target)

        sentry_found = False
        alt_error_tracking_found = False
        error_boundary_found = False
        unhandled_rejection_found = False

        is_react = False
        is_node = (target / "package.json").exists()

        # Check package files for Sentry deps
        for pkg_file in ("package.json", "requirements.txt", "pyproject.toml", "go.mod", "Gemfile"):
            pkg_path = target / pkg_file
            if pkg_path.exists():
                content = self._read_file(pkg_path)
                for pattern in SENTRY_PATTERNS:
                    if pattern.search(content):
                        sentry_found = True
                        break
                if not sentry_found:
                    for pattern in ALT_ERROR_TRACKING_PATTERNS:
                        if pattern.search(content):
                            alt_error_tracking_found = True
                            break
                if pkg_file == "package.json" and "react" in content:
                    is_react = True

        # Check env files for Sentry DSN
        sentry_dsn_configured = False
        for env_name in (".env", ".env.example", ".env.production", ".env.local"):
            env_path = target / env_name
            if env_path.exists():
                content = self._read_file(env_path)
                if SENTRY_DSN_PATTERN.search(content):
                    sentry_dsn_configured = True
                    if not sentry_found:
                        sentry_found = True

        # Scan source files (capped to avoid timeout on large projects)
        # Prioritise likely files first
        _LIKELY_NAMES = ("*sentry*", "*error*", "*instrument*", "*app*", "*server*", "*index*", "*main*", "*_app*")
        priority_files: list[Path] = []
        seen: set[Path] = set()
        for name_pat in _LIKELY_NAMES:
            for ext in SOURCE_EXTENSIONS:
                for f in self._scan_files(f"**/{name_pat}{ext}", max_files=50):
                    if f not in seen:
                        priority_files.append(f)
                        seen.add(f)

        remaining_files: list[Path] = []
        for ext in SOURCE_EXTENSIONS:
            for f in self._scan_files(f"**/*{ext}", max_files=500):
                if f not in seen:
                    remaining_files.append(f)
                    seen.add(f)
                if len(remaining_files) >= 500:
                    break
            if len(remaining_files) >= 500:
                break

        all_done = False
        for src_file in priority_files + remaining_files:
            if all_done:
                break

            try:
                content = src_file.read_text(errors="replace")
            except OSError:
                continue

            if not sentry_found:
                for pattern in SENTRY_PATTERNS:
                    if pattern.search(content):
                        sentry_found = True
                        break

            if not alt_error_tracking_found and not sentry_found:
                for pattern in ALT_ERROR_TRACKING_PATTERNS:
                    if pattern.search(content):
                        alt_error_tracking_found = True
                        break

            if not error_boundary_found:
                for pattern in ERROR_BOUNDARY_PATTERNS:
                    if pattern.search(content):
                        error_boundary_found = True
                        break

            if not unhandled_rejection_found:
                for pattern in UNHANDLED_REJECTION_PATTERNS:
                    if pattern.search(content):
                        unhandled_rejection_found = True
                        break

            # Stop early if everything is found
            tracking_found = sentry_found or alt_error_tracking_found
            all_done = tracking_found and error_boundary_found and unhandled_rejection_found

        # No error tracking at all
        if not sentry_found and not alt_error_tracking_found:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.MEDIUM,
                category=Category.LOGGING,
                file=".",
                rule_id="no-error-tracking",
                rule_name="No Error Tracking Service",
                message=(
                    "No error tracking service (Sentry, Bugsnag, Rollbar, etc.) detected. "
                    "Error tracking is critical for production to catch and diagnose "
                    "unhandled exceptions and crashes."
                ),
                blocks_deploy=False,
                effort=Effort.MEDIUM,
                fix_hint="Install Sentry SDK: npm install @sentry/node (Node) or pip install sentry-sdk (Python)",
                docs_url="https://docs.sentry.io/platforms/",
            ))

        # Sentry found but DSN not configured
        if sentry_found and not sentry_dsn_configured:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.HIGH,
                category=Category.LOGGING,
                file=".env",
                rule_id="sentry-no-dsn",
                rule_name="Sentry DSN Not Configured",
                message=(
                    "Sentry SDK is installed but SENTRY_DSN is not set in environment files. "
                    "Without a DSN, errors will not be reported."
                ),
                blocks_deploy=False,
                effort=Effort.TRIVIAL,
                fix_hint="Set SENTRY_DSN=https://examplePublicKey@o0.ingest.sentry.io/0 in .env",
            ))

        # React app without error boundary
        if is_react and not error_boundary_found:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.MEDIUM,
                category=Category.LOGGING,
                file=".",
                rule_id="no-error-boundary",
                rule_name="Missing React Error Boundary",
                message=(
                    "React application detected but no ErrorBoundary component found. "
                    "An error boundary prevents the entire UI from crashing on component errors."
                ),
                blocks_deploy=False,
                effort=Effort.LOW,
                fix_hint="Add an ErrorBoundary wrapper component or use Sentry.ErrorBoundary",
                docs_url="https://react.dev/reference/react/Component#catching-rendering-errors-with-an-error-boundary",
            ))

        # Node app without unhandled rejection handler
        if is_node and not unhandled_rejection_found:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.MEDIUM,
                category=Category.LOGGING,
                file=".",
                rule_id="no-unhandled-rejection-handler",
                rule_name="No Unhandled Rejection Handler",
                message=(
                    "Node.js application has no unhandledRejection/uncaughtException handlers. "
                    "Unhandled promise rejections can crash the process in Node 15+."
                ),
                blocks_deploy=False,
                effort=Effort.LOW,
                fix_hint=(
                    "Add process.on('unhandledRejection', handler) and "
                    "process.on('uncaughtException', handler)"
                ),
            ))

        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=findings)

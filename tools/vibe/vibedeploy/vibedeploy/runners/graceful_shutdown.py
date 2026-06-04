"""graceful_shutdown — custom runner checking for graceful shutdown handling."""

from __future__ import annotations

import re
from pathlib import Path

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner

# Python signal handler patterns
PYTHON_SIGNAL_PATTERNS = [
    re.compile(r"""signal\.signal\s*\(\s*signal\.SIG(TERM|INT)"""),
    re.compile(r"""signal\.Signals\.SIG(TERM|INT)"""),
    re.compile(r"""atexit\.register"""),
    re.compile(r"""asyncio\.get.*loop\(\)\.add_signal_handler"""),
    re.compile(r"""GracefulKiller|SignalHandler|shutdown_handler""", re.IGNORECASE),
    re.compile(r"""uvicorn.*--timeout-graceful-shutdown"""),
    re.compile(r"""gunicorn.*graceful_timeout"""),
]

# Node.js signal handler patterns
NODE_SIGNAL_PATTERNS = [
    re.compile(r"""process\.on\s*\(\s*['"](SIGTERM|SIGINT|beforeExit|exit)['"]"""),
    re.compile(r"""server\.close\s*\("""),
    re.compile(r"""gracefulShutdown|graceful-shutdown|shutdown-handler""", re.IGNORECASE),
    re.compile(r"""closeGracefully|handleShutdown""", re.IGNORECASE),
]

# Go signal patterns
GO_SIGNAL_PATTERNS = [
    re.compile(r"""signal\.Notify\s*\("""),
    re.compile(r"""os\.Signal"""),
    re.compile(r"""syscall\.SIGTERM"""),
    re.compile(r"""server\.Shutdown\("""),
]

# Ruby signal patterns
RUBY_SIGNAL_PATTERNS = [
    re.compile(r"""Signal\.trap\s*\(\s*['"](TERM|INT)['"]"""),
    re.compile(r"""trap\s*\(\s*['"](TERM|INT)['"]"""),
]

# Java signal patterns
JAVA_SIGNAL_PATTERNS = [
    re.compile(r"""Runtime\.getRuntime\(\)\.addShutdownHook"""),
    re.compile(r"""Signal\.handle"""),
]

LANG_PATTERNS: dict[str, tuple[list[str], list[re.Pattern]]] = {
    "python": ([".py"], PYTHON_SIGNAL_PATTERNS),
    "node": ([".js", ".ts", ".mjs", ".cjs", ".jsx", ".tsx"], NODE_SIGNAL_PATTERNS),
    "go": ([".go"], GO_SIGNAL_PATTERNS),
    "ruby": ([".rb"], RUBY_SIGNAL_PATTERNS),
    "java": ([".java"], JAVA_SIGNAL_PATTERNS),
}


class GracefulShutdownRunner(AsyncToolRunner):
    name = "graceful_shutdown"

    def should_run(self) -> bool:
        for exts, _ in LANG_PATTERNS.values():
            for ext in exts:
                if self._scan_files(f"**/*{ext}", max_files=1):
                    return True
        self.skip_reason = "no supported source files found"
        return False

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        findings: list[Finding] = []
        target = Path(self.target)

        # Detect which languages are in use (cap files to avoid timeout on large projects)
        detected_langs: dict[str, list[Path]] = {}
        for lang, (exts, _) in LANG_PATTERNS.items():
            # Prioritise entry-point files first
            _ENTRY_NAMES = ("*server*", "*app*", "*main*", "*index*", "*worker*", "*start*")
            files: list[Path] = []
            seen: set[Path] = set()
            for name_pat in _ENTRY_NAMES:
                for ext in exts:
                    for f in self._scan_files(f"**/{name_pat}{ext}", max_files=50):
                        if f not in seen:
                            files.append(f)
                            seen.add(f)
            # Then add remaining files up to cap
            for ext in exts:
                for f in self._scan_files(f"**/*{ext}", max_files=300):
                    if f not in seen:
                        files.append(f)
                        seen.add(f)
                    if len(files) >= 500:
                        break
                if len(files) >= 500:
                    break
            if files:
                detected_langs[lang] = files

        if not detected_langs:
            return ToolResult(tool=self.name, status=ToolStatus.SKIPPED)

        # For each detected language, check if any file has shutdown handling
        for lang, files in detected_langs.items():
            _, patterns = LANG_PATTERNS[lang]
            handler_found = False

            for src_file in files:
                try:
                    content = src_file.read_text(errors="replace")
                except OSError:
                    continue

                for pattern in patterns:
                    if pattern.search(content):
                        handler_found = True
                        break
                if handler_found:
                    break

            if not handler_found:
                # Determine the main entry point hint
                entry_hints = {
                    "python": "main.py, app.py, or manage.py",
                    "node": "server.js, index.js, or app.ts",
                    "go": "main.go",
                    "ruby": "config.ru or app.rb",
                    "java": "Application.java or Main.java",
                }
                fix_hints = {
                    "python": "Add signal.signal(signal.SIGTERM, handler) in your entry point",
                    "node": "Add process.on('SIGTERM', () => server.close()) in your entry point",
                    "go": "Add signal.Notify(quit, syscall.SIGTERM) and server.Shutdown(ctx)",
                    "ruby": "Add Signal.trap('TERM') { server.stop } in your entry point",
                    "java": "Add Runtime.getRuntime().addShutdownHook(new Thread(...))",
                }

                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.HIGH,
                    category=Category.PROCESS,
                    file=entry_hints.get(lang, "."),
                    rule_id=f"no-graceful-shutdown-{lang}",
                    rule_name=f"Missing Graceful Shutdown ({lang})",
                    message=(
                        f"No SIGTERM/SIGINT signal handlers detected in {lang} source files. "
                        f"Without graceful shutdown handling, in-flight requests will be dropped "
                        f"during deployments and container restarts."
                    ),
                    blocks_deploy=True,
                    effort=Effort.MEDIUM,
                    fix_hint=fix_hints.get(lang, "Add SIGTERM/SIGINT signal handlers"),
                ))

        # Also check if there is a Dockerfile with STOPSIGNAL
        dockerfile = target / "Dockerfile"
        if dockerfile.exists():
            content = self._read_file(dockerfile)
            if "STOPSIGNAL" not in content:
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.LOW,
                    category=Category.PROCESS,
                    file="Dockerfile",
                    rule_id="no-stopsignal",
                    rule_name="Missing STOPSIGNAL in Dockerfile",
                    message=(
                        "Dockerfile does not set STOPSIGNAL. Docker defaults to SIGTERM, "
                        "but explicitly setting it documents the shutdown contract."
                    ),
                    blocks_deploy=False,
                    effort=Effort.TRIVIAL,
                    fix_hint="Add STOPSIGNAL SIGTERM to Dockerfile",
                ))

        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=findings)

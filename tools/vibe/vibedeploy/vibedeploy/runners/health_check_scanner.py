"""health_check_scanner — custom runner checking for health check endpoints."""

from __future__ import annotations

import re
from pathlib import Path

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner

# Patterns that indicate a health check endpoint
HEALTH_ROUTE_PATTERNS = [
    re.compile(r"""['"/](health|healthz|readiness|liveness|ready|alive|ping|status)['"\s,)\]]""", re.IGNORECASE),
    re.compile(r"""@app\.(get|route)\s*\(\s*['"]/(health|healthz|readiness|liveness)""", re.IGNORECASE),
    re.compile(r"""router\.(get|route)\s*\(\s*['"]/(health|healthz|readiness|liveness)""", re.IGNORECASE),
    re.compile(r"""app\.(get|use)\s*\(\s*['"]/(health|healthz|readiness|liveness)""", re.IGNORECASE),
    re.compile(r"""path\s*\(\s*['"]/?health""", re.IGNORECASE),
    re.compile(r"""endpoint\s*=\s*['"]/?health""", re.IGNORECASE),
]

DOCKERFILE_HEALTHCHECK = re.compile(r"^\s*HEALTHCHECK\s+", re.MULTILINE)

SOURCE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rb", ".java",
    ".rs", ".cs", ".php", ".mjs", ".cjs",
}


class HealthCheckScannerRunner(AsyncToolRunner):
    name = "health_check_scanner"

    def should_run(self) -> bool:
        for ext in SOURCE_EXTENSIONS:
            if self._scan_files(f"**/*{ext}", max_files=1):
                return True
        self.skip_reason = "no source files found"
        return False

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        findings: list[Finding] = []
        target = Path(self.target)

        # Scan source files for health check routes
        # Prioritise route/server files first (health endpoints are almost always there)
        health_endpoint_found = False

        # Phase 1: check likely files first (fast path)
        _LIKELY_NAMES = (
            "*route*", "*server*", "*app*", "*health*", "*index*",
            "*main*", "*api*", "*middleware*",
        )
        likely_files: list[Path] = []
        for name_pat in _LIKELY_NAMES:
            for ext in SOURCE_EXTENSIONS:
                likely_files.extend(self._scan_files(f"**/{name_pat}{ext}", max_files=200))

        for src_file in likely_files:
            try:
                content = src_file.read_text(errors="replace")
            except OSError:
                continue
            for pattern in HEALTH_ROUTE_PATTERNS:
                if pattern.search(content):
                    health_endpoint_found = True
                    break
            if health_endpoint_found:
                break

        # Phase 2: if not found, scan remaining files (capped)
        if not health_endpoint_found:
            likely_set = set(likely_files)
            remaining: list[Path] = []
            for ext in SOURCE_EXTENSIONS:
                for f in self._scan_files(f"**/*{ext}", max_files=500):
                    if f not in likely_set:
                        remaining.append(f)
                    if len(remaining) >= 500:
                        break
                if len(remaining) >= 500:
                    break

            for src_file in remaining:
                try:
                    content = src_file.read_text(errors="replace")
                except OSError:
                    continue
                for pattern in HEALTH_ROUTE_PATTERNS:
                    if pattern.search(content):
                        health_endpoint_found = True
                        break
                if health_endpoint_found:
                    break

        if not health_endpoint_found:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.HIGH,
                category=Category.PROCESS,
                file=".",
                rule_id="no-health-endpoint",
                rule_name="Missing Health Check Endpoint",
                message=(
                    "No health check endpoint (/health, /healthz, /readiness, /liveness) "
                    "detected. Load balancers and orchestrators need a health endpoint "
                    "to verify the application is running."
                ),
                blocks_deploy=True,
                effort=Effort.LOW,
                fix_hint="Add a GET /health or /healthz endpoint that returns 200 OK",
            ))

        # Check Dockerfile for HEALTHCHECK instruction
        dockerfile = target / "Dockerfile"
        if dockerfile.exists():
            content = self._read_file(dockerfile)
            if not DOCKERFILE_HEALTHCHECK.search(content):
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.MEDIUM,
                    category=Category.PROCESS,
                    file="Dockerfile",
                    rule_id="no-dockerfile-healthcheck",
                    rule_name="Missing Dockerfile HEALTHCHECK",
                    message=(
                        "Dockerfile does not include a HEALTHCHECK instruction. "
                        "Docker and orchestrators use this to determine container health."
                    ),
                    blocks_deploy=False,
                    effort=Effort.LOW,
                    fix_hint='Add HEALTHCHECK CMD ["curl", "-f", "http://localhost:PORT/health"] to Dockerfile',
                    docs_url="https://docs.docker.com/reference/dockerfile/#healthcheck",
                ))

        # Check docker-compose for healthcheck
        for compose_name in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
            compose_file = target / compose_name
            if compose_file.exists():
                content = self._read_file(compose_file)
                if "healthcheck:" not in content:
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.LOW,
                        category=Category.PROCESS,
                        file=compose_name,
                        rule_id="no-compose-healthcheck",
                        rule_name="Missing Compose Healthcheck",
                        message=f"{compose_name} does not define healthcheck for services",
                        blocks_deploy=False,
                        effort=Effort.LOW,
                        fix_hint="Add healthcheck section to service definitions in compose file",
                    ))

        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=findings)

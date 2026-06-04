"""otel_checker — custom runner checking OpenTelemetry configuration."""

from __future__ import annotations

import re
from pathlib import Path

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner

# OTel environment variable patterns
OTEL_ENV_VARS = [
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_SERVICE_NAME",
    "OTEL_TRACES_EXPORTER",
    "OTEL_METRICS_EXPORTER",
    "OTEL_RESOURCE_ATTRIBUTES",
]

# OTel config file patterns
OTEL_CONFIG_FILES = [
    "otel-collector-config.yaml",
    "otel-collector-config.yml",
    "otel-config.yaml",
    "otel-config.yml",
    "collector-config.yaml",
    "opentelemetry-config.yaml",
]

# Source code patterns indicating OTel setup
OTEL_SOURCE_PATTERNS = [
    re.compile(r"""opentelemetry""", re.IGNORECASE),
    re.compile(r"""@opentelemetry/"""),
    re.compile(r"""from\s+opentelemetry"""),
    re.compile(r"""import\s+.*opentelemetry"""),
    re.compile(r"""TracerProvider|MeterProvider"""),
    re.compile(r"""otel\.trace|otel\.metrics"""),
    re.compile(r"""OTLPTraceExporter|OTLPMetricExporter"""),
    re.compile(r"""opentelemetry-instrumentation"""),
]

# Alternative observability patterns (Datadog, New Relic, etc.)
ALT_OBSERVABILITY_PATTERNS = [
    re.compile(r"""datadog|dd-trace""", re.IGNORECASE),
    re.compile(r"""newrelic|new_relic""", re.IGNORECASE),
    re.compile(r"""elastic-apm|elasticapm""", re.IGNORECASE),
    re.compile(r"""jaeger""", re.IGNORECASE),
    re.compile(r"""zipkin""", re.IGNORECASE),
    re.compile(r"""prometheus""", re.IGNORECASE),
    re.compile(r"""grafana""", re.IGNORECASE),
    re.compile(r"""honeycomb""", re.IGNORECASE),
    re.compile(r"""lightstep""", re.IGNORECASE),
]


class OtelCheckerRunner(AsyncToolRunner):
    name = "otel_checker"

    def should_run(self) -> bool:
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        findings: list[Finding] = []
        target = Path(self.target)

        otel_found = False
        alt_observability_found = False

        # Check for OTel config files
        for config_name in OTEL_CONFIG_FILES:
            if (target / config_name).exists():
                otel_found = True
                break

        # Check env files for OTel vars
        if not otel_found:
            for env_name in (".env", ".env.example", ".env.production"):
                env_path = target / env_name
                if env_path.exists():
                    content = self._read_file(env_path)
                    for var in OTEL_ENV_VARS:
                        if var in content:
                            otel_found = True
                            break
                if otel_found:
                    break

        # Check docker-compose for OTel collector service
        if not otel_found:
            for compose_name in ("docker-compose.yml", "docker-compose.yaml", "compose.yml"):
                compose_path = target / compose_name
                if compose_path.exists():
                    content = self._read_file(compose_path)
                    if "otel" in content.lower() or "opentelemetry" in content.lower():
                        otel_found = True
                        break

        # Check package files for OTel dependencies
        if not otel_found:
            for pkg_file in ("package.json", "requirements.txt", "pyproject.toml", "go.mod", "Gemfile"):
                pkg_path = target / pkg_file
                if pkg_path.exists():
                    content = self._read_file(pkg_path)
                    for pattern in OTEL_SOURCE_PATTERNS:
                        if pattern.search(content):
                            otel_found = True
                            break
                    # Also check for alt observability
                    if not alt_observability_found:
                        for pattern in ALT_OBSERVABILITY_PATTERNS:
                            if pattern.search(content):
                                alt_observability_found = True
                                break
                if otel_found:
                    break

        # Scan source files if still not found
        if not otel_found and not alt_observability_found:
            source_exts = ("**/*.py", "**/*.js", "**/*.ts", "**/*.go", "**/*.rb", "**/*.java")
            for ext_pattern in source_exts:
                for src_file in self._scan_files(ext_pattern):
                    try:
                        content = src_file.read_text(errors="replace")
                    except OSError:
                        continue
                    for pattern in OTEL_SOURCE_PATTERNS:
                        if pattern.search(content):
                            otel_found = True
                            break
                    if not otel_found and not alt_observability_found:
                        for pattern in ALT_OBSERVABILITY_PATTERNS:
                            if pattern.search(content):
                                alt_observability_found = True
                                break
                    if otel_found:
                        break
                if otel_found:
                    break

        if not otel_found and not alt_observability_found:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.MEDIUM,
                category=Category.LOGGING,
                file=".",
                rule_id="no-observability",
                rule_name="No Observability Configuration",
                message=(
                    "No OpenTelemetry or alternative observability setup detected. "
                    "Production applications need distributed tracing and metrics "
                    "to diagnose performance issues and outages."
                ),
                blocks_deploy=False,
                effort=Effort.MEDIUM,
                fix_hint=(
                    "Add OpenTelemetry SDK and configure an OTLP exporter. "
                    "Set OTEL_SERVICE_NAME and OTEL_EXPORTER_OTLP_ENDPOINT."
                ),
                docs_url="https://opentelemetry.io/docs/getting-started/",
            ))

        # If OTel is found, check for completeness
        if otel_found:
            # Check for service name
            has_service_name = False
            for env_name in (".env", ".env.example", ".env.production"):
                env_path = target / env_name
                if env_path.exists():
                    content = self._read_file(env_path)
                    if "OTEL_SERVICE_NAME" in content:
                        has_service_name = True
                        break

            if not has_service_name:
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.LOW,
                    category=Category.LOGGING,
                    file=".env",
                    rule_id="otel-no-service-name",
                    rule_name="Missing OTEL_SERVICE_NAME",
                    message=(
                        "OTEL_SERVICE_NAME is not set. Without a service name, "
                        "traces and metrics will be harder to identify."
                    ),
                    blocks_deploy=False,
                    effort=Effort.TRIVIAL,
                    fix_hint="Set OTEL_SERVICE_NAME=your-service-name in environment",
                ))

        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=findings)

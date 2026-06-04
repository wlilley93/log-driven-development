"""docker_bench runner — Dockerfile security best practices checker.

Custom runner that statically analyses Dockerfiles for common security issues
such as running as root, using the 'latest' tag, exposing all ports, and other
anti-patterns. Does not require Docker Bench for Security to be installed --
performs checks directly on the Dockerfile content.
"""

from __future__ import annotations

import re
from pathlib import Path

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner


class DockerBenchRunner(AsyncToolRunner):
    name = "docker_bench"
    requires_docker = True

    def should_run(self) -> bool:
        if not self._file_exists("Dockerfile", "docker-compose.yml", "docker-compose.yaml"):
            self.skip_reason = "no Dockerfile found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        dockerfiles = self._scan_files("Dockerfile", "Dockerfile.*", "*.Dockerfile")
        if not dockerfiles:
            return ToolResult(tool=self.name, status=ToolStatus.SKIPPED)

        all_findings: list[Finding] = []

        for dockerfile in dockerfiles:
            content = self._read_file(dockerfile)
            if not content:
                continue
            rel_path = str(dockerfile.relative_to(self.target))
            all_findings.extend(self._check_dockerfile(content, rel_path))

        # Also check docker-compose files
        compose_files = self._scan_files("docker-compose.yml", "docker-compose.yaml", "docker-compose.*.yml")
        for compose_file in compose_files:
            content = self._read_file(compose_file)
            if not content:
                continue
            rel_path = str(compose_file.relative_to(self.target))
            all_findings.extend(self._check_compose(content, rel_path))

        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=all_findings)

    def _check_dockerfile(self, content: str, file_path: str) -> list[Finding]:
        """Check a Dockerfile for common security issues."""
        findings: list[Finding] = []
        lines = content.split("\n")

        has_user_instruction = False
        has_healthcheck = False
        uses_latest_tag = False
        uses_add = False
        exposes_all_ports = False
        uses_sudo = False
        uses_curl_pipe_bash = False
        stores_secrets = False

        for i, line in enumerate(lines, start=1):
            stripped = line.strip()
            upper = stripped.upper()

            # Skip comments and empty lines
            if stripped.startswith("#") or not stripped:
                continue

            # Check for USER instruction
            if upper.startswith("USER "):
                user_val = stripped[5:].strip()
                if user_val and user_val.lower() not in ("root", "0"):
                    has_user_instruction = True

            # Check for HEALTHCHECK
            if upper.startswith("HEALTHCHECK "):
                has_healthcheck = True

            # Check FROM with :latest or no tag
            if upper.startswith("FROM "):
                image_ref = stripped[5:].strip().split()[0] if stripped[5:].strip() else ""
                # Remove AS alias
                image_ref = image_ref.split(" ")[0]
                if image_ref and ":" not in image_ref and image_ref.lower() != "scratch":
                    uses_latest_tag = True
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.MEDIUM,
                        category=Category.DOCKER,
                        file=file_path,
                        line=i,
                        rule_id="db-no-tag",
                        rule_name="No Image Tag",
                        message=f"Base image '{image_ref}' has no tag, defaults to 'latest'",
                        effort=Effort.TRIVIAL,
                        fix_hint=f"Pin {image_ref} to a specific version tag (e.g., {image_ref}:22.04)",
                    ))
                elif ":latest" in image_ref.lower():
                    uses_latest_tag = True
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.MEDIUM,
                        category=Category.DOCKER,
                        file=file_path,
                        line=i,
                        rule_id="db-latest-tag",
                        rule_name="Latest Tag Used",
                        message=f"Base image uses ':latest' tag which is not reproducible",
                        effort=Effort.TRIVIAL,
                        fix_hint="Pin to a specific version tag for reproducible builds",
                    ))

            # Check for ADD instead of COPY
            if upper.startswith("ADD ") and not any(kw in stripped for kw in ("http://", "https://", ".tar", ".gz")):
                uses_add = True
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.LOW,
                    category=Category.DOCKER,
                    file=file_path,
                    line=i,
                    rule_id="db-use-copy",
                    rule_name="Use COPY Instead of ADD",
                    message="ADD used where COPY would suffice. ADD has implicit tar extraction and URL fetch which may be unexpected.",
                    effort=Effort.TRIVIAL,
                    fix_hint="Replace ADD with COPY unless you need tar auto-extraction or URL fetching",
                ))

            # Check for EXPOSE with broad ranges
            if upper.startswith("EXPOSE "):
                ports_str = stripped[7:].strip()
                if "0-65535" in ports_str or "0:65535" in ports_str:
                    exposes_all_ports = True
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.HIGH,
                        category=Category.DOCKER,
                        file=file_path,
                        line=i,
                        rule_id="db-expose-all",
                        rule_name="All Ports Exposed",
                        message="Exposing all ports dramatically increases attack surface",
                        blocks_deploy=True,
                        effort=Effort.TRIVIAL,
                        fix_hint="Only expose the specific ports your application needs",
                    ))

            # Check for sudo usage in RUN
            if upper.startswith("RUN ") and "sudo" in stripped.lower():
                uses_sudo = True
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.LOW,
                    category=Category.DOCKER,
                    file=file_path,
                    line=i,
                    rule_id="db-sudo-usage",
                    rule_name="Sudo in Dockerfile",
                    message="Using sudo in a Dockerfile is unnecessary since commands already run as root by default",
                    effort=Effort.TRIVIAL,
                    fix_hint="Remove sudo; use USER instruction to switch users instead",
                ))

            # Check for curl | bash pattern
            if upper.startswith("RUN ") and re.search(r"curl\s.*\|\s*(bash|sh)", stripped, re.IGNORECASE):
                uses_curl_pipe_bash = True
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.HIGH,
                    category=Category.DOCKER,
                    file=file_path,
                    line=i,
                    rule_id="db-curl-pipe-bash",
                    rule_name="Curl Pipe to Shell",
                    message="Piping curl output to shell is a security risk — content can change between fetches",
                    blocks_deploy=False,
                    effort=Effort.LOW,
                    fix_hint="Download the script first, verify its checksum, then execute it",
                ))

            # Check for secret-like ENV values
            if upper.startswith("ENV "):
                env_content = stripped[4:].strip()
                secret_patterns = re.findall(
                    r'(PASSWORD|SECRET|TOKEN|API_KEY|PRIVATE_KEY)\s*=\s*["\']?(\S+)',
                    env_content,
                    re.IGNORECASE,
                )
                for key_name, value in secret_patterns:
                    if value and value not in ('""', "''", "${" + key_name + "}", "$" + key_name):
                        stores_secrets = True
                        findings.append(Finding(
                            tool=self.name,
                            severity=Severity.CRITICAL,
                            category=Category.DOCKER,
                            file=file_path,
                            line=i,
                            rule_id="db-hardcoded-secret",
                            rule_name="Hardcoded Secret in Dockerfile",
                            message=f"Potential hardcoded secret in ENV: {key_name}",
                            blocks_deploy=True,
                            effort=Effort.LOW,
                            fix_hint="Use build args, runtime environment variables, or a secrets manager instead of hardcoding secrets",
                        ))

        # Check if no USER instruction present (running as root)
        if not has_user_instruction:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.HIGH,
                category=Category.DOCKER,
                file=file_path,
                rule_id="db-running-as-root",
                rule_name="Container Runs as Root",
                message="No USER instruction found. Container will run as root, which is a security risk.",
                blocks_deploy=True,
                effort=Effort.LOW,
                fix_hint="Add 'USER nonroot' or 'USER 1000' instruction after installing dependencies",
            ))

        # Check if no HEALTHCHECK
        if not has_healthcheck:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.LOW,
                category=Category.DOCKER,
                file=file_path,
                rule_id="db-no-healthcheck",
                rule_name="No HEALTHCHECK Instruction",
                message="No HEALTHCHECK instruction found. Orchestrators cannot determine container health.",
                effort=Effort.TRIVIAL,
                fix_hint="Add a HEALTHCHECK instruction (e.g., HEALTHCHECK CMD curl -f http://localhost/ || exit 1)",
            ))

        return findings

    def _check_compose(self, content: str, file_path: str) -> list[Finding]:
        """Check a docker-compose file for common security issues."""
        findings: list[Finding] = []

        # Check for privileged mode
        for i, line in enumerate(content.split("\n"), start=1):
            stripped = line.strip()

            if "privileged: true" in stripped or "privileged:true" in stripped:
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.CRITICAL,
                    category=Category.DOCKER,
                    file=file_path,
                    line=i,
                    rule_id="db-privileged-mode",
                    rule_name="Privileged Container",
                    message="Container running in privileged mode grants full host access",
                    blocks_deploy=True,
                    effort=Effort.LOW,
                    fix_hint="Remove 'privileged: true' and use specific capabilities instead (cap_add)",
                ))

            # Check for network_mode: host
            if "network_mode:" in stripped and "host" in stripped:
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.MEDIUM,
                    category=Category.DOCKER,
                    file=file_path,
                    line=i,
                    rule_id="db-host-network",
                    rule_name="Host Network Mode",
                    message="Container uses host network mode, bypassing network isolation",
                    effort=Effort.LOW,
                    fix_hint="Use bridge networking or a custom network instead of host mode",
                ))

            # Check for pid: host
            if re.match(r'^\s*pid\s*:\s*["\']?host["\']?\s*$', stripped):
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.HIGH,
                    category=Category.DOCKER,
                    file=file_path,
                    line=i,
                    rule_id="db-host-pid",
                    rule_name="Host PID Namespace",
                    message="Container shares the host PID namespace, which allows process inspection and signalling",
                    blocks_deploy=True,
                    effort=Effort.LOW,
                    fix_hint="Remove 'pid: host' unless absolutely required for debugging",
                ))

        return findings

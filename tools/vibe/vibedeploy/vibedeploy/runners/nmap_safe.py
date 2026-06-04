"""nmap_safe runner — safe limited port scanning for common web ports."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner

# Only scan common web ports — keep the scan safe and fast
COMMON_WEB_PORTS = "80,443,8080,8443"

# Expected open ports for a web application
EXPECTED_PORTS = {80, 443, 8080, 8443}

# Potentially concerning ports if unexpectedly open
CONCERNING_PORTS = {
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    25: "SMTP",
    53: "DNS",
    110: "POP3",
    135: "MSRPC",
    139: "NetBIOS",
    143: "IMAP",
    445: "SMB",
    1433: "MSSQL",
    1521: "Oracle",
    3306: "MySQL",
    3389: "RDP",
    5432: "PostgreSQL",
    5900: "VNC",
    6379: "Redis",
    9200: "Elasticsearch",
    27017: "MongoDB",
}


class NmapSafeRunner(AsyncToolRunner):
    name = "nmap_safe"
    requires_url = True

    @property
    def bin_path(self) -> str:
        from vibedeploy.installer import get_tool_bin
        path = get_tool_bin(self.name)
        if path == self.name:
            return "nmap"
        return path

    def should_run(self) -> bool:
        if not self.config.url:
            self.skip_reason = "requires --url"
            return False
        if not self._tool_exists():
            self.skip_reason = "nmap not installed"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        url = self.config.url
        if not url:
            return self._make_error_result("No URL configured")

        hostname = self._extract_hostname(url)
        if not hostname:
            return self._make_error_result(f"Could not extract hostname from URL: {url}")

        # Safe nmap scan: only common web ports, no aggressive probing
        # -sT: TCP connect scan (not SYN, doesn't require root)
        # -p: specific ports only
        # --open: only show open ports
        # -T3: normal timing (not aggressive)
        # --max-retries 2: limit retries
        cmd = [
            self.bin_path,
            "-sT",
            "-p", COMMON_WEB_PORTS,
            "--open",
            "-T3",
            "--max-retries", "2",
            "--host-timeout", "30s",
            hostname,
        ]

        try:
            result = self._exec(cmd, timeout=60)
        except Exception as e:
            return self._make_error_result(f"nmap execution failed: {e}")

        findings = self._parse_output(result.stdout, result.stderr, hostname)

        status = ToolStatus.SUCCESS if result.returncode == 0 else ToolStatus.PARTIAL

        return ToolResult(tool=self.name, status=status, findings=findings)

    def _parse_output(
        self, stdout: str, stderr: str, hostname: str
    ) -> list[Finding]:
        findings: list[Finding] = []
        output = stdout + "\n" + stderr

        # Parse open ports from nmap output
        # Format: PORT/PROTOCOL STATE SERVICE
        port_pattern = re.compile(r"""(\d+)/(\w+)\s+(open|filtered)\s+(\S+)""")
        open_ports: list[tuple[int, str, str]] = []

        for match in port_pattern.finditer(output):
            port = int(match.group(1))
            state = match.group(3)
            service = match.group(4)
            if state == "open":
                open_ports.append((port, state, service))

        # Check for unexpected open ports
        for port, state, service in open_ports:
            if port in CONCERNING_PORTS:
                port_desc = CONCERNING_PORTS[port]
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.MEDIUM,
                    category=Category.DNS_NETWORK,
                    file=".",
                    rule_id=f"nmap-unexpected-port-{port}",
                    rule_name=f"Unexpected Open Port: {port} ({port_desc})",
                    message=(
                        f"Port {port} ({port_desc}/{service}) is open on {hostname}. "
                        f"This port is typically not needed for web applications and "
                        f"increases the attack surface."
                    ),
                    blocks_deploy=False,
                    effort=Effort.LOW,
                    fix_hint=f"Close port {port} if not needed, or restrict access via firewall rules",
                ))

        # Check if no web ports are open
        web_ports_open = [p for p, _, _ in open_ports if p in EXPECTED_PORTS]
        if not web_ports_open and open_ports:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.HIGH,
                category=Category.DNS_NETWORK,
                file=".",
                rule_id="nmap-no-web-ports",
                rule_name="No Standard Web Ports Open",
                message=(
                    f"No standard web ports (80, 443, 8080, 8443) are open on {hostname}. "
                    f"The web server may not be running or is on a non-standard port."
                ),
                blocks_deploy=False,
                effort=Effort.MEDIUM,
                fix_hint="Verify the web server is running and listening on expected ports",
            ))

        # Check if only HTTP (no HTTPS)
        has_80 = any(p == 80 for p, _, _ in open_ports)
        has_443 = any(p == 443 for p, _, _ in open_ports)
        if has_80 and not has_443:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.HIGH,
                category=Category.DNS_NETWORK,
                file=".",
                rule_id="nmap-no-https",
                rule_name="HTTPS Port Not Open",
                message=(
                    f"Port 80 (HTTP) is open but port 443 (HTTPS) is not on {hostname}. "
                    f"TLS encryption is required for production."
                ),
                blocks_deploy=False,
                effort=Effort.MEDIUM,
                fix_hint="Configure TLS certificate and enable HTTPS on port 443",
            ))

        # Check if host is down
        if "Host seems down" in output or "0 hosts up" in output:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.CRITICAL,
                category=Category.DNS_NETWORK,
                file=".",
                rule_id="nmap-host-down",
                rule_name="Host Appears Down",
                message=f"Host {hostname} appears to be down or unreachable",
                blocks_deploy=True,
                effort=Effort.HIGH,
                fix_hint="Verify the server is running and accessible from the network",
            ))

        return findings

    @staticmethod
    def _extract_hostname(url: str) -> str | None:
        """Extract hostname from URL."""
        try:
            parsed = urlparse(url if "://" in url else f"https://{url}")
            return parsed.hostname
        except Exception:
            return None

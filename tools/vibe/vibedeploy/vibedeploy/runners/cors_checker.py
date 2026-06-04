"""cors_checker — custom runner checking CORS configuration via preflight requests."""

from __future__ import annotations

import urllib.request
import urllib.error
from urllib.parse import urlparse

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner

# Common API paths to probe for CORS misconfigurations
_API_PATHS = [
    "/",
    "/api",
    "/api/v1",
    "/api/v2",
    "/graphql",
    "/auth",
    "/auth/login",
    "/api/auth",
    "/api/users",
    "/api/health",
    "/webhook",
    "/ws",
]

# Suspicious origins to test against
_TEST_ORIGINS = [
    "https://evil.com",
    "https://attacker.example.com",
    "null",
]


class CorsCheckerRunner(AsyncToolRunner):
    name = "cors_checker"
    requires_url = True

    def should_run(self) -> bool:
        if not self.config.url:
            self.skip_reason = "requires --url"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        findings: list[Finding] = []
        base_url = self.config.url.rstrip("/")
        parsed = urlparse(base_url)
        is_production = self._is_production(parsed.hostname or "")

        for path in _API_PATHS:
            url = f"{base_url}{path}"

            # Test 1: Simple CORS check — does the server reflect any origin?
            for test_origin in _TEST_ORIGINS:
                headers = self._send_preflight(url, test_origin)
                if headers is None:
                    continue

                acao = headers.get("Access-Control-Allow-Origin", "")
                acac = headers.get("Access-Control-Allow-Credentials", "").lower()

                # Wildcard origin
                if acao == "*":
                    sev = Severity.HIGH if is_production else Severity.MEDIUM
                    blocks = is_production
                    findings.append(Finding(
                        tool=self.name,
                        severity=sev,
                        category=Category.CORS_API,
                        file=url,
                        rule_id="cors-wildcard-origin",
                        rule_name="Wildcard CORS Origin",
                        message=f"CORS allows wildcard origin (*) on {path}",
                        blocks_deploy=blocks,
                        effort=Effort.LOW,
                        fix_hint="Restrict Access-Control-Allow-Origin to specific trusted domains",
                    ))

                    # Wildcard + credentials is particularly dangerous
                    if acac == "true":
                        findings.append(Finding(
                            tool=self.name,
                            severity=Severity.CRITICAL,
                            category=Category.CORS_API,
                            file=url,
                            rule_id="cors-wildcard-credentials",
                            rule_name="CORS Wildcard With Credentials",
                            message=f"CORS allows wildcard origin with credentials on {path} — cookie theft possible",
                            blocks_deploy=True,
                            effort=Effort.LOW,
                            fix_hint="Never combine Access-Control-Allow-Origin: * with Allow-Credentials: true",
                        ))
                    break  # No need to test more origins on this path

                # Origin reflection — server echoes back attacker origin
                if acao == test_origin and test_origin != "null":
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.HIGH,
                        category=Category.CORS_API,
                        file=url,
                        rule_id="cors-origin-reflection",
                        rule_name="CORS Origin Reflection",
                        message=f"CORS reflects arbitrary origin '{test_origin}' on {path}",
                        blocks_deploy=is_production,
                        effort=Effort.LOW,
                        fix_hint="Validate CORS origins against an allowlist instead of reflecting the Origin header",
                    ))

                    if acac == "true":
                        findings.append(Finding(
                            tool=self.name,
                            severity=Severity.CRITICAL,
                            category=Category.CORS_API,
                            file=url,
                            rule_id="cors-reflection-credentials",
                            rule_name="CORS Reflection With Credentials",
                            message=f"CORS reflects origin with credentials on {path} — full account takeover possible",
                            blocks_deploy=True,
                            effort=Effort.LOW,
                            fix_hint="Implement a strict CORS origin allowlist and never reflect untrusted origins",
                        ))
                    break

                # Null origin accepted
                if acao == "null" and test_origin == "null":
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.MEDIUM,
                        category=Category.CORS_API,
                        file=url,
                        rule_id="cors-null-origin",
                        rule_name="CORS Accepts Null Origin",
                        message=f"CORS accepts null origin on {path} — sandbox bypass possible",
                        blocks_deploy=False,
                        effort=Effort.TRIVIAL,
                        fix_hint="Do not allow 'null' as a valid CORS origin",
                    ))

            # Test 2: Check for overly permissive methods
            headers = self._send_preflight(url, f"https://{parsed.hostname}", method="DELETE")
            if headers:
                allowed_methods = headers.get("Access-Control-Allow-Methods", "")
                dangerous_methods = {"DELETE", "PUT", "PATCH"}
                exposed = {m.strip().upper() for m in allowed_methods.split(",") if m.strip()}
                if dangerous_methods & exposed:
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.LOW,
                        category=Category.CORS_API,
                        file=url,
                        rule_id="cors-dangerous-methods",
                        rule_name="CORS Allows Dangerous Methods",
                        message=f"CORS allows {', '.join(dangerous_methods & exposed)} on {path}",
                        blocks_deploy=False,
                        effort=Effort.TRIVIAL,
                        fix_hint="Restrict Access-Control-Allow-Methods to only required HTTP methods",
                    ))

        status = ToolStatus.SUCCESS
        return ToolResult(tool=self.name, status=status, findings=findings)

    def _send_preflight(
        self, url: str, origin: str, method: str = "GET"
    ) -> dict[str, str] | None:
        """Send an OPTIONS preflight request and return response headers."""
        try:
            req = urllib.request.Request(url, method="OPTIONS")
            req.add_header("Origin", origin)
            req.add_header("Access-Control-Request-Method", method)
            req.add_header("Access-Control-Request-Headers", "Content-Type, Authorization")
            req.add_header("User-Agent", "vibedeploy-cors-checker/1.0")

            with urllib.request.urlopen(req, timeout=10) as resp:
                return dict(resp.headers)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError):
            pass

        # Also try a simple GET with Origin header (not all servers respond to OPTIONS)
        try:
            req = urllib.request.Request(url, method="GET")
            req.add_header("Origin", origin)
            req.add_header("User-Agent", "vibedeploy-cors-checker/1.0")

            with urllib.request.urlopen(req, timeout=10) as resp:
                return dict(resp.headers)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError):
            pass

        return None

    @staticmethod
    def _is_production(hostname: str) -> bool:
        """Heuristic to determine if the target is a production environment."""
        dev_indicators = ("localhost", "127.0.0.1", "0.0.0.0", "dev.", "staging.", "test.", "local")
        return not any(ind in hostname.lower() for ind in dev_indicators)

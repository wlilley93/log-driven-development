"""Runner for h2spec — HTTP/2 compliance validation."""

from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.h2spec import H2specNormaliser
from viberapid.runners.base import AsyncToolRunner


class H2specRunner(AsyncToolRunner):
    """Run h2spec against a URL to validate HTTP/2 protocol compliance."""

    name = "h2spec"
    requires_url = True

    def should_run(self) -> bool:
        if not super().should_run():
            return False
        if not self._tool_exists():
            self.skip_reason = "h2spec not found (install via viberapid install)"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        url = self.config.url
        tc = self.tool_config
        bin_path = self.bin_path

        # Parse URL to extract host and port
        parsed = urlparse(url)
        host = parsed.hostname or "localhost"
        port = parsed.port
        is_tls = parsed.scheme == "https"

        if port is None:
            port = 443 if is_tls else 80

        cmd = [
            bin_path,
            "-h", host,
            "-p", str(port),
            "--json",
        ]

        if is_tls:
            cmd.append("--tls")

            # Optional: skip TLS verification
            if tc.get("insecure", False):
                cmd.append("--insecure")

        # Optional: run only specific sections
        sections = tc.get("sections")
        if sections and isinstance(sections, list):
            for section in sections:
                cmd.extend(["-s", str(section)])

        # Optional: timeout per test
        test_timeout = tc.get("timeout")
        if test_timeout and isinstance(test_timeout, (int, float)):
            cmd.extend(["--timeout", str(int(test_timeout))])

        # Optional: max header list size
        max_header = tc.get("max_header_list_size")
        if max_header and isinstance(max_header, int):
            cmd.extend(["--max-header-list-size", str(max_header)])

        try:
            result = self._exec(cmd, cwd="/tmp")

            # h2spec outputs JSON to stdout when --json is used
            raw_output = result.stdout.strip()
            if not raw_output:
                # h2spec may output results to stderr on connection failure
                stderr = result.stderr.strip()
                if "connection refused" in stderr.lower() or "dial tcp" in stderr.lower():
                    return self._make_error_result(
                        f"h2spec could not connect to {host}:{port}. "
                        f"Ensure the server supports HTTP/2."
                    )
                return self._make_error_result(
                    f"h2spec did not produce output. stderr: {stderr[:500]}"
                )

            try:
                data = json.loads(raw_output)
            except json.JSONDecodeError:
                # Fallback: try to parse plain text output
                return self._make_error_result(
                    f"h2spec output is not valid JSON. stdout: {raw_output[:500]}"
                )

            normaliser = H2specNormaliser()
            findings = normaliser.normalise(data)

            # Extract summary counts from the JSON
            total_tests = 0
            passed_tests = 0
            failed_tests = 0
            skipped_tests = 0

            for suite in data if isinstance(data, list) else [data]:
                if not isinstance(suite, dict):
                    continue
                total_tests += suite.get("testCount", 0)
                passed_tests += suite.get("passedCount", 0)
                failed_tests += suite.get("failedCount", 0)
                skipped_tests += suite.get("skippedCount", 0)

            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS if failed_tests == 0 else ToolStatus.PARTIAL,
                findings=findings,
                metrics={
                    "url": url,
                    "host": host,
                    "port": port,
                    "tls": is_tls,
                    "total_tests": total_tests,
                    "passed": passed_tests,
                    "failed": failed_tests,
                    "skipped": skipped_tests,
                },
            )

        except Exception as exc:
            return self._make_error_result(f"h2spec failed: {exc}")

"""Runner for webhint — web best practices, security headers, and compatibility checks."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.webhint import WebhintNormaliser
from viberapid.runners.base import AsyncToolRunner


class WebhintRunner(AsyncToolRunner):
    """Run webhint (hint) against a URL to check headers, caching, security, and compatibility."""

    name = "webhint"
    requires_url = True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        npx = self._npx_path()
        url = self.config.url

        # webhint outputs JSON to a file via --output
        with tempfile.TemporaryDirectory(prefix="viberapid-webhint-") as tmpdir:
            try:
                cmd = [
                    npx, "hint", url,
                    "--formatters", "json",
                    "--output", tmpdir,
                ]

                result = self._exec(cmd)

                # webhint writes JSON to <tmpdir>/<formatter-name>.json
                json_files = list(Path(tmpdir).glob("*.json"))
                if not json_files:
                    # webhint may also output to stdout
                    if result.stdout.strip():
                        try:
                            data = json.loads(result.stdout)
                        except json.JSONDecodeError:
                            return self._make_error_result(
                                f"webhint did not produce valid JSON. "
                                f"stderr: {result.stderr[:500]}"
                            )
                    else:
                        return self._make_error_result(
                            f"webhint did not produce output. "
                            f"stderr: {result.stderr[:500]}"
                        )
                else:
                    # Read the first JSON output file
                    with open(json_files[0]) as f:
                        data = json.load(f)

                # Ensure data is a list (webhint JSON formatter outputs an array)
                if isinstance(data, dict):
                    data = [data]

                normaliser = WebhintNormaliser()
                findings = normaliser.normalise(data)

                # Count problems by severity
                total_problems = sum(
                    len(entry.get("problems", []))
                    for entry in data
                    if isinstance(entry, dict)
                )

                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.SUCCESS,
                    findings=findings,
                    metrics={
                        "url": url,
                        "total_problems": total_problems,
                    },
                )

            except Exception as exc:
                return self._make_error_result(f"webhint failed: {exc}")

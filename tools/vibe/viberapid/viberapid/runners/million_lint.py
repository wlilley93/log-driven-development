"""Runner for million-lint — static analysis of React component rendering performance."""

from __future__ import annotations

import json

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.million_lint import MillionLintNormaliser
from viberapid.runners.base import AsyncToolRunner


class MillionLintRunner(AsyncToolRunner):
    """Run @million/lint to identify React components that could be optimised."""

    name = "million-lint"
    requires_node = True

    def should_run(self) -> bool:
        if not self._file_exists("package.json"):
            self.skip_reason = "no package.json found"
            return False

        # Check for React-related files
        has_react_files = bool(
            self._glob_files("*.jsx", "*.tsx")
        )
        if not has_react_files:
            self.skip_reason = "no .jsx or .tsx files found"
            return False

        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        npx = self._npx_path()

        cmd = [npx, "@million/lint"]

        result = self._exec(cmd, timeout=120)
        stderr = result.stderr.strip() if result.stderr else ""
        stdout = result.stdout.strip() if result.stdout else ""

        # million-lint may output JSON or structured text.
        # Try JSON parse first.
        data = None
        if stdout:
            try:
                data = json.loads(stdout)
            except json.JSONDecodeError:
                # Parse text output into a structured format
                data = self._parse_text_output(stdout)

        if data is None:
            # If million-lint produced no output, it may mean no issues found
            if result.returncode == 0:
                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.SUCCESS,
                    findings=[],
                    metrics={"components_analysed": 0, "issues_found": 0},
                )
            return self._make_error_result(
                f"million-lint failed. stderr: {stderr[:500]}"
            )

        normaliser = MillionLintNormaliser()
        findings = normaliser.normalise(data)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "issues_found": len(findings),
                "react_files": len(self._glob_files("*.jsx", "*.tsx")),
            },
        )

    def _parse_text_output(self, stdout: str) -> dict | None:
        """Parse million-lint text output into a structured format."""
        if not stdout:
            return None

        issues: list[dict] = []
        lines = stdout.splitlines()

        current_file = None
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # million-lint output often includes file paths with issues
            # Format varies but generally: file:line message
            if ":" in stripped and any(ext in stripped for ext in (".jsx", ".tsx", ".js", ".ts")):
                parts = stripped.split(":", 2)
                if len(parts) >= 2:
                    filepath = parts[0].strip()
                    rest = ":".join(parts[1:]).strip()

                    # Try to extract line number
                    line_no = None
                    message = rest
                    if rest and rest[0].isdigit():
                        num_parts = rest.split(" ", 1)
                        try:
                            line_no = int(num_parts[0].rstrip(":"))
                            message = num_parts[1] if len(num_parts) > 1 else rest
                        except ValueError:
                            pass

                    issues.append({
                        "file": filepath,
                        "line": line_no,
                        "message": message.strip(),
                    })
                    current_file = filepath

            elif current_file and stripped:
                # Continuation of previous issue message
                if issues:
                    issues[-1]["message"] += " " + stripped

        if not issues:
            return None

        return {"issues": issues}

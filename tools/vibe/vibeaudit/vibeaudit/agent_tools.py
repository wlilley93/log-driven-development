"""Tools available to the agentic scanner."""

from __future__ import annotations

import os
import re
from pathlib import Path

from vibeaudit.provider import ToolDefinition


def get_agent_tools() -> list[ToolDefinition]:
    """Return tool definitions for the agent."""
    return [
        ToolDefinition(
            name="read_file",
            description="Read a file's contents. Returns line-numbered content.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to scan root"},
                    "start_line": {"type": "integer", "description": "Start line (1-indexed, optional)"},
                    "end_line": {"type": "integer", "description": "End line (inclusive, optional)"},
                },
                "required": ["path"],
            },
        ),
        ToolDefinition(
            name="search_code",
            description="Search for a regex pattern across the codebase. Returns matching lines with file paths and line numbers.",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern to search for"},
                    "file_glob": {"type": "string", "description": "Glob pattern to filter files (e.g. '**/*.ts')"},
                    "max_results": {"type": "integer", "description": "Maximum results to return (default 20)"},
                },
                "required": ["pattern"],
            },
        ),
        ToolDefinition(
            name="list_files",
            description="List files in a directory.",
            parameters={
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Directory path relative to scan root"},
                    "pattern": {"type": "string", "description": "Glob pattern filter"},
                    "recursive": {"type": "boolean", "description": "Recurse into subdirectories (default true)"},
                },
                "required": ["directory"],
            },
        ),
        ToolDefinition(
            name="find_references",
            description="Find all usages of a symbol (function, variable, class) across the codebase.",
            parameters={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Symbol name to find references for"},
                    "file_glob": {"type": "string", "description": "Glob pattern to filter files"},
                },
                "required": ["symbol"],
            },
        ),
        ToolDefinition(
            name="get_route_middleware_chain",
            description="Trace the middleware/auth chain for an API route. Reads the route file and any middleware imports.",
            parameters={
                "type": "object",
                "properties": {
                    "route_path": {"type": "string", "description": "API route path (e.g. '/api/users/[id]') or file path"},
                },
                "required": ["route_path"],
            },
        ),
        ToolDefinition(
            name="report_finding",
            description="Submit a security finding. Call this when you've identified a vulnerability.",
            parameters={
                "type": "object",
                "properties": {
                    "vuln_class": {"type": "string", "description": "Vulnerability class (e.g. 'idor', 'auth_bypass')"},
                    "severity": {"type": "string", "enum": ["critical", "high", "medium", "low", "info"]},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "title": {"type": "string", "description": "Brief finding title"},
                    "description": {"type": "string", "description": "Detailed description"},
                    "attack_scenario": {"type": "string", "description": "Step-by-step attack scenario"},
                    "impact": {"type": "string", "description": "Impact if exploited"},
                    "remediation": {"type": "string", "description": "How to fix"},
                    "file_path": {"type": "string", "description": "Primary affected file"},
                    "start_line": {"type": "integer", "description": "Start line of affected code"},
                    "end_line": {"type": "integer", "description": "End line of affected code"},
                    "cwe_id": {"type": "string", "description": "CWE identifier"},
                },
                "required": ["vuln_class", "severity", "confidence", "title", "description", "file_path"],
            },
        ),
    ]


class ToolExecutor:
    """Execute agent tools with sandboxed file access."""

    def __init__(self, scan_root: Path):
        self.scan_root = scan_root.resolve()

    def execute(self, tool_name: str, arguments: dict) -> str:
        """Execute a tool and return string result."""
        method = getattr(self, f"_tool_{tool_name}", None)
        if method is None:
            return f"Error: Unknown tool '{tool_name}'"
        try:
            return method(**arguments)
        except Exception as e:
            return f"Error: {e}"

    def _resolve_path(self, path: str) -> Path:
        """Resolve path relative to scan root, preventing escape."""
        resolved = (self.scan_root / path).resolve()
        if not str(resolved).startswith(str(self.scan_root)):
            raise ValueError(f"Path escapes scan root: {path}")
        return resolved

    def _tool_read_file(self, path: str, start_line: int | None = None, end_line: int | None = None) -> str:
        resolved = self._resolve_path(path)
        if not resolved.is_file():
            return f"Error: File not found: {path}"

        lines = resolved.read_text(errors="replace").split("\n")
        start = (start_line or 1) - 1
        end = end_line or len(lines)
        selected = lines[start:end]

        numbered = []
        for i, line in enumerate(selected, start + 1):
            numbered.append(f"{i:4d} | {line}")
        return "\n".join(numbered)

    def _tool_search_code(self, pattern: str, file_glob: str | None = None, max_results: int = 20) -> str:
        import fnmatch
        results = []
        compiled = re.compile(pattern, re.IGNORECASE)

        for path in self.scan_root.rglob("*"):
            if not path.is_file():
                continue
            rel = str(path.relative_to(self.scan_root))

            # Skip common non-code dirs
            if any(part in rel for part in ["node_modules", ".git", ".next", "__pycache__", "dist"]):
                continue

            if file_glob and not fnmatch.fnmatch(rel, file_glob):
                continue

            try:
                content = path.read_text(errors="replace")
            except Exception:
                continue

            for i, line in enumerate(content.split("\n"), 1):
                if compiled.search(line):
                    results.append(f"{rel}:{i}: {line.strip()}")
                    if len(results) >= max_results:
                        return "\n".join(results)

        return "\n".join(results) if results else "No matches found."

    def _tool_list_files(self, directory: str, pattern: str | None = None, recursive: bool = True) -> str:
        import fnmatch
        resolved = self._resolve_path(directory)
        if not resolved.is_dir():
            return f"Error: Directory not found: {directory}"

        files = []
        iterator = resolved.rglob("*") if recursive else resolved.iterdir()
        for path in sorted(iterator):
            if not path.is_file():
                continue
            rel = str(path.relative_to(self.scan_root))
            if pattern and not fnmatch.fnmatch(path.name, pattern):
                continue
            files.append(rel)
            if len(files) >= 100:
                files.append("... (truncated at 100)")
                break

        return "\n".join(files) if files else "No files found."

    def _tool_find_references(self, symbol: str, file_glob: str | None = None) -> str:
        # Delegate to search_code with word boundary
        pattern = rf"\b{re.escape(symbol)}\b"
        return self._tool_search_code(pattern, file_glob, max_results=30)

    def _tool_get_route_middleware_chain(self, route_path: str) -> str:
        # Convert route path to file path if needed
        if route_path.startswith("/"):
            file_path = route_path.lstrip("/").replace("[", "[").replace("]", "]")
            candidates = [
                self.scan_root / "app" / file_path / "route.ts",
                self.scan_root / "app" / file_path / "route.js",
                self.scan_root / file_path,
            ]
        else:
            candidates = [self._resolve_path(route_path)]

        for candidate in candidates:
            if candidate.is_file():
                content = candidate.read_text(errors="replace")
                # Extract imports and auth-related code
                lines = content.split("\n")
                relevant = []
                for i, line in enumerate(lines, 1):
                    if any(kw in line.lower() for kw in [
                        "import", "auth", "middleware", "csrf", "session",
                        "getactive", "requireauth", "login_required",
                        "export async function", "export function",
                        "rate", "limit", "permission", "role",
                    ]):
                        relevant.append(f"{i:4d} | {line}")

                rel = str(candidate.relative_to(self.scan_root))
                header = f"File: {rel}\n{'=' * 40}\n"
                return header + "\n".join(relevant) if relevant else header + "(no auth/middleware patterns found)"

        return f"Error: Could not find route file for {route_path}"

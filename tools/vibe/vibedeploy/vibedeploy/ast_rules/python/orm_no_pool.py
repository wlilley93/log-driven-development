"""Detect database connections without connection pooling."""

from __future__ import annotations

import re
from pathlib import Path

from vibedeploy.models import Category, Effort, Finding, Severity


class OrmNoPoolRule:
    """Flag psycopg2.connect() and similar without connection pooling."""

    rule_id = "py-orm-no-pool"
    rule_name = "DB Without Pool"
    file_patterns = ("*.py",)

    _NO_POOL_PATTERNS = [
        (re.compile(r'psycopg2\.connect\s*\('), "psycopg2.connect() without pool"),
        (re.compile(r'pymysql\.connect\s*\('), "pymysql.connect() without pool"),
        (re.compile(r'sqlite3\.connect\s*\('), "sqlite3.connect() without pool"),
        (re.compile(r'create_engine\s*\([^)]*(?!pool)'), "SQLAlchemy create_engine() may lack pool config"),
    ]

    _POOL_INDICATORS = [
        "pool", "Pool", "ConnectionPool", "pool_size", "max_overflow",
        "pgbouncer", "pgpool", "connection_pool",
    ]

    def scan(self, target: str) -> list[Finding]:
        findings = []

        for py_file in Path(target).rglob("*.py"):
            rel = str(py_file.relative_to(target))
            if any(skip in rel for skip in ("venv", "node_modules", ".git", "test", "migration")):
                continue

            try:
                content = py_file.read_text(errors="replace")
            except OSError:
                continue

            # Check if file has pool indicators
            has_pool = any(indicator in content for indicator in self._POOL_INDICATORS)
            if has_pool:
                continue

            for i, line in enumerate(content.split("\n"), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue

                for pattern, desc in self._NO_POOL_PATTERNS:
                    if pattern.search(line):
                        findings.append(Finding(
                            tool="ast",
                            severity=Severity.MEDIUM,
                            category=Category.AST,
                            file=rel,
                            line=i,
                            rule_id=self.rule_id,
                            rule_name=self.rule_name,
                            message=f"{desc} — use connection pooling in production",
                            effort=Effort.MEDIUM,
                            fix_hint="Use psycopg2.pool, SQLAlchemy pool, or pgbouncer",
                        ))

        return findings

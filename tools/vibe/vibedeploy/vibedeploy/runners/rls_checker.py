"""rls_checker runner (custom) — scan SQL for tables missing Row Level Security."""

from __future__ import annotations

import re

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner

# Tables that typically do not need RLS (system/metadata tables)
_RLS_EXEMPT_PATTERNS = [
    re.compile(r"^schema_migrations$", re.IGNORECASE),
    re.compile(r"^flyway_schema_history$", re.IGNORECASE),
    re.compile(r"^__drizzle_migrations$", re.IGNORECASE),
    re.compile(r"^_prisma_migrations$", re.IGNORECASE),
    re.compile(r"^knex_migrations", re.IGNORECASE),
    re.compile(r"^pg_", re.IGNORECASE),
    re.compile(r"^information_schema\.", re.IGNORECASE),
    re.compile(r"^sequelize", re.IGNORECASE),
    re.compile(r"^typeorm_metadata$", re.IGNORECASE),
    re.compile(r"^alembic_version$", re.IGNORECASE),
    re.compile(r"^django_migrations$", re.IGNORECASE),
    re.compile(r"^django_content_type$", re.IGNORECASE),
    re.compile(r"^ar_internal_metadata$", re.IGNORECASE),
]

# Pattern to extract table names from CREATE TABLE statements
_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:\"?(\w+)\"?\.)?\"?(\w+)\"?",
    re.IGNORECASE | re.MULTILINE,
)

# Pattern to find ENABLE ROW LEVEL SECURITY statements
_ENABLE_RLS_RE = re.compile(
    r"ALTER\s+TABLE\s+(?:\"?(\w+)\"?\.)?\"?(\w+)\"?\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY",
    re.IGNORECASE | re.MULTILINE,
)


def _is_exempt(table_name: str) -> bool:
    """Check if a table is exempt from RLS requirements."""
    return any(p.match(table_name) for p in _RLS_EXEMPT_PATTERNS)


class RlsCheckerRunner(AsyncToolRunner):
    name = "rls_checker"

    def _is_sqlite_project(self) -> bool:
        """Detect whether the project uses SQLite (which has no RLS support).

        Checks, in order:
        1. Explicit --db flag (config.db) — "sqlite" means SQLite.
        2. Presence of .db or .sqlite / .sqlite3 files in the target directory.
        3. sqlite3 imports or sqlite connection strings in Python/JS source files.
        """
        # 1. Explicit --db override from CLI or config file
        if self.config.db:
            return self.config.db.lower() in ("sqlite", "sqlite3")

        from pathlib import Path

        target = Path(self.target)

        # 2. Look for SQLite database files
        for ext in ("*.db", "*.sqlite", "*.sqlite3"):
            # Only check top-level and one level deep to stay fast
            if list(target.glob(ext)) or list(target.glob(f"*/{ext}")):
                return True

        # 3. Scan source files for sqlite3 usage patterns
        _SQLITE_PATTERNS = [
            re.compile(r"import\s+sqlite3", re.IGNORECASE),
            re.compile(r"from\s+sqlite3\s+import", re.IGNORECASE),
            re.compile(r"require\(['\"]better-sqlite3['\"]\)", re.IGNORECASE),
            re.compile(r"sqlite:///", re.IGNORECASE),
            re.compile(r"sqlite3\.connect\(", re.IGNORECASE),
        ]
        source_files = self._scan_files("*.py", "*.js", "*.ts", max_files=200)
        for src in source_files:
            content = self._read_file(src)
            if not content:
                continue
            for pat in _SQLITE_PATTERNS:
                if pat.search(content):
                    return True

        return False

    def should_run(self) -> bool:
        # SQLite does not support or need Row Level Security
        if self._is_sqlite_project():
            self.skip_reason = "SQLite detected — RLS is not applicable"
            return False

        sql_files = self._scan_files(
            "*.sql",
            "migrations/**/*.sql",
            "db/migrate/**/*.sql",
            "db/migrations/**/*.sql",
            "supabase/migrations/**/*.sql",
        )
        if not sql_files:
            self.skip_reason = "no SQL files found to check for RLS"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        sql_files = self._scan_files(
            "*.sql",
            "migrations/**/*.sql",
            "db/migrate/**/*.sql",
            "db/migrations/**/*.sql",
            "supabase/migrations/**/*.sql",
        )
        if not sql_files:
            return ToolResult(tool=self.name, status=ToolStatus.SKIPPED)

        # Collect all CREATE TABLE and ENABLE RLS across all files
        created_tables: dict[str, tuple[str, int]] = {}  # table_name -> (file, line)
        rls_enabled_tables: set[str] = set()

        for sql_file in sql_files:
            content = self._read_file(sql_file)
            if not content:
                continue

            try:
                relative_path = str(sql_file.relative_to(self.target))
            except ValueError:
                relative_path = str(sql_file)

            # Find CREATE TABLE statements
            for match in _CREATE_TABLE_RE.finditer(content):
                schema = match.group(1) or "public"
                table_name = match.group(2)
                full_name = f"{schema}.{table_name}"
                # Approximate line number
                line_num = content[:match.start()].count("\n") + 1

                if not _is_exempt(table_name):
                    # Only track the first occurrence
                    if table_name not in created_tables and full_name not in created_tables:
                        created_tables[table_name] = (relative_path, line_num)

            # Find ENABLE ROW LEVEL SECURITY statements
            for match in _ENABLE_RLS_RE.finditer(content):
                schema = match.group(1) or "public"
                table_name = match.group(2)
                rls_enabled_tables.add(table_name)
                rls_enabled_tables.add(f"{schema}.{table_name}")

        # Find tables without RLS
        findings: list[Finding] = []
        for table_name, (file_path, line_num) in created_tables.items():
            if table_name not in rls_enabled_tables:
                # Also check with public schema prefix
                if f"public.{table_name}" not in rls_enabled_tables:
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.CRITICAL,
                        category=Category.DATABASE,
                        file=file_path,
                        line=line_num,
                        rule_id="missing-rls",
                        rule_name="Missing Row Level Security",
                        message=f"Table '{table_name}' is missing Row Level Security (RLS). "
                                f"Without RLS, any authenticated user can access all rows.",
                        blocks_deploy=True,
                        effort=Effort.MEDIUM,
                        fix_hint=(
                            f"Add: ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY; "
                            f"then create appropriate policies with CREATE POLICY"
                        ),
                        docs_url="https://www.postgresql.org/docs/current/ddl-rowsecurity.html",
                    ))

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
        )

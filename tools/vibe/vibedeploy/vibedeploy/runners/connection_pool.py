"""connection_pool runner (custom) — check for database connection pool configuration."""

from __future__ import annotations

import re

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner

# Patterns indicating direct connections without pooling
_DIRECT_CONNECT_PATTERNS: list[tuple[re.Pattern, str, str, str]] = [
    # Python: psycopg2 direct connect without pool
    (
        re.compile(r"psycopg2\.connect\s*\(", re.MULTILINE),
        "psycopg2-no-pool",
        "Direct psycopg2.connect() without connection pooling",
        "Use psycopg2.pool.ThreadedConnectionPool or SQLAlchemy with pool_size",
    ),
    # Python: direct psycopg3 connect
    (
        re.compile(r"psycopg\.connect\s*\(", re.MULTILINE),
        "psycopg3-no-pool",
        "Direct psycopg.connect() without connection pooling",
        "Use psycopg_pool.ConnectionPool or psycopg_pool.AsyncConnectionPool",
    ),
    # Node.js: pg.Client without pool
    (
        re.compile(r"new\s+(?:pg\.)?Client\s*\(", re.MULTILINE),
        "pg-client-no-pool",
        "Using pg.Client instead of pg.Pool — each query opens a new connection",
        "Replace new Client() with new Pool() from the 'pg' package",
    ),
    # Ruby: direct PG.connect
    (
        re.compile(r"PG\.connect\s*\(", re.MULTILINE),
        "pg-ruby-no-pool",
        "Direct PG.connect() without connection pooling",
        "Use ActiveRecord or configure a connection pool in database.yml",
    ),
    # Java: DriverManager.getConnection without pool
    (
        re.compile(r"DriverManager\.getConnection\s*\(", re.MULTILINE),
        "jdbc-no-pool",
        "Direct JDBC DriverManager.getConnection() without connection pooling",
        "Use HikariCP, Apache DBCP, or c3p0 connection pool",
    ),
    # Go: sql.Open without pool config
    (
        re.compile(r"sql\.Open\s*\(", re.MULTILINE),
        "go-sql-no-pool-config",
        "sql.Open() detected — ensure SetMaxOpenConns and SetMaxIdleConns are configured",
        "Call db.SetMaxOpenConns(), db.SetMaxIdleConns(), and db.SetConnMaxLifetime()",
    ),
]

# Patterns for DATABASE_URL without pool parameters
_URL_NO_POOL_PATTERNS: list[tuple[re.Pattern, str, str, str]] = [
    # Prisma without connection_limit
    (
        re.compile(
            r'DATABASE_URL\s*=\s*["\']?postgres(?:ql)?://[^"\']*(?!\?.*connection_limit)[^"\']*["\']?',
            re.MULTILINE,
        ),
        "prisma-no-connection-limit",
        "DATABASE_URL for Prisma missing ?connection_limit parameter",
        "Add ?connection_limit=10 (or appropriate value) to DATABASE_URL for Prisma",
    ),
]

# Patterns indicating pooling IS configured (positive signals)
_POOL_PRESENT_PATTERNS: list[re.Pattern] = [
    re.compile(r"new\s+(?:pg\.)?Pool\s*\(", re.MULTILINE),  # pg.Pool
    re.compile(r"pgBouncer|pgbouncer|PgBouncer", re.MULTILINE),  # pgBouncer
    re.compile(r"connection_limit\s*=|connectionLimit|pool_size|poolSize|maxConnections", re.MULTILINE),
    re.compile(r"(?:Threaded|Simple)ConnectionPool|ConnectionPool\s*\(", re.MULTILINE),  # psycopg2 pool
    re.compile(r"create_pool|AsyncConnectionPool|NullPool|QueuePool", re.MULTILINE),  # SQLAlchemy / asyncpg
    re.compile(r"HikariCP|hikari|HikariDataSource", re.IGNORECASE | re.MULTILINE),  # Java HikariCP
    re.compile(r"SetMaxOpenConns|SetMaxIdleConns|SetConnMaxLifetime", re.MULTILINE),  # Go
    re.compile(r"pgxpool|pgx\.ConnConfig", re.MULTILINE),  # Go pgx pool
    re.compile(r"pool_mode\s*=|default_pool_size", re.MULTILINE),  # pgBouncer config
    re.compile(r"Supavisor|supavisor", re.MULTILINE),  # Supabase pooler
]

# File extensions to scan
_SOURCE_EXTENSIONS = (
    "*.py", "*.js", "*.ts", "*.tsx", "*.jsx",
    "*.rb", "*.java", "*.go", "*.rs",
    "*.env", "*.env.*", "*.toml", "*.yaml", "*.yml",
    "*.prisma", "*.cfg", "*.conf", "*.ini",
)


class ConnectionPoolRunner(AsyncToolRunner):
    name = "connection_pool"

    def should_run(self) -> bool:
        # Look for any source files that might contain database configuration
        for ext in _SOURCE_EXTENSIONS:
            if self._scan_files(ext, max_files=1):
                return True
        self.skip_reason = "no source files found to check for connection pooling"
        return False

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        # Prioritise config/env files and limit source file scanning
        _CONFIG_EXTS = ("*.env", "*.env.*", "*.toml", "*.yaml", "*.yml", "*.prisma", "*.cfg", "*.conf", "*.ini")
        _CODE_EXTS = ("*.py", "*.js", "*.ts", "*.tsx", "*.jsx", "*.rb", "*.java", "*.go", "*.rs")

        source_files = []
        for ext in _CONFIG_EXTS:
            source_files.extend(self._scan_files(ext, max_files=200))
        for ext in _CODE_EXTS:
            source_files.extend(self._scan_files(ext, max_files=500))

        if not source_files:
            return ToolResult(tool=self.name, status=ToolStatus.SKIPPED)

        findings: list[Finding] = []
        pool_detected = False

        for source_file in source_files:
            content = self._read_file(source_file)
            if not content:
                continue

            try:
                relative_path = str(source_file.relative_to(self.target))
            except ValueError:
                relative_path = str(source_file)

            # Check if pooling is already configured in this file
            file_has_pool = any(p.search(content) for p in _POOL_PRESENT_PATTERNS)
            if file_has_pool:
                pool_detected = True
                continue

            # Check for direct connection patterns (anti-patterns)
            for pattern, rule_id, message, hint in _DIRECT_CONNECT_PATTERNS:
                for match in pattern.finditer(content):
                    line_num = content[:match.start()].count("\n") + 1
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.HIGH,
                        category=Category.DATABASE,
                        file=relative_path,
                        line=line_num,
                        rule_id=rule_id,
                        rule_name="Missing connection pool",
                        message=message,
                        blocks_deploy=False,
                        effort=Effort.MEDIUM,
                        fix_hint=hint,
                    ))

            # Check DATABASE_URL patterns (only in config/env files)
            if relative_path.endswith((".env", ".toml", ".yaml", ".yml", ".prisma", ".cfg", ".conf", ".ini")) \
               or ".env." in relative_path:
                for pattern, rule_id, message, hint in _URL_NO_POOL_PATTERNS:
                    for match in pattern.finditer(content):
                        line_num = content[:match.start()].count("\n") + 1
                        findings.append(Finding(
                            tool=self.name,
                            severity=Severity.MEDIUM,
                            category=Category.DATABASE,
                            file=relative_path,
                            line=line_num,
                            rule_id=rule_id,
                            rule_name="Missing pool configuration in URL",
                            message=message,
                            blocks_deploy=False,
                            effort=Effort.TRIVIAL,
                            fix_hint=hint,
                        ))

        # Check for pgBouncer config files
        pgbouncer_configs = self._scan_files("pgbouncer.ini", "pgbouncer.conf", "**/pgbouncer.ini")
        if pgbouncer_configs:
            pool_detected = True

        # If no pool is detected anywhere and we found direct connections, elevate severity
        if not pool_detected and findings:
            # Add a summary finding
            findings.insert(0, Finding(
                tool=self.name,
                severity=Severity.HIGH,
                category=Category.DATABASE,
                file="project",
                rule_id="no-connection-pool",
                rule_name="No connection pooling detected",
                message=(
                    "No database connection pooling was detected in this project. "
                    "Direct connections exhaust database limits under load and cause "
                    "connection storms during deployments."
                ),
                blocks_deploy=False,
                effort=Effort.MEDIUM,
                fix_hint=(
                    "Add a connection pool: pg.Pool (Node.js), SQLAlchemy pool (Python), "
                    "HikariCP (Java), or use PgBouncer as an external pooler"
                ),
            ))

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
        )

"""Normaliser for sqlfluff output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser

# Rules that indicate full-table scan or dangerous query patterns
FULL_TABLE_SCAN_RULES = {
    "L044",  # Query produces a cartesian product (implicit join)
    "ST09",  # SELECT * usage
    "AM06",  # SELECT * usage (newer alias)
}

# Rules associated with missing WHERE clauses or unbounded queries
UNBOUNDED_QUERY_RULES = {
    "L053",  # Top-level statements should not be wrapped in brackets
}

# Map sqlfluff rule codes to human-readable names
RULE_NAME_MAP = {
    "L001": "Unnecessary trailing whitespace",
    "L002": "Mixed spaces and tabs in indentation",
    "L003": "Indentation not consistent",
    "L004": "Indentation not a multiple of configured tab size",
    "L005": "Commas should not have whitespace directly before them",
    "L006": "Operators should be surrounded by single spaces",
    "L007": "Operators should be at the end of the line",
    "L008": "Commas should be followed by a single space",
    "L009": "Files must end with a single trailing newline",
    "L010": "Inconsistent capitalisation of keywords",
    "L011": "Implicit aliasing of table",
    "L012": "Implicit aliasing of column",
    "L013": "Column expression without alias in a SELECT with more than one column",
    "L014": "Inconsistent capitalisation of unquoted identifiers",
    "L015": "DISTINCT used with parentheses",
    "L016": "Line too long",
    "L017": "Function name not immediately followed by parenthesis",
    "L018": "WITH clause closing bracket should be on its own line",
    "L019": "Leading/Trailing comma enforcement",
    "L020": "Table aliases should be unique within each clause",
    "L021": "Ambiguous use of DISTINCT in SELECT with GROUP BY",
    "L022": "Blank line expected but not found after CTE closing bracket",
    "L023": "Single whitespace expected after AS in WITH clause",
    "L024": "Single whitespace expected after USING in JOIN clause",
    "L025": "Tables should not be aliased if that alias is not used",
    "L026": "References cannot be qualified if source not found",
    "L027": "References should be qualified if select targets are ambiguous",
    "L028": "References should be consistent in statements with a single table",
    "L029": "Keywords should not be used as identifiers",
    "L030": "Inconsistent capitalisation of function names",
    "L031": "Avoid table aliases in FROM and JOIN clauses",
    "L032": "Prefer specifying join keys instead of using USING",
    "L033": "UNION [DISTINCT|ALL] preference",
    "L034": "Select wildcards then simple targets before calculations",
    "L035": "Do not specify ELSE NULL in a CASE WHEN statement",
    "L036": "Select targets should be on a new line unless there is only one",
    "L037": "Ambiguous ordering direction for columns in ORDER BY",
    "L038": "Trailing commas within SELECT clause",
    "L039": "Unnecessary whitespace found",
    "L040": "Inconsistent capitalisation of boolean/null literal",
    "L041": "SELECT clause modifiers such as DISTINCT must be on the same line as SELECT",
    "L042": "JOIN and FROM clause subqueries should not be wrapped in brackets",
    "L043": "Unnecessary CASE when the values are booleans",
    "L044": "Query produces a cartesian product",
    "L045": "Query defines a CTE but does not use it",
    "L046": "Jinja tags should have a single whitespace on either side",
    "L048": "Quoted literals should be surrounded by single whitespace",
    "L049": "Comparisons should use IS or IS NOT for null/boolean comparisons",
    "L050": "Files should not begin with newlines",
    "L051": "INNER JOIN should be fully qualified",
    "L052": "Statements should end with a semicolon",
    "L053": "Top-level statements should not be wrapped in brackets",
    "L054": "Inconsistent column references in GROUP BY/ORDER BY",
    "L055": "Use LEFT JOIN instead of RIGHT JOIN",
    "L056": "SP_ prefix should not be used for user-defined stored procedures",
    "L057": "Do not use special characters in identifiers",
    "L058": "Nested CASE statement found",
    "L059": "Unnecessary quoted identifier",
    "L060": "Use COALESCE instead of CASE with IS NULL",
    "L061": "Use != instead of <> or vice versa",
    "L062": "Prefer CAST to CONVERT",
    "L063": "Data type identifier casing",
    "L064": "Consistent usage of preferred quotes for quoted literals",
    "L065": "Set operators should be surrounded by newlines",
    "L066": "Ambient union types should be parenthesised",
    "L067": "Enforce consistent syntax for typed array columns",
    # Newer sqlfluff rule prefixes (post-2.x)
    "ST09": "SELECT * usage",
    "AM06": "SELECT * usage",
    "JJ01": "Implicit JOIN (comma join)",
    "RF02": "Unqualified reference in multi-table statement",
    "RF03": "Ambiguous column reference",
    "CP01": "Capitalisation of keywords",
    "CP02": "Capitalisation of identifiers",
    "LT01": "Expected single space",
    "LT02": "Incorrect indentation",
    "LT05": "Line too long",
    "LT09": "Select targets should be on new lines",
    "LT12": "Files must end with a trailing newline",
}

# Anti-patterns that indicate performance issues
ANTI_PATTERN_RULES = FULL_TABLE_SCAN_RULES | {
    "L011",  # Implicit aliasing (readability, but can cause perf confusion)
    "L012",  # Implicit column aliasing
    "L044",  # Cartesian product
    "L045",  # Unused CTE (wasted computation)
    "JJ01",  # Implicit JOIN
    "RF02",  # Unqualified reference
    "RF03",  # Ambiguous column reference
}


class SqlfluffNormaliser(BaseNormaliser):
    """Convert sqlfluff JSON output to Finding objects.

    sqlfluff JSON shape (list of file results):
    [
      {
        "filepath": "queries/select_all.sql",
        "violations": [
          {
            "start_line_no": 1,
            "start_line_pos": 8,
            "code": "L044",
            "description": "Query produces a cartesian product",
            "name": "ambiguous.join",
            "warning": false,
            "fixes": [...]
          }
        ]
      }
    ]
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, list):
            return []

        findings: list[Finding] = []

        for file_entry in raw_data:
            if not isinstance(file_entry, dict):
                continue

            filepath = file_entry.get("filepath", "<unknown>")
            violations = file_entry.get("violations", [])

            if not isinstance(violations, list):
                continue

            for violation in violations:
                if not isinstance(violation, dict):
                    continue

                code = violation.get("code", "unknown")
                description = violation.get("description", "SQL lint violation")
                line = violation.get("start_line_no")
                col = violation.get("start_line_pos")
                has_fixes = bool(violation.get("fixes"))

                severity = self._classify_severity(code)
                rule_name = RULE_NAME_MAP.get(code, violation.get("name", code))
                fix_hint = self._build_fix_hint(code, description, has_fixes)
                effort = self._classify_effort(code, has_fixes)

                findings.append(Finding(
                    tool="sqlfluff",
                    severity=severity,
                    category=Category.DATABASE,
                    file=filepath,
                    rule_id=f"sqlfluff/{code}",
                    rule_name=rule_name,
                    message=description,
                    line=line,
                    col=col,
                    fix_hint=fix_hint,
                    effort=effort,
                    raw=violation,
                ))

        return findings

    def _classify_severity(self, code: str) -> Severity:
        """Classify severity based on the rule code."""
        if code in FULL_TABLE_SCAN_RULES:
            return Severity.HIGH
        if code in ANTI_PATTERN_RULES:
            return Severity.MEDIUM
        return Severity.MEDIUM

    def _build_fix_hint(self, code: str, description: str, has_fixes: bool) -> str:
        """Generate a helpful fix hint for the violation."""
        auto_fix = " Run `sqlfluff fix` to auto-fix." if has_fixes else ""

        if code in ("ST09", "AM06"):
            return (
                "Replace SELECT * with explicit column names. This avoids fetching "
                "unnecessary data and prevents breakage when table schema changes."
                + auto_fix
            )
        if code == "L044" or code == "JJ01":
            return (
                "Use explicit JOIN syntax (INNER JOIN, LEFT JOIN) with ON clauses "
                "instead of comma-separated tables. Cartesian products cause "
                "exponential row expansion and severe performance degradation."
                + auto_fix
            )
        if code == "L045":
            return (
                "Remove the unused CTE or reference it in the main query. "
                "Unused CTEs waste computation and can confuse query planners."
                + auto_fix
            )
        if code in ("RF02", "RF03", "L026", "L027"):
            return (
                "Qualify column references with table aliases to avoid ambiguity. "
                "This helps the query planner and prevents incorrect results in "
                "multi-table queries."
                + auto_fix
            )
        if code in ("L011", "L012"):
            return (
                "Use explicit AS keyword for aliases. Implicit aliasing reduces "
                "readability and can cause confusion in complex queries."
                + auto_fix
            )

        return f"{description}.{auto_fix}" if auto_fix else description

    def _classify_effort(self, code: str, has_fixes: bool) -> Effort:
        """Classify the effort required to fix this violation."""
        if has_fixes:
            return Effort.LOW
        if code in FULL_TABLE_SCAN_RULES:
            return Effort.MEDIUM
        if code in ANTI_PATTERN_RULES:
            return Effort.MEDIUM
        return Effort.LOW

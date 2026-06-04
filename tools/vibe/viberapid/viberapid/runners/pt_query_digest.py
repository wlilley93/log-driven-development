"""Runner for pt-query-digest — Percona Toolkit MySQL slow query log analysis."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.pt_query_digest import PtQueryDigestNormaliser
from viberapid.runners.base import AsyncToolRunner


class PtQueryDigestRunner(AsyncToolRunner):
    """Run pt-query-digest to analyse MySQL/MariaDB slow query logs.

    Expects either:
    - tools.pt_query_digest.slow_log in config pointing to a slow query log
    - Auto-detected slow query log in the project directory
    """

    name = "pt_query_digest"

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "pt-query-digest not installed (Percona Toolkit)"
            return False

        log_file = self._resolve_slow_log()
        if not log_file:
            self.skip_reason = (
                "no MySQL slow query log found — set "
                "tools.pt_query_digest.slow_log in config"
            )
            return False

        return True

    @property
    def bin_path(self) -> str:
        """pt-query-digest uses a hyphenated binary name."""
        from viberapid.installer import get_tool_bin
        import shutil

        path = get_tool_bin("pt-query-digest")
        if Path(path).exists():
            return path
        found = shutil.which("pt-query-digest")
        return found or "pt-query-digest"

    def _resolve_slow_log(self) -> str | None:
        """Find the MySQL slow query log from config or auto-detection."""
        tc = self.tool_config
        explicit = tc.get("slow_log")
        if explicit:
            path = Path(explicit)
            if not path.is_absolute():
                path = Path(self.target) / path
            if path.exists():
                return str(path)
            return None

        # Auto-detect common slow query log locations
        candidates = [
            "slow-query.log",
            "mysql-slow.log",
            "slow.log",
            "log/slow-query.log",
            "logs/mysql-slow.log",
        ]
        for candidate in candidates:
            path = Path(self.target) / candidate
            if path.exists():
                return str(path)

        return None

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        slow_log = self._resolve_slow_log()
        if not slow_log:
            return self._make_error_result("no MySQL slow query log found")

        tc = self.tool_config
        limit_queries = tc.get("limit", 20)

        try:
            bin_path = self.bin_path
            cmd = [
                bin_path,
                "--limit", f"{limit_queries}",
                "--output", "report",
                slow_log,
            ]

            result = self._exec(cmd)

            if result.returncode != 0 and not result.stdout.strip():
                return self._make_error_result(
                    f"pt-query-digest failed. "
                    f"exit code: {result.returncode}, "
                    f"stderr: {result.stderr[:500]}"
                )

            # Parse the text report into structured data
            raw_data = _parse_digest_report(result.stdout)
            raw_data["slow_log"] = slow_log

            normaliser = PtQueryDigestNormaliser()
            findings = normaliser.normalise(raw_data)

            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=findings,
                metrics={
                    "slow_log": slow_log,
                    "queries_analysed": raw_data.get("total_queries", 0),
                    "unique_queries": len(raw_data.get("queries", [])),
                },
            )

        except Exception as exc:
            return self._make_error_result(f"pt-query-digest failed: {exc}")


def _parse_digest_report(report: str) -> dict:
    """Parse pt-query-digest text report into structured data.

    The report has a profile section and per-query sections.
    """
    result: dict = {
        "queries": [],
        "total_queries": 0,
        "total_time_s": 0,
    }

    if not report.strip():
        return result

    # --- Parse overall summary ---
    # Look for lines like: "# Attribute    total     min     max     avg"
    total_match = re.search(
        r"#\s+(\d+)\s+unique",
        report,
    )
    if total_match:
        result["total_queries"] = int(total_match.group(1))

    # --- Parse profile section ---
    # Profile looks like:
    # # Rank Query ID           Response time   Calls  R/Call  V/M   Item
    # # ==== ================== ============== ======= ======= ===== ======
    # #    1 0xABC123...        100.0000 50.0%     500  0.2000  0.01 SELECT orders
    profile_pattern = re.compile(
        r"#\s+(\d+)\s+(0x[A-Fa-f0-9]+)\s+"
        r"([\d.]+)\s+([\d.]+)%\s+"
        r"(\d+)\s+([\d.]+)\s+([\d.]+)\s+"
        r"(.+)"
    )

    for match in profile_pattern.finditer(report):
        rank = int(match.group(1))
        query_id = match.group(2)
        response_time = float(match.group(3))
        response_pct = float(match.group(4))
        calls = int(match.group(5))
        avg_time = float(match.group(6))
        variance = float(match.group(7))
        item = match.group(8).strip()

        result["queries"].append({
            "rank": rank,
            "query_id": query_id,
            "total_time_s": response_time,
            "pct_total": response_pct,
            "calls": calls,
            "avg_time_s": avg_time,
            "variance_to_mean": variance,
            "item": item,
        })

    # --- Parse individual query sections ---
    # Each query section starts with "# Query N: ..."
    query_sections = re.split(r"(?=# Query \d+:)", report)
    query_details: dict[int, dict] = {}

    for section in query_sections:
        header_match = re.match(r"# Query (\d+):", section)
        if not header_match:
            continue

        rank = int(header_match.group(1))
        details: dict = {"rank": rank}

        # Extract QPS
        qps_match = re.search(r"([\d.]+) QPS", section)
        if qps_match:
            details["qps"] = float(qps_match.group(1))

        # Extract sample query
        # Queries typically appear after a blank line following the stats
        lines = section.split("\n")
        query_lines = []
        in_query = False
        for line in lines:
            if not line.startswith("#") and line.strip():
                in_query = True
                query_lines.append(line)
            elif in_query and not line.strip():
                break

        if query_lines:
            details["sample_query"] = "\n".join(query_lines).strip()

        # Extract time stats
        time_match = re.search(
            r"#\s+Query_time.*?:\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)",
            section,
        )
        if time_match:
            details["min_time_s"] = float(time_match.group(1))
            details["max_time_s"] = float(time_match.group(2))
            details["avg_time_s"] = float(time_match.group(3))
            details["p95_time_s"] = float(time_match.group(4))

        # Extract rows examined
        rows_match = re.search(
            r"#\s+Rows_examined.*?:\s+(\d+)\s+(\d+)\s+([\d.]+)\s+([\d.]+)",
            section,
        )
        if rows_match:
            details["rows_examined_min"] = int(rows_match.group(1))
            details["rows_examined_max"] = int(rows_match.group(2))

        query_details[rank] = details

    # Merge details into queries
    for query in result["queries"]:
        rank = query["rank"]
        if rank in query_details:
            query.update(query_details[rank])

    return result

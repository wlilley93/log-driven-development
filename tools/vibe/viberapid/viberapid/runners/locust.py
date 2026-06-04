"""Runner for locust — Python-based load testing framework."""

from __future__ import annotations

import csv
import io
import tempfile
from pathlib import Path

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.locust import LocustNormaliser
from viberapid.runners.base import AsyncToolRunner


class LocustRunner(AsyncToolRunner):
    """Run locust in headless mode with CSV export against a URL."""

    name = "locust"
    requires_python = True
    is_load_tester = True
    requires_url = True

    def should_run(self) -> bool:
        if not self.config.url:
            self.skip_reason = "no --url provided"
            return False
        if not self._tool_exists():
            self.skip_reason = "locust not installed"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        url = self.config.url
        tc = self.tool_config

        duration = self.config.load_duration  # e.g., "30s"
        users = self.config.load_vus
        spawn_rate = tc.get("spawn_rate", max(1, users // 5))

        # Parse duration to a locust-compatible run-time string
        run_time = duration  # locust accepts "30s", "5m", etc.

        # Generate a minimal locustfile
        locustfile_content = f"""from locust import HttpUser, task, between

class ViberapidUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def load_target(self):
        self.client.get("/")
"""

        # Allow custom locustfile from tool config
        custom_locustfile = tc.get("locustfile")

        locustfile_path = None
        csv_prefix_dir = None
        csv_prefix = None

        try:
            # Write locustfile to temp if no custom one
            if custom_locustfile:
                locustfile_resolved = Path(self.target) / custom_locustfile
                if not locustfile_resolved.exists():
                    return self._make_error_result(
                        f"Custom locustfile not found: {custom_locustfile}"
                    )
                locustfile_path = str(locustfile_resolved)
            else:
                with tempfile.NamedTemporaryFile(
                    prefix="viberapid-locust-",
                    suffix=".py",
                    mode="w",
                    delete=False,
                ) as lf:
                    lf.write(locustfile_content)
                    locustfile_path = lf.name

            # CSV output prefix
            csv_prefix_dir = tempfile.mkdtemp(prefix="viberapid-locust-csv-")
            csv_prefix = str(Path(csv_prefix_dir) / "stats")

            bin_path = self.bin_path
            cmd = [
                bin_path,
                "--headless",
                "--host", url,
                "--users", str(users),
                "--spawn-rate", str(spawn_rate),
                "--run-time", run_time,
                "--csv", csv_prefix,
                "--locustfile", locustfile_path,
            ]

            result = self._exec(cmd, cwd="/tmp")

            # Parse CSV stats file
            stats_csv = Path(f"{csv_prefix}_stats.csv")
            if not stats_csv.exists() or stats_csv.stat().st_size == 0:
                return self._make_error_result(
                    f"locust did not produce CSV output. "
                    f"exit code: {result.returncode}, "
                    f"stderr: {result.stderr[:500]}"
                )

            csv_text = stats_csv.read_text()
            reader = csv.DictReader(io.StringIO(csv_text))
            rows = list(reader)

            # Parse failure stats if available
            failures_csv = Path(f"{csv_prefix}_failures.csv")
            failure_rows = []
            if failures_csv.exists() and failures_csv.stat().st_size > 0:
                failure_reader = csv.DictReader(
                    io.StringIO(failures_csv.read_text())
                )
                failure_rows = list(failure_reader)

            raw_data = {
                "stats": rows,
                "failures": failure_rows,
            }

            normaliser = LocustNormaliser()
            findings = normaliser.normalise(raw_data)

            # Extract summary metrics from the Aggregated row
            aggregated = None
            for row in rows:
                name = row.get("Name", "")
                if name == "Aggregated":
                    aggregated = row
                    break

            metrics: dict = {
                "url": url,
                "users": users,
                "spawn_rate": spawn_rate,
                "duration": duration,
            }

            if aggregated:
                metrics.update({
                    "total_requests": _safe_int(aggregated.get("Request Count")),
                    "failure_count": _safe_int(aggregated.get("Failure Count")),
                    "median_ms": _safe_float(aggregated.get("Median Response Time")),
                    "avg_ms": _safe_float(aggregated.get("Average Response Time")),
                    "p50_ms": _safe_float(aggregated.get("50%")),
                    "p95_ms": _safe_float(aggregated.get("95%")),
                    "p99_ms": _safe_float(aggregated.get("99%")),
                    "rps": _safe_float(aggregated.get("Requests/s")),
                    "failures_per_s": _safe_float(aggregated.get("Failures/s")),
                })

            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=findings,
                metrics=metrics,
            )

        except Exception as exc:
            return self._make_error_result(f"locust failed: {exc}")

        finally:
            # Clean up temp files
            if locustfile_path and not custom_locustfile:
                Path(locustfile_path).unlink(missing_ok=True)
            if csv_prefix_dir:
                import shutil
                shutil.rmtree(csv_prefix_dir, ignore_errors=True)


def _safe_float(value: str | None) -> float | None:
    """Safely convert a CSV cell to float."""
    if value is None or value == "" or value == "N/A":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: str | None) -> int | None:
    """Safely convert a CSV cell to int."""
    if value is None or value == "" or value == "N/A":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

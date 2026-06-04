"""Normaliser for hyperfine benchmark output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


class HyperfineNormaliser(BaseNormaliser):
    """Convert hyperfine JSON output to Finding objects.

    hyperfine JSON shape (--export-json):
    {
      "results": [
        {
          "command": "npm run build",
          "mean": 12.345,
          "stddev": 0.5,
          "median": 12.2,
          "user": 10.0,
          "system": 2.0,
          "min": 11.5,
          "max": 13.5,
          "times": [12.1, 12.3, 12.5, ...],
          "exit_codes": [0, 0, 0, ...],
          "parameters": {}
        }
      ]
    }

    Note: All times are in SECONDS.
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        results = raw_data.get("results", [])
        findings: list[Finding] = []

        for bench in results:
            if not isinstance(bench, dict):
                continue

            command = bench.get("command", "<command>")
            mean = bench.get("mean")
            median = bench.get("median")
            stddev = bench.get("stddev")
            min_time = bench.get("min")
            max_time = bench.get("max")

            if mean is None:
                continue

            # Determine severity based on absolute time
            # These are general heuristics for CLI/build benchmarks
            if mean > 60:
                severity = Severity.CRITICAL
                message = f"Command takes {mean:.1f}s on average. This is extremely slow for a CLI operation."
            elif mean > 30:
                severity = Severity.HIGH
                message = f"Command takes {mean:.1f}s on average. Consider optimisation."
            elif mean > 10:
                severity = Severity.MEDIUM
                message = f"Command takes {mean:.1f}s on average."
            elif mean > 5:
                severity = Severity.LOW
                message = f"Command takes {mean:.1f}s on average."
            else:
                # Under 5s is generally acceptable; still report as INFO
                severity = Severity.INFO
                message = f"Command takes {mean:.1f}s on average."

            # Add variability info
            if stddev is not None and mean > 0:
                cv = (stddev / mean) * 100
                if cv > 20:
                    message += f" High variability (CV: {cv:.0f}%)."

            # Sanitise command for rule_id (truncate long commands)
            safe_cmd = command[:80].replace(" ", "-").replace("/", "_")

            findings.append(Finding(
                tool="hyperfine",
                severity=severity,
                category=Category.RUNTIME,
                file=command,
                rule_id=f"bench-{safe_cmd}",
                rule_name="Command Benchmark",
                message=message,
                metric="mean_time_s",
                current_value=round(mean, 3),
                target_value=5.0,
                effort=Effort.MEDIUM,
                fix_hint="Profile the command to find bottlenecks. Consider caching, parallelism, or incremental builds.",
                saving_estimate=f"Reduce execution time from {mean:.1f}s" if mean > 5 else None,
                raw={
                    "command": command,
                    "mean": mean,
                    "median": median,
                    "stddev": stddev,
                    "min": min_time,
                    "max": max_time,
                },
            ))

            # Detect high variability as a separate finding
            if stddev is not None and mean > 0:
                cv = (stddev / mean) * 100
                if cv > 30:
                    findings.append(Finding(
                        tool="hyperfine",
                        severity=Severity.MEDIUM if cv > 50 else Severity.LOW,
                        category=Category.RUNTIME,
                        file=command,
                        rule_id=f"bench-variability-{safe_cmd}",
                        rule_name="High Benchmark Variability",
                        message=(
                            f"Coefficient of variation is {cv:.0f}% "
                            f"(stddev: {stddev:.3f}s, mean: {mean:.3f}s). "
                            f"Results may be unreliable."
                        ),
                        metric="cv_pct",
                        current_value=round(cv, 1),
                        target_value=15.0,
                        effort=Effort.LOW,
                        fix_hint="Close background applications, increase run count, use a dedicated benchmark environment.",
                        raw={"cv": cv, "stddev": stddev, "mean": mean},
                    ))

        return findings

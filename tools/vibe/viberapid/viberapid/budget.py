"""Performance budget — load, check, scaffold, and report budget compliance."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from viberapid.models import BudgetResult, ScanResult


# ---------------------------------------------------------------------------
# Default budget scaffold
# ---------------------------------------------------------------------------
DEFAULT_BUDGET: dict[str, Any] = {
    "$schema": "https://viberapid.dev/budget.schema.json",
    "description": "Performance budget — targets for key metrics",
    "metrics": {
        "LCP": {"target": 2500, "unit": "ms", "fail_on_exceed": True},
        "FID": {"target": 100, "unit": "ms", "fail_on_exceed": True},
        "CLS": {"target": 0.1, "unit": "score", "fail_on_exceed": True},
        "TTI": {"target": 3800, "unit": "ms", "fail_on_exceed": True},
        "TBT": {"target": 200, "unit": "ms", "fail_on_exceed": True},
        "p99_latency_ms": {"target": 500, "unit": "ms", "fail_on_exceed": True},
        "error_rate_pct": {"target": 1.0, "unit": "%", "fail_on_exceed": True},
        "rps_at_50_vus": {"target": 100, "unit": "req/s", "fail_on_exceed": False},
    },
    "bundles": {
        "total_js": {"target": 300, "unit": "kB", "fail_on_exceed": True},
        "total_css": {"target": 50, "unit": "kB", "fail_on_exceed": True},
        "largest_image": {"target": 200, "unit": "kB", "fail_on_exceed": False},
        "largest_font": {"target": 100, "unit": "kB", "fail_on_exceed": False},
    },
}


def load_budget(path: str) -> dict[str, Any]:
    """Load a budget JSON file.

    Args:
        path: Absolute or relative path to the budget JSON file.

    Returns:
        Parsed budget dict with 'metrics' and 'bundles' keys.

    Raises:
        FileNotFoundError: If the budget file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    filepath = Path(path)
    if not filepath.exists():
        raise FileNotFoundError(f"Budget file not found: {path}")

    with open(filepath) as f:
        budget = json.load(f)

    # Normalise — ensure both sections exist
    if "metrics" not in budget:
        budget["metrics"] = {}
    if "bundles" not in budget:
        budget["bundles"] = {}

    return budget


def _extract_metrics(scan_result: ScanResult) -> dict[str, float]:
    """Extract all available metric values from a scan result.

    Pulls from:
    1. tool_result.metrics dicts
    2. finding.metric + finding.current_value
    3. The _merged_metrics attr set by the scanner (if present)
    """
    metrics: dict[str, float] = {}

    # From tool results
    for tr in scan_result.tool_results:
        for key, value in tr.metrics.items():
            if isinstance(value, (int, float)):
                metrics[key] = value

    # From findings
    for f in scan_result.deduplicated_findings:
        if f.metric and f.current_value is not None:
            metrics[f.metric] = f.current_value

    # From scanner-injected merged metrics
    merged = getattr(scan_result, "_merged_metrics", None)
    if merged and isinstance(merged, dict):
        for key, value in merged.items():
            if isinstance(value, (int, float)):
                metrics[key] = value

    return metrics


def check_budget(
    budget: dict[str, Any],
    scan_result: ScanResult,
) -> list[BudgetResult]:
    """Compare scan metrics against budget thresholds.

    Checks both 'metrics' and 'bundles' sections of the budget.

    For most metrics, exceeding the target = failure.
    For rps_at_50_vus, falling BELOW the target = failure (higher is better).

    Args:
        budget: Loaded budget dict from load_budget().
        scan_result: Completed ScanResult.

    Returns:
        List of BudgetResult for each metric that has both a target and a measured value.
    """
    current_metrics = _extract_metrics(scan_result)
    results: list[BudgetResult] = []

    # Metrics where lower is NOT better (higher is better)
    _higher_is_better = {"rps_at_50_vus", "rps"}

    # Process both sections
    for section_key in ("metrics", "bundles"):
        section = budget.get(section_key, {})
        for metric_name, spec in section.items():
            if not isinstance(spec, dict):
                continue

            target = spec.get("target")
            if target is None:
                continue

            # Look up the current value
            current = current_metrics.get(metric_name)
            if current is None:
                continue

            unit = spec.get("unit", "")
            fail_on_exceed = spec.get("fail_on_exceed", True)

            # Determine pass/fail
            if metric_name in _higher_is_better:
                # For throughput metrics: current BELOW target = fail
                passed = current >= target
            else:
                # For latency/size metrics: current ABOVE target = fail
                passed = current <= target

            results.append(
                BudgetResult(
                    metric=metric_name,
                    current=current,
                    target=target,
                    unit=unit,
                    passed=passed,
                    fail_on_exceed=fail_on_exceed,
                )
            )

    return results


def any_budget_failures(results: list[BudgetResult]) -> bool:
    """Return True if any budget metric with fail_on_exceed=True has failed.

    Args:
        results: List of BudgetResult from check_budget().

    Returns:
        True if at least one critical budget metric was exceeded.
    """
    return any(not r.passed and r.fail_on_exceed for r in results)


def all_critical_exceeded(results: list[BudgetResult]) -> bool:
    """Return True if ALL budget metrics with fail_on_exceed=True have failed.

    This triggers exit code 4 — every critical budget metric is blown.

    Args:
        results: List of BudgetResult from check_budget().

    Returns:
        True if every fail_on_exceed metric is exceeded.
    """
    critical = [r for r in results if r.fail_on_exceed]
    if not critical:
        return False
    return all(not r.passed for r in critical)


def scaffold_budget(path: str) -> Path:
    """Create a default budget file at the given path.

    Args:
        path: File path where the budget JSON will be written.

    Returns:
        Path to the created budget file.
    """
    filepath = Path(path)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w") as f:
        json.dump(DEFAULT_BUDGET, f, indent=2)
        f.write("\n")

    return filepath

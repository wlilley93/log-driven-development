"""Normaliser for sitespeed.io output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


class SitespeedNormaliser(BaseNormaliser):
    """Convert sitespeed.io JSON output to Finding objects.

    sitespeed.io produces a budget result JSON at:
      /tmp/viberapid-sitespeed/budget.json
    And a HAR/summary at:
      /tmp/viberapid-sitespeed/data/

    Budget JSON shape:
    {
      "budget": [
        {
          "url": "https://example.com",
          "type": "...",
          "metric": "transferSize",
          "friendlyName": "Total transfer size",
          "limit": 1000000,
          "value": 1200000,
          "status": "failing"
        },
        ...
      ]
    }

    Summary JSON shape (pages summary):
    {
      "statistics": {
        "timings": {
          "firstPaint": { "median": 1200, ... },
          "fullyLoaded": { "median": 4500, ... },
          "pageTimings": { "backEndTime": { "median": 300 }, ... }
        },
        "requests": { "total": 45 },
        "transferSize": { "total": 1500000 }
      }
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []

        # --- Budget violations ---
        budget_items = raw_data.get("budget", [])
        for item in budget_items:
            if not isinstance(item, dict):
                continue
            status = item.get("status", "")
            if status != "failing":
                continue

            url = item.get("url", "<url>")
            metric = item.get("metric", "unknown")
            friendly_name = item.get("friendlyName", metric)
            limit_val = item.get("limit", 0)
            current_val = item.get("value", 0)

            # Determine severity based on how far over budget
            if limit_val > 0:
                ratio = current_val / limit_val
                if ratio > 2.0:
                    severity = Severity.CRITICAL
                elif ratio > 1.5:
                    severity = Severity.HIGH
                elif ratio > 1.2:
                    severity = Severity.MEDIUM
                else:
                    severity = Severity.LOW
            else:
                severity = Severity.MEDIUM

            findings.append(Finding(
                tool="sitespeed",
                severity=severity,
                category=Category.NETWORK,
                file=url,
                rule_id=f"budget-{metric}",
                rule_name=f"Budget violation: {friendly_name}",
                message=f"{friendly_name} is {current_val} (budget: {limit_val}).",
                metric=metric,
                current_value=float(current_val),
                target_value=float(limit_val),
                effort=Effort.MEDIUM,
                fix_hint=f"Reduce {friendly_name} to stay within the configured budget of {limit_val}.",
                saving_estimate=f"Reduce {friendly_name} by {current_val - limit_val}",
                raw=item,
            ))

        # --- Performance summary metrics ---
        statistics = raw_data.get("statistics", {})
        timings = statistics.get("timings", {})

        # First paint
        first_paint = timings.get("firstPaint", {})
        fp_median = first_paint.get("median")
        if fp_median is not None:
            fp_s = fp_median / 1000.0
            if fp_s > 3.0:
                findings.append(Finding(
                    tool="sitespeed",
                    severity=Severity.HIGH if fp_s > 5.0 else Severity.MEDIUM,
                    category=Category.NETWORK,
                    file="<url>",
                    rule_id="first-paint",
                    rule_name="First Paint",
                    message=f"First paint at {fp_s:.1f}s is slow.",
                    metric="first_paint",
                    current_value=round(fp_s, 2),
                    target_value=1.8,
                    effort=Effort.HIGH,
                    fix_hint="Reduce server response time, eliminate render-blocking resources, inline critical CSS.",
                    saving_estimate=f"Reduce first paint from {fp_s:.1f}s to < 1.8s",
                    raw={"firstPaint": first_paint},
                ))

        # Fully loaded
        fully_loaded = timings.get("fullyLoaded", {})
        fl_median = fully_loaded.get("median")
        if fl_median is not None:
            fl_s = fl_median / 1000.0
            if fl_s > 5.0:
                findings.append(Finding(
                    tool="sitespeed",
                    severity=Severity.HIGH if fl_s > 10.0 else Severity.MEDIUM,
                    category=Category.NETWORK,
                    file="<url>",
                    rule_id="fully-loaded",
                    rule_name="Fully Loaded Time",
                    message=f"Page fully loaded in {fl_s:.1f}s.",
                    metric="fully_loaded",
                    current_value=round(fl_s, 2),
                    target_value=5.0,
                    effort=Effort.HIGH,
                    fix_hint="Reduce total page weight, defer non-critical resources, optimise images.",
                    saving_estimate=f"Reduce fully loaded time from {fl_s:.1f}s to < 5s",
                    raw={"fullyLoaded": fully_loaded},
                ))

        return findings

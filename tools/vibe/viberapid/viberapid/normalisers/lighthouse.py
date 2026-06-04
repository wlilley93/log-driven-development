"""Normaliser for Lighthouse audit output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


# Thresholds for core web vitals
_LCP_THRESHOLDS = [
    (4.0, Severity.CRITICAL, "LCP > 4s is a poor experience; users are likely to abandon."),
    (2.5, Severity.HIGH, "LCP between 2.5-4s needs improvement; aim for < 2.5s."),
    (1.8, Severity.MEDIUM, "LCP is acceptable but could be improved."),
]

_CLS_THRESHOLDS = [
    (0.25, Severity.HIGH, "CLS > 0.25 causes significant layout instability."),
    (0.1, Severity.MEDIUM, "CLS between 0.1-0.25 should be improved."),
]

_TBT_THRESHOLDS = [
    (600, Severity.CRITICAL, "TBT > 600ms makes the page feel unresponsive."),
    (300, Severity.HIGH, "TBT between 300-600ms; reduce long tasks to improve interactivity."),
    (200, Severity.MEDIUM, "TBT is acceptable but could be reduced."),
]

_TTI_THRESHOLDS = [
    (7.3, Severity.CRITICAL, "TTI > 7.3s; page takes too long to become interactive."),
    (3.8, Severity.HIGH, "TTI between 3.8-7.3s needs improvement."),
]

_SI_THRESHOLDS = [
    (5.8, Severity.HIGH, "Speed Index > 5.8s; visual load is too slow."),
    (3.4, Severity.MEDIUM, "Speed Index between 3.4-5.8s could be improved."),
]


def _severity_for_metric(value: float, thresholds: list[tuple[float, Severity, str]]) -> tuple[Severity, str] | None:
    """Return severity and message for the first threshold exceeded."""
    for threshold, severity, message in thresholds:
        if value > threshold:
            return severity, message
    return None


class LighthouseNormaliser(BaseNormaliser):
    """Convert Lighthouse JSON output to Finding objects.

    Lighthouse JSON shape (partial):
    {
      "categories": {
        "performance": { "score": 0.85 },
        ...
      },
      "audits": {
        "largest-contentful-paint": { "numericValue": 2300, "score": 0.8, ... },
        "cumulative-layout-shift": { "numericValue": 0.12, ... },
        "total-blocking-time": { "numericValue": 350, ... },
        "interactive": { "numericValue": 4200, ... },
        "speed-index": { "numericValue": 3100, ... },
        "render-blocking-resources": { "details": { "items": [...] }, ... },
        "uses-optimized-images": { "details": { "items": [...] }, ... },
        "uses-long-cache-ttl": { "details": { "items": [...] }, ... },
        ...
      }
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        audits = raw_data.get("audits", {})
        findings: list[Finding] = []

        # --- Core Web Vitals ---

        # LCP (Largest Contentful Paint) - reported in ms, thresholds in seconds
        lcp_audit = audits.get("largest-contentful-paint", {})
        lcp_ms = lcp_audit.get("numericValue")
        if lcp_ms is not None:
            lcp_s = lcp_ms / 1000.0
            result = _severity_for_metric(lcp_s, _LCP_THRESHOLDS)
            if result:
                sev, msg = result
                findings.append(Finding(
                    tool="lighthouse",
                    severity=sev,
                    category=Category.NETWORK,
                    file="<url>",
                    rule_id="lcp",
                    rule_name="Largest Contentful Paint",
                    message=msg,
                    metric="lcp",
                    current_value=round(lcp_s, 2),
                    target_value=2.5,
                    effort=Effort.HIGH,
                    fix_hint="Optimise server response time, preload critical resources, reduce render-blocking CSS/JS.",
                    saving_estimate=f"Reduce LCP from {lcp_s:.1f}s to < 2.5s",
                    raw={"audit": "largest-contentful-paint", "numericValue": lcp_ms},
                ))

        # TBT (Total Blocking Time) - reported in ms
        tbt_audit = audits.get("total-blocking-time", {})
        tbt_ms = tbt_audit.get("numericValue")
        if tbt_ms is not None:
            result = _severity_for_metric(tbt_ms, _TBT_THRESHOLDS)
            if result:
                sev, msg = result
                findings.append(Finding(
                    tool="lighthouse",
                    severity=sev,
                    category=Category.NETWORK,
                    file="<url>",
                    rule_id="tbt",
                    rule_name="Total Blocking Time",
                    message=msg,
                    metric="tbt",
                    current_value=round(tbt_ms, 0),
                    target_value=200,
                    effort=Effort.HIGH,
                    fix_hint="Break up long tasks, defer non-critical JS, use web workers for heavy computation.",
                    saving_estimate=f"Reduce TBT from {tbt_ms:.0f}ms to < 200ms",
                    raw={"audit": "total-blocking-time", "numericValue": tbt_ms},
                ))

        # CLS (Cumulative Layout Shift)
        cls_audit = audits.get("cumulative-layout-shift", {})
        cls_val = cls_audit.get("numericValue")
        if cls_val is not None:
            result = _severity_for_metric(cls_val, _CLS_THRESHOLDS)
            if result:
                sev, msg = result
                findings.append(Finding(
                    tool="lighthouse",
                    severity=sev,
                    category=Category.NETWORK,
                    file="<url>",
                    rule_id="cls",
                    rule_name="Cumulative Layout Shift",
                    message=msg,
                    metric="cls",
                    current_value=round(cls_val, 3),
                    target_value=0.1,
                    effort=Effort.MEDIUM,
                    fix_hint="Set explicit width/height on images/iframes, avoid inserting content above existing content.",
                    saving_estimate=f"Reduce CLS from {cls_val:.3f} to < 0.1",
                    raw={"audit": "cumulative-layout-shift", "numericValue": cls_val},
                ))

        # TTI (Time to Interactive) - reported in ms, thresholds in seconds
        tti_audit = audits.get("interactive", {})
        tti_ms = tti_audit.get("numericValue")
        if tti_ms is not None:
            tti_s = tti_ms / 1000.0
            result = _severity_for_metric(tti_s, _TTI_THRESHOLDS)
            if result:
                sev, msg = result
                findings.append(Finding(
                    tool="lighthouse",
                    severity=sev,
                    category=Category.NETWORK,
                    file="<url>",
                    rule_id="tti",
                    rule_name="Time to Interactive",
                    message=msg,
                    metric="tti",
                    current_value=round(tti_s, 2),
                    target_value=3.8,
                    effort=Effort.HIGH,
                    fix_hint="Reduce JS execution time, minimise main thread work, keep request counts low.",
                    saving_estimate=f"Reduce TTI from {tti_s:.1f}s to < 3.8s",
                    raw={"audit": "interactive", "numericValue": tti_ms},
                ))

        # Speed Index - reported in ms, thresholds in seconds
        si_audit = audits.get("speed-index", {})
        si_ms = si_audit.get("numericValue")
        if si_ms is not None:
            si_s = si_ms / 1000.0
            result = _severity_for_metric(si_s, _SI_THRESHOLDS)
            if result:
                sev, msg = result
                findings.append(Finding(
                    tool="lighthouse",
                    severity=sev,
                    category=Category.NETWORK,
                    file="<url>",
                    rule_id="speed-index",
                    rule_name="Speed Index",
                    message=msg,
                    metric="speed_index",
                    current_value=round(si_s, 2),
                    target_value=3.4,
                    effort=Effort.HIGH,
                    fix_hint="Minimise main-thread work, reduce JavaScript execution time, ensure text remains visible during font load.",
                    saving_estimate=f"Reduce Speed Index from {si_s:.1f}s to < 3.4s",
                    raw={"audit": "speed-index", "numericValue": si_ms},
                ))

        # --- Render-blocking resources ---
        rb_audit = audits.get("render-blocking-resources", {})
        rb_items = rb_audit.get("details", {}).get("items", [])
        if rb_items:
            total_waste_ms = sum(item.get("wastedMs", 0) for item in rb_items)
            findings.append(Finding(
                tool="lighthouse",
                severity=Severity.HIGH if total_waste_ms > 500 else Severity.MEDIUM,
                category=Category.RENDER,
                file="<url>",
                rule_id="render-blocking-resources",
                rule_name="Render-blocking resources",
                message=f"{len(rb_items)} render-blocking resource(s) delaying first paint by ~{total_waste_ms:.0f}ms.",
                metric="render_blocking_waste_ms",
                current_value=round(total_waste_ms, 0),
                target_value=0,
                effort=Effort.MEDIUM,
                fix_hint="Defer non-critical CSS/JS with async/defer, inline critical CSS, use preload for key resources.",
                saving_estimate=f"Eliminate ~{total_waste_ms:.0f}ms of render-blocking time",
                raw={"items": rb_items[:5], "total_waste_ms": total_waste_ms},
            ))

        # --- Unoptimised images ---
        img_audit = audits.get("uses-optimized-images", {})
        img_items = img_audit.get("details", {}).get("items", [])
        if img_items:
            total_waste_bytes = sum(item.get("wastedBytes", 0) for item in img_items)
            total_waste_kb = total_waste_bytes / 1024
            findings.append(Finding(
                tool="lighthouse",
                severity=Severity.HIGH if total_waste_kb > 500 else Severity.MEDIUM,
                category=Category.ASSET,
                file="<url>",
                rule_id="unoptimised-images",
                rule_name="Unoptimised images",
                message=f"{len(img_items)} image(s) could save ~{total_waste_kb:.0f}KB with better compression.",
                metric="image_waste_kb",
                current_value=round(total_waste_kb, 0),
                target_value=0,
                effort=Effort.LOW,
                fix_hint="Convert to WebP/AVIF, resize to actual display dimensions, use responsive srcset.",
                saving_estimate=f"Save ~{total_waste_kb:.0f}KB in image transfer size",
                raw={"items": img_items[:5], "total_waste_bytes": total_waste_bytes},
            ))

        # --- Missing cache headers ---
        cache_audit = audits.get("uses-long-cache-ttl", {})
        cache_items = cache_audit.get("details", {}).get("items", [])
        if cache_items:
            total_waste_bytes = sum(item.get("wastedBytes", 0) for item in cache_items)
            total_waste_kb = total_waste_bytes / 1024
            findings.append(Finding(
                tool="lighthouse",
                severity=Severity.HIGH if len(cache_items) > 10 else Severity.MEDIUM,
                category=Category.CACHE,
                file="<url>",
                rule_id="missing-cache-headers",
                rule_name="Missing or short cache TTL",
                message=f"{len(cache_items)} static asset(s) served without efficient cache policy (~{total_waste_kb:.0f}KB).",
                metric="uncached_assets",
                current_value=len(cache_items),
                target_value=0,
                effort=Effort.LOW,
                fix_hint="Set Cache-Control max-age >= 1 year for hashed assets, use immutable directive.",
                saving_estimate=f"Cache {len(cache_items)} assets to save ~{total_waste_kb:.0f}KB per repeat visit",
                raw={"items": cache_items[:5], "total_waste_bytes": total_waste_bytes},
            ))

        return findings

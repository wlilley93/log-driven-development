"""Normaliser for PageSpeed Insights output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


# CrUX metric thresholds (field data)
_CRUX_THRESHOLDS: dict[str, list[tuple[float, Severity, str]]] = {
    "LARGEST_CONTENTFUL_PAINT_MS": [
        (4000, Severity.CRITICAL, "Field LCP > 4s indicates a poor real-user experience."),
        (2500, Severity.HIGH, "Field LCP 2.5-4s needs improvement; aim for < 2.5s."),
    ],
    "FIRST_INPUT_DELAY_MS": [
        (300, Severity.HIGH, "Field FID > 300ms causes noticeable input lag for real users."),
        (100, Severity.MEDIUM, "Field FID 100-300ms; aim for < 100ms."),
    ],
    "INTERACTION_TO_NEXT_PAINT": [
        (500, Severity.HIGH, "Field INP > 500ms makes interactions feel unresponsive."),
        (200, Severity.MEDIUM, "Field INP 200-500ms; aim for < 200ms."),
    ],
    "CUMULATIVE_LAYOUT_SHIFT_SCORE": [
        (0.25, Severity.HIGH, "Field CLS > 0.25 causes significant layout instability for real users."),
        (0.1, Severity.MEDIUM, "Field CLS 0.1-0.25; aim for < 0.1."),
    ],
    "FIRST_CONTENTFUL_PAINT_MS": [
        (3000, Severity.HIGH, "Field FCP > 3s is slow; users may not perceive the page is loading."),
        (1800, Severity.MEDIUM, "Field FCP 1.8-3s could be improved."),
    ],
    "EXPERIMENTAL_TIME_TO_FIRST_BYTE": [
        (1800, Severity.HIGH, "Field TTFB > 1.8s indicates slow server response for real users."),
        (800, Severity.MEDIUM, "Field TTFB 800ms-1.8s; aim for < 800ms."),
    ],
}

# Human-readable names for CrUX metrics
_CRUX_NAMES: dict[str, tuple[str, str, str]] = {
    # key -> (rule_name, metric_id, unit_label)
    "LARGEST_CONTENTFUL_PAINT_MS": ("CrUX Largest Contentful Paint", "field_lcp", "ms"),
    "FIRST_INPUT_DELAY_MS": ("CrUX First Input Delay", "field_fid", "ms"),
    "INTERACTION_TO_NEXT_PAINT": ("CrUX Interaction to Next Paint", "field_inp", "ms"),
    "CUMULATIVE_LAYOUT_SHIFT_SCORE": ("CrUX Cumulative Layout Shift", "field_cls", ""),
    "FIRST_CONTENTFUL_PAINT_MS": ("CrUX First Contentful Paint", "field_fcp", "ms"),
    "EXPERIMENTAL_TIME_TO_FIRST_BYTE": ("CrUX Time to First Byte", "field_ttfb", "ms"),
}

# Lab audit thresholds (from Lighthouse result embedded in PSI)
_LAB_LCP_THRESHOLDS = [
    (4.0, Severity.CRITICAL, "Lab LCP > 4s is a poor experience; users are likely to abandon."),
    (2.5, Severity.HIGH, "Lab LCP 2.5-4s needs improvement; aim for < 2.5s."),
    (1.8, Severity.MEDIUM, "Lab LCP is acceptable but could be improved."),
]

_LAB_TBT_THRESHOLDS = [
    (600, Severity.CRITICAL, "Lab TBT > 600ms makes the page feel unresponsive."),
    (300, Severity.HIGH, "Lab TBT 300-600ms; reduce long tasks to improve interactivity."),
    (200, Severity.MEDIUM, "Lab TBT is acceptable but could be reduced."),
]

_LAB_CLS_THRESHOLDS = [
    (0.25, Severity.HIGH, "Lab CLS > 0.25 causes significant layout instability."),
    (0.1, Severity.MEDIUM, "Lab CLS 0.1-0.25 should be improved."),
]

_LAB_FCP_THRESHOLDS = [
    (3.0, Severity.HIGH, "Lab FCP > 3s; page takes too long to show first content."),
    (1.8, Severity.MEDIUM, "Lab FCP 1.8-3s could be improved."),
]

_LAB_SI_THRESHOLDS = [
    (5.8, Severity.HIGH, "Lab Speed Index > 5.8s; visual load is too slow."),
    (3.4, Severity.MEDIUM, "Lab Speed Index 3.4-5.8s could be improved."),
]


def _severity_for_metric(value: float, thresholds: list[tuple[float, Severity, str]]) -> tuple[Severity, str] | None:
    """Return severity and message for the first threshold exceeded."""
    for threshold, severity, message in thresholds:
        if value > threshold:
            return severity, message
    return None


def _fix_hint_for_crux(metric_key: str) -> str:
    """Return a fix hint for a CrUX metric."""
    hints = {
        "LARGEST_CONTENTFUL_PAINT_MS": (
            "Optimise server response time, preload the LCP resource, "
            "compress images (WebP/AVIF), and reduce render-blocking CSS/JS."
        ),
        "FIRST_INPUT_DELAY_MS": (
            "Break up long tasks, defer non-critical JavaScript, "
            "use web workers for heavy computation."
        ),
        "INTERACTION_TO_NEXT_PAINT": (
            "Reduce JavaScript execution time, yield to the main thread frequently, "
            "and minimise DOM size to improve input responsiveness."
        ),
        "CUMULATIVE_LAYOUT_SHIFT_SCORE": (
            "Set explicit width/height on images and iframes, avoid inserting "
            "content above existing content, use CSS contain where appropriate."
        ),
        "FIRST_CONTENTFUL_PAINT_MS": (
            "Reduce server response time, eliminate render-blocking resources, "
            "inline critical CSS, and preload key requests."
        ),
        "EXPERIMENTAL_TIME_TO_FIRST_BYTE": (
            "Optimise server-side processing, use a CDN, enable caching, "
            "and reduce redirect chains."
        ),
    }
    return hints.get(metric_key, "Review PageSpeed Insights recommendations.")


class PSINormaliser(BaseNormaliser):
    """Convert PageSpeed Insights JSON output to Finding objects.

    PSI JSON shape (partial):
    {
      "loadingExperience": {
        "overall_category": "SLOW" | "AVERAGE" | "FAST",
        "metrics": {
          "LARGEST_CONTENTFUL_PAINT_MS": {
            "percentile": 3200,
            "category": "SLOW"
          },
          "CUMULATIVE_LAYOUT_SHIFT_SCORE": {
            "percentile": 0.15,
            "category": "NEEDS_IMPROVEMENT"
          },
          ...
        }
      },
      "lighthouseResult": {
        "categories": { "performance": { "score": 0.72 } },
        "audits": {
          "largest-contentful-paint": { "numericValue": 2800, "score": 0.65 },
          "total-blocking-time": { "numericValue": 450, ... },
          "cumulative-layout-shift": { "numericValue": 0.12, ... },
          "first-contentful-paint": { "numericValue": 1900, ... },
          "speed-index": { "numericValue": 3200, ... },
          "render-blocking-resources": { "details": { "items": [...] } },
          "unused-javascript": { "details": { "items": [...] } },
          ...
        }
      }
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []

        # --- CrUX Field Data ---
        loading_exp = raw_data.get("loadingExperience", {})
        field_metrics = loading_exp.get("metrics", {})

        for metric_key, thresholds in _CRUX_THRESHOLDS.items():
            metric_data = field_metrics.get(metric_key, {})
            percentile = metric_data.get("percentile")
            if percentile is None:
                continue

            result = _severity_for_metric(percentile, thresholds)
            if result is None:
                continue

            sev, msg = result
            names = _CRUX_NAMES.get(metric_key)
            if not names:
                continue

            rule_name, metric_id, unit = names
            category_label = metric_data.get("category", "UNKNOWN")

            # Determine target value from the first (best) threshold
            target_val = thresholds[-1][0] if thresholds else percentile

            findings.append(Finding(
                tool="psi",
                severity=sev,
                category=Category.NETWORK,
                file="<url>",
                rule_id=f"crux-{metric_id}",
                rule_name=rule_name,
                message=f"{msg} (p75={percentile}{unit}, category={category_label})",
                metric=metric_id,
                current_value=float(percentile),
                target_value=float(target_val),
                effort=Effort.HIGH,
                fix_hint=_fix_hint_for_crux(metric_key),
                saving_estimate=f"Improve {rule_name} from {percentile}{unit} to < {target_val}{unit}",
                raw={"metric": metric_key, "percentile": percentile, "category": category_label},
            ))

        # --- Lab Data (from embedded Lighthouse result) ---
        lighthouse = raw_data.get("lighthouseResult", {})
        audits = lighthouse.get("audits", {})

        # Lab LCP
        lcp_audit = audits.get("largest-contentful-paint", {})
        lcp_ms = lcp_audit.get("numericValue")
        if lcp_ms is not None:
            lcp_s = lcp_ms / 1000.0
            result = _severity_for_metric(lcp_s, _LAB_LCP_THRESHOLDS)
            if result:
                sev, msg = result
                findings.append(Finding(
                    tool="psi",
                    severity=sev,
                    category=Category.NETWORK,
                    file="<url>",
                    rule_id="lab-lcp",
                    rule_name="Lab Largest Contentful Paint",
                    message=msg,
                    metric="lab_lcp",
                    current_value=round(lcp_s, 2),
                    target_value=2.5,
                    effort=Effort.HIGH,
                    fix_hint="Optimise server response time, preload critical resources, reduce render-blocking CSS/JS.",
                    saving_estimate=f"Reduce lab LCP from {lcp_s:.1f}s to < 2.5s",
                    raw={"audit": "largest-contentful-paint", "numericValue": lcp_ms},
                ))

        # Lab TBT
        tbt_audit = audits.get("total-blocking-time", {})
        tbt_ms = tbt_audit.get("numericValue")
        if tbt_ms is not None:
            result = _severity_for_metric(tbt_ms, _LAB_TBT_THRESHOLDS)
            if result:
                sev, msg = result
                findings.append(Finding(
                    tool="psi",
                    severity=sev,
                    category=Category.NETWORK,
                    file="<url>",
                    rule_id="lab-tbt",
                    rule_name="Lab Total Blocking Time",
                    message=msg,
                    metric="lab_tbt",
                    current_value=round(tbt_ms, 0),
                    target_value=200,
                    effort=Effort.HIGH,
                    fix_hint="Break up long tasks, defer non-critical JS, use web workers for heavy computation.",
                    saving_estimate=f"Reduce lab TBT from {tbt_ms:.0f}ms to < 200ms",
                    raw={"audit": "total-blocking-time", "numericValue": tbt_ms},
                ))

        # Lab CLS
        cls_audit = audits.get("cumulative-layout-shift", {})
        cls_val = cls_audit.get("numericValue")
        if cls_val is not None:
            result = _severity_for_metric(cls_val, _LAB_CLS_THRESHOLDS)
            if result:
                sev, msg = result
                findings.append(Finding(
                    tool="psi",
                    severity=sev,
                    category=Category.NETWORK,
                    file="<url>",
                    rule_id="lab-cls",
                    rule_name="Lab Cumulative Layout Shift",
                    message=msg,
                    metric="lab_cls",
                    current_value=round(cls_val, 3),
                    target_value=0.1,
                    effort=Effort.MEDIUM,
                    fix_hint="Set explicit width/height on images/iframes, avoid inserting content above existing content.",
                    saving_estimate=f"Reduce lab CLS from {cls_val:.3f} to < 0.1",
                    raw={"audit": "cumulative-layout-shift", "numericValue": cls_val},
                ))

        # Lab FCP
        fcp_audit = audits.get("first-contentful-paint", {})
        fcp_ms = fcp_audit.get("numericValue")
        if fcp_ms is not None:
            fcp_s = fcp_ms / 1000.0
            result = _severity_for_metric(fcp_s, _LAB_FCP_THRESHOLDS)
            if result:
                sev, msg = result
                findings.append(Finding(
                    tool="psi",
                    severity=sev,
                    category=Category.NETWORK,
                    file="<url>",
                    rule_id="lab-fcp",
                    rule_name="Lab First Contentful Paint",
                    message=msg,
                    metric="lab_fcp",
                    current_value=round(fcp_s, 2),
                    target_value=1.8,
                    effort=Effort.HIGH,
                    fix_hint="Reduce server response time, eliminate render-blocking resources, inline critical CSS.",
                    saving_estimate=f"Reduce lab FCP from {fcp_s:.1f}s to < 1.8s",
                    raw={"audit": "first-contentful-paint", "numericValue": fcp_ms},
                ))

        # Lab Speed Index
        si_audit = audits.get("speed-index", {})
        si_ms = si_audit.get("numericValue")
        if si_ms is not None:
            si_s = si_ms / 1000.0
            result = _severity_for_metric(si_s, _LAB_SI_THRESHOLDS)
            if result:
                sev, msg = result
                findings.append(Finding(
                    tool="psi",
                    severity=sev,
                    category=Category.NETWORK,
                    file="<url>",
                    rule_id="lab-speed-index",
                    rule_name="Lab Speed Index",
                    message=msg,
                    metric="lab_speed_index",
                    current_value=round(si_s, 2),
                    target_value=3.4,
                    effort=Effort.HIGH,
                    fix_hint="Minimise main-thread work, reduce JavaScript execution time, ensure text remains visible during font load.",
                    saving_estimate=f"Reduce lab Speed Index from {si_s:.1f}s to < 3.4s",
                    raw={"audit": "speed-index", "numericValue": si_ms},
                ))

        # --- Unused JavaScript ---
        unused_js = audits.get("unused-javascript", {})
        unused_js_items = unused_js.get("details", {}).get("items", [])
        if unused_js_items:
            total_waste_bytes = sum(item.get("wastedBytes", 0) for item in unused_js_items)
            total_waste_kb = total_waste_bytes / 1024
            findings.append(Finding(
                tool="psi",
                severity=Severity.HIGH if total_waste_kb > 200 else Severity.MEDIUM,
                category=Category.NETWORK,
                file="<url>",
                rule_id="unused-javascript",
                rule_name="Unused JavaScript",
                message=f"{len(unused_js_items)} script(s) contain ~{total_waste_kb:.0f}KB of unused code.",
                metric="unused_js_kb",
                current_value=round(total_waste_kb, 0),
                target_value=0,
                effort=Effort.MEDIUM,
                fix_hint="Use code splitting, tree-shake unused exports, lazy-load non-critical scripts.",
                saving_estimate=f"Remove ~{total_waste_kb:.0f}KB of unused JavaScript",
                raw={"items": unused_js_items[:5], "total_waste_bytes": total_waste_bytes},
            ))

        # --- Render-blocking resources ---
        rb_audit = audits.get("render-blocking-resources", {})
        rb_items = rb_audit.get("details", {}).get("items", [])
        if rb_items:
            total_waste_ms = sum(item.get("wastedMs", 0) for item in rb_items)
            findings.append(Finding(
                tool="psi",
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

        return findings

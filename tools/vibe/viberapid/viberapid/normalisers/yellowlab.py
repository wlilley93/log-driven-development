"""Normaliser for Yellow Lab Tools output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


# Map Yellow Lab rule policies to severity.
# YLT scores rules 0-100 and assigns grades: A (best) through F (worst).
# The "bad" flag indicates if a rule failed its threshold.
_GRADE_SEVERITY = {
    "F": Severity.CRITICAL,
    "E": Severity.HIGH,
    "D": Severity.MEDIUM,
    "C": Severity.LOW,
    "B": Severity.INFO,
    "A": Severity.INFO,
}

# Map YLT policy categories to our Category + Effort
_CATEGORY_MAP: dict[str, tuple[Category, Effort]] = {
    "pageWeight": (Category.NETWORK, Effort.MEDIUM),
    "requests": (Category.NETWORK, Effort.MEDIUM),
    "domComplexity": (Category.RENDER, Effort.HIGH),
    "cssComplexity": (Category.CSS, Effort.MEDIUM),
    "javascriptComplexity": (Category.CODE, Effort.HIGH),
    "badJavascript": (Category.CODE, Effort.MEDIUM),
    "jQuery": (Category.CODE, Effort.MEDIUM),
    "fontsCount": (Category.FONT, Effort.LOW),
    "serverConfig": (Category.NETWORK, Effort.LOW),
    "images": (Category.ASSET, Effort.LOW),
    "caching": (Category.CACHE, Effort.LOW),
}

# Actionable fix hints per YLT rule category
_FIX_HINTS: dict[str, str] = {
    "pageWeight": "Reduce page weight by compressing assets, using modern image formats (WebP/AVIF), and removing unused code.",
    "requests": "Reduce the number of HTTP requests by bundling assets, inlining critical resources, and lazy-loading non-critical ones.",
    "domComplexity": "Simplify the DOM structure: reduce nesting depth, remove unnecessary wrapper elements, and virtualise long lists.",
    "cssComplexity": "Simplify CSS: reduce selector specificity, remove unused rules (PurgeCSS), and avoid deeply nested selectors.",
    "javascriptComplexity": "Reduce JavaScript complexity: split large bundles, defer non-critical scripts, and remove unused code.",
    "badJavascript": "Fix JavaScript anti-patterns: avoid document.write, synchronous XHR, and excessive global variables.",
    "jQuery": "Consider replacing jQuery with native APIs (querySelector, fetch, classList) to reduce bundle size.",
    "fontsCount": "Reduce web font usage: limit font families, use font-display:swap, and subset fonts to required characters.",
    "serverConfig": "Optimise server configuration: enable compression (gzip/brotli), set proper cache headers, and use HTTP/2.",
    "images": "Optimise images: use responsive srcset, compress with WebP/AVIF, and lazy-load off-screen images.",
    "caching": "Improve caching: set long Cache-Control max-age for hashed assets, use immutable directive, and add ETags.",
}


def _saving_estimate_for_rule(rule_id: str, value: Any, abnormal_threshold: Any) -> str:
    """Generate a saving estimate based on the rule and current/threshold values."""
    if isinstance(value, (int, float)) and isinstance(abnormal_threshold, (int, float)):
        if "weight" in rule_id.lower() or "size" in rule_id.lower():
            if value > 1024:
                return f"Reduce from {value / 1024:.0f}KB to < {abnormal_threshold / 1024:.0f}KB"
            return f"Reduce from {value} to < {abnormal_threshold}"
        if "count" in rule_id.lower() or "requests" in rule_id.lower():
            return f"Reduce from {value} to < {abnormal_threshold}"
        return f"Improve from {value} to < {abnormal_threshold}"
    return f"Improve metric '{rule_id}' to meet threshold"


class YellowLabNormaliser(BaseNormaliser):
    """Convert Yellow Lab Tools JSON output to Finding objects.

    Yellow Lab Tools JSON shape (partial):
    {
      "scoreProfiles": {
        "generic": {
          "globalScore": 72,
          "categories": {
            "pageWeight": { "categoryScore": 65 },
            "requests": { "categoryScore": 80 },
            "domComplexity": { "categoryScore": 45 },
            ...
          }
        }
      },
      "rules": {
        "totalWeight": {
          "value": 2500000,
          "score": 45,
          "bad": true,
          "abnormal": false,
          "policy": {
            "tool": "phantomas",
            "label": "Total page weight",
            "message": "...",
            "isOkThreshold": 1000000,
            "isBadThreshold": 3000000,
            "isAbnormalThreshold": 10000000
          },
          "offenders": [ ... ]
        },
        "DOMelementsCount": {
          "value": 2500,
          "score": 30,
          "bad": true,
          ...
        },
        ...
      },
      "toolsResults": { ... }
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        rules = raw_data.get("rules", {})
        findings: list[Finding] = []

        for rule_id, rule_data in rules.items():
            if not isinstance(rule_data, dict):
                continue

            score = rule_data.get("score")
            value = rule_data.get("value")
            is_bad = rule_data.get("bad", False)
            is_abnormal = rule_data.get("abnormal", False)
            policy = rule_data.get("policy", {})
            offenders = rule_data.get("offenders", [])

            # Only report rules that are below threshold (bad or abnormal) or have low scores
            if not is_bad and not is_abnormal and (score is None or score >= 80):
                continue

            # Determine severity from score
            if is_abnormal:
                severity = Severity.CRITICAL
            elif score is not None:
                if score < 20:
                    severity = Severity.CRITICAL
                elif score < 40:
                    severity = Severity.HIGH
                elif score < 60:
                    severity = Severity.MEDIUM
                elif score < 80:
                    severity = Severity.LOW
                else:
                    continue  # Score >= 80 is acceptable
            elif is_bad:
                severity = Severity.HIGH
            else:
                severity = Severity.MEDIUM

            # Extract policy metadata
            label = policy.get("label", rule_id)
            policy_message = policy.get("message", "")
            is_ok_threshold = policy.get("isOkThreshold")
            is_bad_threshold = policy.get("isBadThreshold")

            # Determine category and effort from the rule's scoring category
            # Walk the score profiles to find which category this rule belongs to
            rule_category_name = self._find_rule_category(raw_data, rule_id)
            cat, effort = _CATEGORY_MAP.get(rule_category_name, (Category.NETWORK, Effort.MEDIUM))

            # Build message
            message_parts = [label]
            if policy_message:
                message_parts.append(policy_message)
            if value is not None:
                message_parts.append(f"Current value: {value}")
            if score is not None:
                message_parts.append(f"Score: {score}/100")
            message = ". ".join(str(p) for p in message_parts) + "."

            # Fix hint
            fix_hint = _FIX_HINTS.get(rule_category_name, f"Review and optimise '{label}' per Yellow Lab Tools recommendations.")

            # Saving estimate
            target = is_ok_threshold if is_ok_threshold is not None else is_bad_threshold
            saving = _saving_estimate_for_rule(rule_id, value, target)

            findings.append(Finding(
                tool="yellowlab",
                severity=severity,
                category=cat,
                file="<url>",
                rule_id=f"ylt-{rule_id}",
                rule_name=label,
                message=message,
                metric=rule_id,
                current_value=float(value) if isinstance(value, (int, float)) else None,
                target_value=float(target) if isinstance(target, (int, float)) else None,
                effort=effort,
                fix_hint=fix_hint,
                saving_estimate=saving,
                raw={
                    "rule": rule_id,
                    "value": value,
                    "score": score,
                    "bad": is_bad,
                    "abnormal": is_abnormal,
                    "offenders": offenders[:5] if isinstance(offenders, list) else [],
                },
            ))

        return findings

    @staticmethod
    def _find_rule_category(data: dict, rule_id: str) -> str:
        """Find which YLT category a rule belongs to by walking the score profiles."""
        categories = (
            data.get("scoreProfiles", {})
            .get("generic", {})
            .get("categories", {})
        )
        for cat_name, cat_data in categories.items():
            if not isinstance(cat_data, dict):
                continue
            rules_in_cat = cat_data.get("rules", [])
            if isinstance(rules_in_cat, list) and rule_id in rules_in_cat:
                return cat_name
            # Some versions use a dict of rule references
            if isinstance(rules_in_cat, dict) and rule_id in rules_in_cat:
                return cat_name
        return "pageWeight"  # default fallback

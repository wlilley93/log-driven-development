"""Cross-tool deduplication — exact match and near match."""

from __future__ import annotations

from typing import Any

from viberapid.models import Finding, Severity


def deduplicate(
    findings: list[Finding],
    near_line_threshold: int = 3,
) -> tuple[list[Finding], dict[str, Any]]:
    """Deduplicate findings from multiple tools.

    Two dedup strategies:
    1. Exact match: same file + same line + same rule_id
    2. Near match: same file + same category + line within ±near_line_threshold

    Duplicates are merged — the highest severity is kept, and all contributing
    tool names are recorded in `finding.tools`.

    Args:
        findings: Raw findings from all tools.
        near_line_threshold: Max line distance for near-match dedup.

    Returns:
        Tuple of (deduplicated findings sorted by severity desc, overlap stats dict).
    """
    if not findings:
        return [], {}

    # ------------------------------------------------------------------
    # Phase 1: Exact match dedup (file + line + rule_id)
    # ------------------------------------------------------------------
    exact_groups: dict[str, list[Finding]] = {}

    for f in findings:
        key = f"{f.file}:{f.line}:{f.rule_id}"
        if key not in exact_groups:
            exact_groups[key] = []
        exact_groups[key].append(f)

    # Merge exact duplicates: keep the highest severity, collect tool names
    exact_merged: list[Finding] = []
    exact_dup_count = 0

    for key, group in exact_groups.items():
        if len(group) == 1:
            primary = group[0]
            primary.tools = [primary.tool]
            exact_merged.append(primary)
        else:
            # Sort by severity descending — keep the most severe
            group.sort(key=lambda f: f.severity.rank, reverse=True)
            primary = group[0]
            primary.tools = list({f.tool for f in group})
            primary.duplicate_group = key
            for secondary in group[1:]:
                secondary.is_duplicate = True
                secondary.duplicate_group = key
                exact_dup_count += 1
                # Carry forward the best fix_hint / saving_estimate
                if not primary.fix_hint and secondary.fix_hint:
                    primary.fix_hint = secondary.fix_hint
                if not primary.saving_estimate and secondary.saving_estimate:
                    primary.saving_estimate = secondary.saving_estimate
            exact_merged.append(primary)

    # ------------------------------------------------------------------
    # Phase 2: Near match dedup (file + category + line ± threshold)
    # ------------------------------------------------------------------
    near_dup_count = 0
    final: list[Finding] = []
    consumed: set[int] = set()

    # Index by (file, category) for efficient near-match lookup
    bucket: dict[tuple[str, str], list[tuple[int, Finding]]] = {}
    for idx, f in enumerate(exact_merged):
        bkey = (f.file, f.category.value)
        if bkey not in bucket:
            bucket[bkey] = []
        bucket[bkey].append((idx, f))

    for bkey, items in bucket.items():
        # Sort by line number for proximity checks
        items.sort(key=lambda x: x[1].line or 0)

        for i, (idx_a, fa) in enumerate(items):
            if idx_a in consumed:
                continue

            near_group = [fa]

            for j in range(i + 1, len(items)):
                idx_b, fb = items[j]
                if idx_b in consumed:
                    continue

                line_a = fa.line or 0
                line_b = fb.line or 0

                if abs(line_a - line_b) <= near_line_threshold:
                    # Same file + same category + close lines = near dup
                    near_group.append(fb)
                    consumed.add(idx_b)
                    near_dup_count += 1

            consumed.add(idx_a)

            if len(near_group) == 1:
                final.append(near_group[0])
            else:
                # Merge near matches — keep highest severity
                near_group.sort(key=lambda f: f.severity.rank, reverse=True)
                primary = near_group[0]
                for secondary in near_group[1:]:
                    for t in secondary.tools or [secondary.tool]:
                        if t not in (primary.tools or []):
                            primary.tools.append(t)
                    if not primary.fix_hint and secondary.fix_hint:
                        primary.fix_hint = secondary.fix_hint
                    if not primary.saving_estimate and secondary.saving_estimate:
                        primary.saving_estimate = secondary.saving_estimate
                final.append(primary)

    # ------------------------------------------------------------------
    # Sort by severity descending (CRITICAL first), then by file
    # ------------------------------------------------------------------
    final.sort(key=lambda f: (-f.severity.rank, f.file, f.line or 0))

    # ------------------------------------------------------------------
    # Overlap stats
    # ------------------------------------------------------------------
    tool_finding_counts: dict[str, int] = {}
    for f in findings:
        tool_finding_counts[f.tool] = tool_finding_counts.get(f.tool, 0) + 1

    multi_tool_findings = sum(1 for f in final if len(f.tools) > 1)

    overlap: dict[str, Any] = {
        "total_raw": len(findings),
        "exact_duplicates_removed": exact_dup_count,
        "near_duplicates_removed": near_dup_count,
        "total_after_dedup": len(final),
        "multi_tool_findings": multi_tool_findings,
        "tool_finding_counts": tool_finding_counts,
    }

    return final, overlap

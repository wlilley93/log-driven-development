"""Cross-tool finding deduplication."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from vibescan.models import Category, Finding


def deduplicate(findings: list[Finding]) -> tuple[list[Finding], dict[str, Any]]:
    """Deduplicate findings across tools.

    Returns (deduplicated_findings, tool_overlap_summary).
    """
    if not findings:
        return [], {}

    deduped: list[Finding] = []
    seen_exact: dict[str, Finding] = {}
    cve_groups: dict[str, list[Finding]] = defaultdict(list)
    near_groups: dict[str, list[Finding]] = defaultdict(list)

    # Phase 1: CVE dedup — same CVE ID regardless of tool
    cve_findings = [f for f in findings if f.cve]
    non_cve_findings = [f for f in findings if not f.cve]

    for f in cve_findings:
        cve_groups[f.cve].append(f)

    for cve_id, group in cve_groups.items():
        best = max(group, key=lambda f: f.severity.rank)
        best.tools = list({f.tool for f in group})
        if len(group) > 1:
            best.is_duplicate = True
            best.duplicate_group = f"cve:{cve_id}"
        deduped.append(best)

    # Phase 2: Exact match — same file + line + rule_id
    for f in non_cve_findings:
        exact_key = f"{f.file}:{f.line}:{f.rule_id}"
        if exact_key in seen_exact:
            existing = seen_exact[exact_key]
            if f.severity.rank > existing.severity.rank:
                existing.severity = f.severity
            existing.tools = list(set(existing.tools) | {f.tool})
            existing.is_duplicate = True
            existing.duplicate_group = f"exact:{exact_key}"
        else:
            f.tools = [f.tool]
            seen_exact[exact_key] = f

    # Phase 3: Near-match — same file, line ±3, same category
    exact_list = list(seen_exact.values())
    for f in exact_list:
        near_key = f"{f.file}:{f.category.value}:{(f.line or 0) // 6}"
        near_groups[near_key].append(f)

    for _key, group in near_groups.items():
        if len(group) > 1:
            group_id = f"near:{group[0].file}:{group[0].line}"
            for f in group:
                f.duplicate_group = f.duplicate_group or group_id

    deduped.extend(exact_list)

    # Sort: highest severity first, then by file/line
    deduped.sort(key=lambda f: (-f.severity.rank, f.file, f.line or 0))

    overlap = _compute_overlap(findings)

    return deduped, overlap


def _compute_overlap(findings: list[Finding]) -> dict[str, Any]:
    """Compute tool overlap statistics."""
    tool_findings: dict[str, set[str]] = defaultdict(set)
    tool_pair_overlap: dict[tuple[str, str], int] = defaultdict(int)

    for f in findings:
        key = f"{f.file}:{f.line}:{f.category.value}"
        tool_findings[f.tool].add(key)

    tools = sorted(tool_findings.keys())
    for i, t1 in enumerate(tools):
        for t2 in tools[i + 1 :]:
            shared = tool_findings[t1] & tool_findings[t2]
            if shared:
                tool_pair_overlap[(t1, t2)] = len(shared)

    # CVE-specific overlap
    cve_tools: dict[str, set[str]] = defaultdict(set)
    for f in findings:
        if f.cve:
            cve_tools[f.cve].add(f.tool)

    cve_overlap = {}
    multi_tool_cves = {cve: ts for cve, ts in cve_tools.items() if len(ts) > 1}
    if multi_tool_cves:
        # Compute unique counts per tool
        all_cve_tools = set()
        for ts in multi_tool_cves.values():
            all_cve_tools.update(ts)

        for tool in sorted(all_cve_tools):
            tool_cves = {cve for cve, ts in cve_tools.items() if tool in ts}
            other_cves = {cve for cve, ts in cve_tools.items() if tool not in ts and len(ts) > 0}
            shared = {cve for cve, ts in multi_tool_cves.items() if tool in ts}
            unique = tool_cves - {cve for cve, ts in multi_tool_cves.items()}
            cve_overlap[tool] = {
                "total": len(tool_cves),
                "shared": len(shared),
                "unique": len(unique),
            }

    return {
        "pair_overlap": {f"{t1}+{t2}": count for (t1, t2), count in tool_pair_overlap.items()},
        "cve_overlap": cve_overlap,
        "total_raw": len(findings),
        "total_deduplicated": len(set(f.id for f in findings)),
    }

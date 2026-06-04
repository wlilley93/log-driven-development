"""Generate fix commands and priority ordering for findings."""

from __future__ import annotations

from vibedeploy.models import Finding, Effort


def generate_fixes(findings: list[Finding]) -> list[dict]:
    """Generate a prioritised list of fix actions from findings.

    Returns list of dicts with: finding_id, rule_id, fix_command, fix_hint,
    effort, priority, blocks_deploy.
    """
    fixes = []

    for f in findings:
        if not f.fix_command and not f.fix_hint:
            continue

        fixes.append({
            "finding_id": f.id,
            "rule_id": f.rule_id,
            "tool": f.tool,
            "file": f.file,
            "line": f.line,
            "message": f.message,
            "severity": f.severity.value,
            "blocks_deploy": f.blocks_deploy,
            "effort": f.effort.value,
            "fix_command": f.fix_command,
            "fix_hint": f.fix_hint,
            "docs_url": f.docs_url,
        })

    # Sort: blockers first, then by severity rank desc, then by effort asc
    effort_rank = {
        Effort.TRIVIAL: 0,
        Effort.LOW: 1,
        Effort.MEDIUM: 2,
        Effort.HIGH: 3,
        Effort.UNKNOWN: 4,
    }

    severity_rank = {
        "CRITICAL": 4,
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1,
        "INFO": 0,
    }

    fixes.sort(
        key=lambda x: (
            -int(x["blocks_deploy"]),
            -severity_rank.get(x["severity"], 0),
            effort_rank.get(Effort(x["effort"]), 4),
        )
    )

    # Add priority numbers
    for i, fix in enumerate(fixes):
        fix["priority"] = i + 1

    return fixes

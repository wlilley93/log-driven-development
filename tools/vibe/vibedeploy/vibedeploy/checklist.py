"""Render findings as a markdown pre-deploy checklist."""

from __future__ import annotations

from vibedeploy.models import Finding, ScanResult, Severity


def render_checklist(result: ScanResult) -> str:
    """Generate a markdown pre-deploy checklist from scan results."""
    lines: list[str] = []
    lines.append("# Pre-Deploy Checklist")
    lines.append("")
    lines.append(f"**Target**: {result.target}")
    lines.append(f"**Scanned**: {result.timestamp}")
    lines.append(f"**Readiness Score**: {result.readiness_score}/100")
    lines.append("")

    # Deploy blockers section
    blockers = result.deploy_blockers
    if blockers:
        lines.append(f"## Deploy Blockers ({len(blockers)})")
        lines.append("")
        lines.append("These MUST be resolved before deploying:")
        lines.append("")
        for f in blockers:
            _append_checklist_item(lines, f)
        lines.append("")

    # By severity
    for sev in (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO):
        sev_findings = [
            f for f in result.deduplicated_findings
            if f.severity == sev and not f.blocks_deploy
        ]
        if not sev_findings:
            continue

        lines.append(f"## {sev.value} ({len(sev_findings)})")
        lines.append("")
        for f in sev_findings:
            _append_checklist_item(lines, f)
        lines.append("")

    if not result.deduplicated_findings:
        lines.append("All clear — no findings detected. Ship it!")
        lines.append("")

    return "\n".join(lines)


def _append_checklist_item(lines: list[str], f: Finding) -> None:
    """Append a single checklist item."""
    location = f.file
    if f.line:
        location += f":{f.line}"

    lines.append(f"- [ ] **[{f.tool}]** {f.message}")
    lines.append(f"  - Location: `{location}`")
    if f.fix_hint:
        lines.append(f"  - Fix: {f.fix_hint}")
    if f.fix_command:
        lines.append(f"  - Command: `{f.fix_command}`")
    if f.docs_url:
        lines.append(f"  - Docs: {f.docs_url}")

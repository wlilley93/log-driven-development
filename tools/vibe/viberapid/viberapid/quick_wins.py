"""Quick wins engine — rank findings by ROI (severity * effort) and return top N."""

from __future__ import annotations

from viberapid.models import Finding


def compute_quick_wins(
    findings: list[Finding],
    top_n: int = 5,
) -> list[Finding]:
    """Sort findings by quick_win_score descending and return the top N.

    The quick_win_score property on Finding computes:
        severity_weight * effort_weight

    where high severity and low effort yield the highest score (best ROI).

    Args:
        findings: Deduplicated findings list.
        top_n: Number of quick wins to return.

    Returns:
        Top N findings ordered by quick_win_score descending.
    """
    if not findings:
        return []

    # Sort by quick_win_score descending, then severity descending as tiebreaker
    ranked = sorted(
        findings,
        key=lambda f: (f.quick_win_score, f.severity.rank),
        reverse=True,
    )

    return ranked[:top_n]

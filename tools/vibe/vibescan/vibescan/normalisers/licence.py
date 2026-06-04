"""Normaliser for licence scanning output."""

from __future__ import annotations

from typing import Any

from vibescan.models import Category, Finding, Severity
from vibescan.normalisers.base import BaseNormaliser

# Default blocklist of copyleft / problematic licences
DEFAULT_LICENCE_BLOCKLIST: set[str] = {
    "GPL-2.0",
    "GPL-2.0-only",
    "GPL-2.0-or-later",
    "GPL-3.0",
    "GPL-3.0-only",
    "GPL-3.0-or-later",
    "AGPL-1.0",
    "AGPL-3.0",
    "AGPL-3.0-only",
    "AGPL-3.0-or-later",
    "SSPL-1.0",
    "EUPL-1.1",
    "EUPL-1.2",
    "CPAL-1.0",
    "OSL-3.0",
    "CPOL-1.02",
    "UNKNOWN",
}


class LicenceNormaliser(BaseNormaliser):
    """Transform licence scan output into normalised Findings.

    Input: dict with "npm" and/or "pip" keys, each containing a list
    of {name, version, license}.

    Args:
        blocklist: Set of licence identifiers to flag as HIGH severity.
                   Defaults to DEFAULT_LICENCE_BLOCKLIST.
    """

    tool_name = "licence-scan"

    def __init__(self, blocklist: set[str] | None = None) -> None:
        self.blocklist = blocklist if blocklist is not None else DEFAULT_LICENCE_BLOCKLIST

    def _is_blocked(self, licence_str: str) -> bool:
        """Check if a licence string matches any entry in the blocklist."""
        if not licence_str:
            return True  # Unknown/empty licence is blocked
        normalised = licence_str.strip().upper()
        return normalised in {b.upper() for b in self.blocklist}

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []

        ecosystem_files = {
            "npm": "package.json",
            "pip": "requirements.txt",
        }

        for ecosystem, manifest_file in ecosystem_files.items():
            packages = raw_data.get(ecosystem, [])
            if not isinstance(packages, list):
                continue

            for pkg in packages:
                if not isinstance(pkg, dict):
                    continue

                pkg_name = pkg.get("name", "unknown")
                pkg_version = pkg.get("version", "")
                licence_str = pkg.get("license", "") or pkg.get("licence", "")

                if not isinstance(licence_str, str):
                    licence_str = str(licence_str)

                blocked = self._is_blocked(licence_str)
                severity = Severity.HIGH if blocked else Severity.MEDIUM

                display_licence = licence_str if licence_str else "UNKNOWN"
                message = f"{pkg_name}@{pkg_version} uses licence: {display_licence}"
                if blocked:
                    message = f"{message} (blocklisted)"

                findings.append(
                    Finding(
                        tool=self.tool_name,
                        severity=severity,
                        category=Category.LICENCE,
                        file=manifest_file,
                        rule_id=display_licence,
                        rule_name=f"licence-{display_licence}",
                        message=message,
                        licence=licence_str if licence_str else None,
                        raw=pkg,
                    )
                )

        return findings

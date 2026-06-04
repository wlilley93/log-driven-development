"""Normaliser for dnsx JSON output."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser


class DnsxNormaliser(BaseNormaliser):
    tool_name = "dnsx"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings: list[Finding] = []
        hostname = raw_data.get("_hostname", raw_data.get("host", "unknown"))

        # Check for missing A/AAAA records
        a_records = raw_data.get("a", [])
        aaaa_records = raw_data.get("aaaa", [])
        cname_records = raw_data.get("cname", [])

        if not a_records and not aaaa_records and not cname_records:
            findings.append(Finding(
                tool=self.tool_name,
                severity=Severity.CRITICAL,
                category=Category.DNS_NETWORK,
                file=".",
                rule_id="dns-no-address-records",
                rule_name="No DNS Address Records",
                message=f"No A, AAAA, or CNAME records found for {hostname}",
                blocks_deploy=True,
                effort=Effort.MEDIUM,
                fix_hint=f"Add A or CNAME record for {hostname} in your DNS provider",
            ))

        # Check for missing MX records (might indicate incomplete setup)
        mx_records = raw_data.get("mx", [])

        # Check for SPF/DMARC in TXT records
        txt_records = raw_data.get("txt", [])
        has_spf = any("v=spf1" in txt for txt in txt_records)
        has_dmarc = any("v=DMARC1" in txt for txt in txt_records)

        if mx_records and not has_spf:
            findings.append(Finding(
                tool=self.tool_name,
                severity=Severity.LOW,
                category=Category.DNS_NETWORK,
                file=".",
                rule_id="dns-no-spf",
                rule_name="Missing SPF Record",
                message=f"No SPF record found for {hostname}. Email spoofing protection is missing.",
                blocks_deploy=False,
                effort=Effort.LOW,
                fix_hint="Add TXT record: v=spf1 include:_spf.google.com ~all (adjust for your mail provider)",
            ))

        if mx_records and not has_dmarc:
            findings.append(Finding(
                tool=self.tool_name,
                severity=Severity.LOW,
                category=Category.DNS_NETWORK,
                file=".",
                rule_id="dns-no-dmarc",
                rule_name="Missing DMARC Record",
                message=f"No DMARC record found for {hostname}. Email authentication policy is missing.",
                blocks_deploy=False,
                effort=Effort.LOW,
                fix_hint=f"Add TXT record for _dmarc.{hostname}: v=DMARC1; p=quarantine; rua=mailto:dmarc@{hostname}",
            ))

        # Check for CNAME at apex (not recommended)
        if cname_records and not a_records and "." not in hostname.split(".", 1)[0]:
            findings.append(Finding(
                tool=self.tool_name,
                severity=Severity.LOW,
                category=Category.DNS_NETWORK,
                file=".",
                rule_id="dns-cname-apex",
                rule_name="CNAME at Zone Apex",
                message=(
                    f"CNAME record at zone apex ({hostname}) can cause issues with "
                    f"other record types (MX, TXT). Use an ALIAS/ANAME record instead."
                ),
                blocks_deploy=False,
                effort=Effort.LOW,
                fix_hint="Replace CNAME at apex with an ALIAS or A record",
            ))

        return findings

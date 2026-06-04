"""Detect full library imports where tree-shakeable alternatives exist."""

from __future__ import annotations

import re

from viberapid.models import Category, Effort, Finding, Severity

TOOL_NAME = "ast-analyser"
RULE_ID = "js-large-import"
RULE_NAME = "Large Library Full Import"

# Known large libraries and their estimated sizes, plus fix hints
LARGE_LIBRARIES: dict[str, tuple[str, str]] = {
    "lodash": (
        "~72KB minified",
        "Import specific functions: import debounce from 'lodash/debounce'",
    ),
    "moment": (
        "~329KB minified (includes all locales)",
        "Use date-fns or dayjs instead — they are tree-shakeable",
    ),
    "rxjs": (
        "~50KB+ minified (full bundle)",
        "Import specific operators: import { map } from 'rxjs/operators'",
    ),
    "underscore": (
        "~25KB minified",
        "Import specific functions or switch to native ES methods",
    ),
    "jquery": (
        "~87KB minified",
        "Use native DOM APIs or a lighter alternative",
    ),
    "ramda": (
        "~50KB minified",
        "Import specific functions: import map from 'ramda/src/map'",
    ),
    "immutable": (
        "~63KB minified",
        "Use Immer (12KB) or native spread operators",
    ),
    "material-ui": (
        "Large bundle — imports all components",
        "Import specific components: import Button from '@mui/material/Button'",
    ),
    "@mui/material": (
        "Large bundle — imports all components",
        "Import specific components: import Button from '@mui/material/Button'",
    ),
    "@mui/icons-material": (
        "Very large — includes all icons",
        "Import specific icons: import Home from '@mui/icons-material/Home'",
    ),
    "antd": (
        "Large bundle — imports all components",
        "Import specific components: import { Button } from 'antd' with babel-plugin-import",
    ),
}

# Patterns that indicate a full library import (not tree-shakeable)
# Default import: import _ from 'lodash'
DEFAULT_IMPORT = re.compile(
    r"""^import\s+(\w+)\s+from\s+['"]([^'"./][^'"]*?)['"]"""
)

# Namespace import: import * as _ from 'lodash'
NAMESPACE_IMPORT = re.compile(
    r"""^import\s+\*\s+as\s+(\w+)\s+from\s+['"]([^'"./][^'"]*?)['"]"""
)

# Require: const _ = require('lodash')
REQUIRE_PATTERN = re.compile(
    r"""(?:const|let|var)\s+(\w+)\s*=\s*require\s*\(\s*['"]([^'"./][^'"]*?)['"]\s*\)"""
)

# Comment pattern
COMMENT_RE = re.compile(r"//.*$")
BLOCK_COMMENT_OPEN = re.compile(r"/\*")
BLOCK_COMMENT_CLOSE = re.compile(r"\*/")


def _normalize_package_name(name: str) -> str:
    """Normalize package name for matching (strip version, handle scoped)."""
    # Handle scoped packages: @mui/material -> @mui/material
    return name.split("/")[0] if not name.startswith("@") else "/".join(name.split("/")[:2])


def check(filepath: str, source: str) -> list[Finding]:
    """Detect full library imports of known large packages."""
    findings: list[Finding] = []
    lines = source.split("\n")
    in_block_comment = False

    for line_idx, raw_line in enumerate(lines):
        line_num = line_idx + 1

        # Handle block comments
        if in_block_comment:
            if BLOCK_COMMENT_CLOSE.search(raw_line):
                in_block_comment = False
            continue
        if BLOCK_COMMENT_OPEN.search(raw_line) and not BLOCK_COMMENT_CLOSE.search(raw_line):
            in_block_comment = True
            continue

        stripped = COMMENT_RE.sub("", raw_line).strip()
        if not stripped:
            continue

        # Check default imports: import _ from 'lodash'
        match = DEFAULT_IMPORT.match(stripped)
        if match:
            identifier, package = match.group(1), match.group(2)
            pkg_key = _normalize_package_name(package)
            if pkg_key in LARGE_LIBRARIES:
                size_info, fix_hint = LARGE_LIBRARIES[pkg_key]
                findings.append(
                    Finding(
                        tool=TOOL_NAME,
                        severity=Severity.HIGH,
                        category=Category.BUNDLE,
                        file=filepath,
                        rule_id=RULE_ID,
                        rule_name=RULE_NAME,
                        message=(
                            f"Full import of `{package}` ({size_info}) — "
                            f"imports the entire library instead of specific functions"
                        ),
                        line=line_num,
                        fix_hint=fix_hint,
                        effort=Effort.LOW,
                    )
                )
            continue

        # Check namespace imports: import * as _ from 'lodash'
        match = NAMESPACE_IMPORT.match(stripped)
        if match:
            identifier, package = match.group(1), match.group(2)
            pkg_key = _normalize_package_name(package)
            if pkg_key in LARGE_LIBRARIES:
                size_info, fix_hint = LARGE_LIBRARIES[pkg_key]
                findings.append(
                    Finding(
                        tool=TOOL_NAME,
                        severity=Severity.HIGH,
                        category=Category.BUNDLE,
                        file=filepath,
                        rule_id=RULE_ID,
                        rule_name=RULE_NAME,
                        message=(
                            f"Namespace import of `{package}` ({size_info}) — "
                            f"prevents tree-shaking"
                        ),
                        line=line_num,
                        fix_hint=fix_hint,
                        effort=Effort.LOW,
                    )
                )
            continue

        # Check require: const _ = require('lodash')
        match = REQUIRE_PATTERN.search(stripped)
        if match:
            identifier, package = match.group(1), match.group(2)
            pkg_key = _normalize_package_name(package)
            if pkg_key in LARGE_LIBRARIES:
                size_info, fix_hint = LARGE_LIBRARIES[pkg_key]
                findings.append(
                    Finding(
                        tool=TOOL_NAME,
                        severity=Severity.HIGH,
                        category=Category.BUNDLE,
                        file=filepath,
                        rule_id=RULE_ID,
                        rule_name=RULE_NAME,
                        message=(
                            f"Full require of `{package}` ({size_info}) — "
                            f"imports the entire library"
                        ),
                        line=line_num,
                        fix_hint=fix_hint,
                        effort=Effort.LOW,
                    )
                )

    return findings

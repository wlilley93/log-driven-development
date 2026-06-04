"""Runner for prisma_inspector — detects N+1 patterns in Prisma ORM schemas."""

from __future__ import annotations

import re
from pathlib import Path

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.prisma_inspector import PrismaInspectorNormaliser
from viberapid.runners.base import AsyncToolRunner


class PrismaInspectorRunner(AsyncToolRunner):
    """Analyse Prisma schema and source files for N+1 query patterns and missing optimisations.

    Detects:
    - Relations without explicit include/select in queries
    - Models with many relations (N+1 risk)
    - Missing @@index directives for foreign key columns
    - Unbounded findMany calls without take/cursor
    """

    name = "prisma_inspector"
    requires_node = True

    def should_run(self) -> bool:
        schema_files = self._glob_files("schema.prisma", "*.prisma")
        if not schema_files:
            self.skip_reason = "no Prisma schema files found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        target = Path(self.target)

        # --- Parse Prisma schema ---
        schema_files = self._glob_files("schema.prisma", "*.prisma")
        if not schema_files:
            return self._make_error_result("no Prisma schema files found")

        models: dict[str, _PrismaModel] = {}
        for schema_file in schema_files:
            try:
                content = schema_file.read_text(errors="ignore")
                parsed = _parse_prisma_schema(content, str(schema_file.relative_to(target)))
                models.update(parsed)
            except OSError:
                continue

        if not models:
            return self._make_error_result("no Prisma models found in schema files")

        # --- Scan source files for Prisma query patterns ---
        source_files = (
            self._glob_files("*.ts", "*.tsx", "*.js", "*.jsx")
        )

        query_patterns: list[dict] = []
        for source_file in source_files:
            # Skip node_modules and build artifacts
            rel_path = str(source_file.relative_to(target))
            if "node_modules" in rel_path or ".next" in rel_path or "dist" in rel_path:
                continue

            try:
                content = source_file.read_text(errors="ignore")
            except OSError:
                continue

            patterns = _scan_for_query_patterns(content, rel_path)
            query_patterns.extend(patterns)

        raw_data = {
            "models": {name: model.to_dict() for name, model in models.items()},
            "query_patterns": query_patterns,
            "schema_files": [str(f.relative_to(target)) for f in schema_files],
            "source_files_scanned": len(source_files),
        }

        normaliser = PrismaInspectorNormaliser()
        findings = normaliser.normalise(raw_data)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "models_found": len(models),
                "relations_found": sum(
                    len(m.relations) for m in models.values()
                ),
                "schema_files": len(schema_files),
                "source_files_scanned": len(source_files),
                "query_patterns_detected": len(query_patterns),
            },
        )


class _PrismaModel:
    """Parsed Prisma model with fields and relations."""

    __slots__ = ("name", "file", "line", "fields", "relations", "indexes")

    def __init__(self, name: str, file: str, line: int):
        self.name = name
        self.file = file
        self.line = line
        self.fields: list[dict] = []
        self.relations: list[dict] = []
        self.indexes: list[str] = []

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "file": self.file,
            "line": self.line,
            "fields": self.fields,
            "relations": self.relations,
            "indexes": self.indexes,
        }


def _parse_prisma_schema(content: str, file_path: str) -> dict[str, _PrismaModel]:
    """Parse a Prisma schema file into model definitions."""
    models: dict[str, _PrismaModel] = {}

    # Find model blocks
    model_pattern = re.compile(
        r"^model\s+(\w+)\s*\{(.*?)^\}",
        re.MULTILINE | re.DOTALL,
    )

    for match in model_pattern.finditer(content):
        model_name = match.group(1)
        body = match.group(2)
        line_num = content[:match.start()].count("\n") + 1

        model = _PrismaModel(model_name, file_path, line_num)

        # Parse fields
        field_pattern = re.compile(
            r"^\s+(\w+)\s+(\w+)(\[\])?\s*(.*?)$",
            re.MULTILINE,
        )

        for field_match in field_pattern.finditer(body):
            field_name = field_match.group(1)
            field_type = field_match.group(2)
            is_array = field_match.group(3) is not None
            attributes = field_match.group(4).strip()

            field_line = line_num + body[:field_match.start()].count("\n") + 1

            # Check if this is a relation field
            is_relation = (
                field_type in models
                or field_type[0].isupper()
                and "@relation" in attributes
                or is_array
                and field_type[0].isupper()
            )

            field_info = {
                "name": field_name,
                "type": field_type,
                "is_array": is_array,
                "is_relation": is_relation,
                "attributes": attributes,
                "line": field_line,
            }

            model.fields.append(field_info)

            if is_relation:
                model.relations.append(field_info)

        # Parse @@index directives
        index_pattern = re.compile(r"@@index\(\[([^\]]+)\]\)")
        for idx_match in index_pattern.finditer(body):
            model.indexes.append(idx_match.group(1).strip())

        models[model_name] = model

    # Second pass: mark relations for models found after initial parse
    all_model_names = set(models.keys())
    for model in models.values():
        for field in model.fields:
            if not field["is_relation"] and field["type"] in all_model_names:
                field["is_relation"] = True
                model.relations.append(field)

    return models


def _scan_for_query_patterns(content: str, file_path: str) -> list[dict]:
    """Scan a source file for Prisma query patterns that may cause N+1 issues."""
    patterns: list[dict] = []

    lines = content.split("\n")

    # Pattern: findMany without include/select
    findmany_pattern = re.compile(
        r"\.findMany\s*\(\s*(?:\{[^}]*?\})?\s*\)",
        re.DOTALL,
    )

    # Pattern: findMany with take/cursor (pagination — good)
    findmany_paginated = re.compile(
        r"\.findMany\s*\(\s*\{[^}]*(?:take|cursor)[^}]*\}",
        re.DOTALL,
    )

    # Pattern: loops that call prisma operations
    loop_prisma_pattern = re.compile(
        r"(?:for\s*\(|\.(?:map|forEach|reduce)\s*\()[^)]*?\.(?:findUnique|findFirst|findMany|update|delete)\s*\(",
        re.DOTALL,
    )

    for i, line in enumerate(lines, 1):
        # Detect findMany without include
        if ".findMany" in line:
            # Check surrounding context (5 lines ahead)
            context = "\n".join(lines[max(0, i - 1):min(len(lines), i + 5)])
            if "include" not in context and "select" not in context:
                # Check if it has pagination
                if not findmany_paginated.search(context):
                    patterns.append({
                        "file": file_path,
                        "line": i,
                        "type": "findMany_no_include",
                        "context": line.strip()[:200],
                    })

            # Check for unbounded findMany (no take/cursor)
            if "take" not in context and "cursor" not in context:
                patterns.append({
                    "file": file_path,
                    "line": i,
                    "type": "unbounded_findMany",
                    "context": line.strip()[:200],
                })

    # Detect prisma calls inside loops (N+1 pattern)
    for match in loop_prisma_pattern.finditer(content):
        line_num = content[:match.start()].count("\n") + 1
        patterns.append({
            "file": file_path,
            "line": line_num,
            "type": "prisma_in_loop",
            "context": match.group()[:200],
        })

    return patterns

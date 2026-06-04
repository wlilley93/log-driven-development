"""Normaliser for prisma_inspector schema and query analysis output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


class PrismaInspectorNormaliser(BaseNormaliser):
    """Convert Prisma schema and query pattern analysis to Finding objects.

    Expected raw_data shape:
    {
      "models": {
        "User": {
          "name": "User",
          "file": "prisma/schema.prisma",
          "line": 10,
          "fields": [...],
          "relations": [...],
          "indexes": [...]
        }
      },
      "query_patterns": [
        {
          "file": "src/lib/users.ts",
          "line": 42,
          "type": "findMany_no_include",
          "context": "const users = await prisma.user.findMany()"
        }
      ]
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []
        models = raw_data.get("models", {})
        query_patterns = raw_data.get("query_patterns", [])

        if isinstance(models, dict):
            findings.extend(self._analyse_models(models))

        if isinstance(query_patterns, list):
            findings.extend(self._analyse_query_patterns(query_patterns))

        return findings

    def _analyse_models(self, models: dict[str, Any]) -> list[Finding]:
        """Analyse Prisma models for schema-level issues."""
        findings: list[Finding] = []

        for model_name, model_data in models.items():
            if not isinstance(model_data, dict):
                continue

            file_path = model_data.get("file", "<schema>")
            line = model_data.get("line")
            relations = model_data.get("relations", [])
            fields = model_data.get("fields", [])
            indexes = model_data.get("indexes", [])

            # --- Models with many relations (N+1 risk) ---
            if len(relations) > 5:
                findings.append(Finding(
                    tool="prisma_inspector",
                    severity=Severity.MEDIUM,
                    category=Category.DATABASE,
                    file=file_path,
                    rule_id="prisma/many-relations",
                    rule_name="Model With Many Relations",
                    message=(
                        f"Model '{model_name}' has {len(relations)} relations. "
                        "Queries that load this model without explicit `select` or "
                        "`include` may inadvertently trigger N+1 queries."
                    ),
                    line=line,
                    effort=Effort.MEDIUM,
                    fix_hint=(
                        f"Always use `select` or `include` when querying '{model_name}'. "
                        "Only load the relations you actually need. Consider creating "
                        "a Prisma view or computed field for commonly needed aggregates."
                    ),
                    raw=model_data,
                ))

            # --- Missing indexes on foreign key columns ---
            indexed_fields = set()
            for idx in indexes:
                # Parse index field list like "userId, orgId"
                for field_name in idx.split(","):
                    indexed_fields.add(field_name.strip())

            for field in fields:
                if not isinstance(field, dict):
                    continue

                field_name = field.get("name", "")
                attributes = field.get("attributes", "")

                # Check for foreign key fields (fields with @relation or ending in Id)
                is_fk = (
                    "@relation" in attributes
                    or (field_name.endswith("Id") and not field.get("is_relation"))
                )

                if is_fk and field_name not in indexed_fields:
                    # Check if it's part of @id or @unique
                    if "@id" in attributes or "@unique" in attributes:
                        continue

                    findings.append(Finding(
                        tool="prisma_inspector",
                        severity=Severity.MEDIUM,
                        category=Category.DATABASE,
                        file=file_path,
                        rule_id="prisma/missing-fk-index",
                        rule_name="Missing Foreign Key Index",
                        message=(
                            f"Field '{model_name}.{field_name}' appears to be a "
                            "foreign key but has no @@index. This causes sequential "
                            "scans on JOINs and WHERE clauses."
                        ),
                        line=field.get("line"),
                        effort=Effort.LOW,
                        fix_hint=(
                            f"Add @@index([{field_name}]) to the '{model_name}' model. "
                            "This is critical for query performance on relations."
                        ),
                        saving_estimate=(
                            f"Index on {model_name}.{field_name} eliminates sequential "
                            "scans for related queries"
                        ),
                        raw=field,
                    ))

            # --- Array relations without @@index on the reverse side ---
            for relation in relations:
                if not isinstance(relation, dict):
                    continue

                if relation.get("is_array"):
                    relation_type = relation.get("type", "")
                    relation_name = relation.get("name", "")

                    # Check if the target model has an index on the FK pointing back
                    target_model = models.get(relation_type, {})
                    if isinstance(target_model, dict):
                        target_fields = target_model.get("fields", [])
                        target_indexes = set()
                        for idx in target_model.get("indexes", []):
                            for f in idx.split(","):
                                target_indexes.add(f.strip())

                        # Look for FK field in target pointing to this model
                        fk_field_name = f"{model_name[0].lower()}{model_name[1:]}Id"
                        has_fk_field = any(
                            f.get("name") == fk_field_name
                            for f in target_fields
                            if isinstance(f, dict)
                        )

                        if has_fk_field and fk_field_name not in target_indexes:
                            findings.append(Finding(
                                tool="prisma_inspector",
                                severity=Severity.HIGH,
                                category=Category.DATABASE,
                                file=target_model.get("file", file_path),
                                rule_id="prisma/missing-reverse-index",
                                rule_name="Missing Index on Reverse Relation",
                                message=(
                                    f"'{model_name}.{relation_name}' is an array "
                                    f"relation to '{relation_type}', but "
                                    f"'{relation_type}.{fk_field_name}' has no index. "
                                    "Loading this relation will cause a sequential scan."
                                ),
                                line=relation.get("line"),
                                effort=Effort.LOW,
                                fix_hint=(
                                    f"Add @@index([{fk_field_name}]) to the "
                                    f"'{relation_type}' model to make loading "
                                    f"'{model_name}.{relation_name}' efficient."
                                ),
                                saving_estimate=(
                                    f"Index on {relation_type}.{fk_field_name} "
                                    "prevents full table scans when loading relation"
                                ),
                                raw=relation,
                            ))

        return findings

    def _analyse_query_patterns(self, patterns: list[Any]) -> list[Finding]:
        """Analyse detected Prisma query patterns in source code."""
        findings: list[Finding] = []

        for pattern in patterns:
            if not isinstance(pattern, dict):
                continue

            pattern_type = pattern.get("type", "")
            file_path = pattern.get("file", "<unknown>")
            line = pattern.get("line")
            context = pattern.get("context", "")

            if pattern_type == "findMany_no_include":
                findings.append(Finding(
                    tool="prisma_inspector",
                    severity=Severity.MEDIUM,
                    category=Category.DATABASE,
                    file=file_path,
                    rule_id="prisma/findMany-no-include",
                    rule_name="findMany Without include/select",
                    message=(
                        f"findMany() called without `include` or `select`. "
                        f"If relations are accessed later, this causes N+1 queries. "
                        f"Context: {context}"
                    ),
                    line=line,
                    effort=Effort.LOW,
                    fix_hint=(
                        "Add explicit `include` or `select` to specify which fields "
                        "and relations to load. This prevents lazy loading N+1 patterns."
                    ),
                    raw=pattern,
                ))

            elif pattern_type == "unbounded_findMany":
                findings.append(Finding(
                    tool="prisma_inspector",
                    severity=Severity.MEDIUM,
                    category=Category.DATABASE,
                    file=file_path,
                    rule_id="prisma/unbounded-findMany",
                    rule_name="Unbounded findMany Query",
                    message=(
                        f"findMany() called without `take` or `cursor` pagination. "
                        f"May load entire table into memory. Context: {context}"
                    ),
                    line=line,
                    effort=Effort.LOW,
                    fix_hint=(
                        "Add `take` with a reasonable limit (e.g., 100) and use "
                        "`cursor` or `skip` for pagination. Unbounded queries "
                        "can cause OOM errors as data grows."
                    ),
                    raw=pattern,
                ))

            elif pattern_type == "prisma_in_loop":
                findings.append(Finding(
                    tool="prisma_inspector",
                    severity=Severity.HIGH,
                    category=Category.DATABASE,
                    file=file_path,
                    rule_id="prisma/query-in-loop",
                    rule_name="Prisma Query Inside Loop (N+1)",
                    message=(
                        f"Prisma query detected inside a loop or array method. "
                        f"This is a classic N+1 pattern. Context: {context}"
                    ),
                    line=line,
                    effort=Effort.MEDIUM,
                    fix_hint=(
                        "Refactor to use a single query with `where: { id: { in: ids } }` "
                        "or use `include` on the parent query to eagerly load relations. "
                        "For complex cases, consider Prisma's `$transaction` with batched queries."
                    ),
                    saving_estimate=(
                        "Eliminating N+1 can reduce query count from N to 1-2"
                    ),
                    raw=pattern,
                ))

        return findings

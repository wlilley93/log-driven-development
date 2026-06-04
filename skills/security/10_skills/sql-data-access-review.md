---
name: sql-data-access-review
type: skill
domain: security
summary: Review SQL, ORM, analytics queries, and data access for injection, tenant scope, and data exposure.
outputs: [sql-data-access-review.md]
---

# SQL Data Access Review

## Use When

Use for raw SQL, ORM queries, report queries, analytics exports, data warehouse work, migrations, background jobs, and query builders.

## Required Checks

- Query purpose, dialect, grain, source tables, filters, and joins are explicit.
- Queries are parameterized and do not interpolate untrusted strings.
- Tenant/workspace/org filters are present for scoped data.
- Joins are validated for row explosion and cross-tenant leakage.
- Sensitive columns are minimized, masked, or excluded.
- Date/partition filters prevent unbounded scans where relevant.
- Raw SQL has a stronger review than ORM calls because framework-level guards may not apply.

## Output

Record query risk, injection posture, tenant isolation posture, sensitive data exposure, performance footguns that can become availability risks, and exact validation checks.

---
name: authz-tenant-isolation-review
type: skill
domain: security
summary: Trace authorization, RBAC/ABAC, object access, tenant scope, and mass assignment risks.
outputs: [tenant-findings.json]
---

# Authz Tenant Isolation Review

## Use When

Use when reviewing roles, permissions, org/workspace scoping, object IDs, admin routes, background jobs, webhooks, database queries, or cross-tenant data flows.

## Required Checks

- Every read/write path has actor, role, and tenant/workspace context.
- Object-level authorization is checked for every resource ID.
- Sensitive fields have property-level authorization where needed.
- Admin paths cannot be reached by parameter manipulation.
- Background jobs, events, and webhooks carry durable tenant scope.
- ORM and raw SQL queries include tenant filters unless globally-scoped by design.
- Request bodies cannot mass-assign role, owner, tenant, billing, or security fields.

## Required Tests

Same-tenant access succeeds; cross-tenant access fails; lower roles cannot mutate privileged fields; deleted/suspended tenant access fails; forged IDs fail; replayed webhooks cannot cross tenants.

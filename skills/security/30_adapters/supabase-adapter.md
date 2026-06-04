---
name: supabase-adapter
type: adapter
domain: security
summary: Supabase security adapter.
---

# Supabase Adapter

Apply when Supabase auth, database, storage, realtime, edge functions, or service-role clients are present.

## Required Checks

- Service-role keys stay server-only and do not enter client bundles.
- RLS is enabled and policies enforce tenant isolation.
- Grants and exposed schemas are minimal.
- RPC and `security definer` functions cannot bypass tenant checks.
- Storage policies, signed URLs, realtime channels, edge functions, and webhooks are scoped and auditable.

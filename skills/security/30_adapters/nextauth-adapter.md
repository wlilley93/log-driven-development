---
name: nextauth-adapter
type: adapter
domain: security
summary: NextAuth authentication and session adapter.
---

# NextAuth Adapter

Apply when NextAuth/Auth.js config, callbacks, JWT/session fields, PrismaAdapter, route protection, or middleware are present.

## Required Checks

- JWT and session callbacks do not promote stale DB state into durable authorization or MFA state.
- Session augmentation is minimal and does not expose sensitive fields.
- API routes and server components enforce auth on the server.
- CSRF and callback URL behavior match the framework threat model.
- Tests cover callback behavior, protected route access, and logout/session invalidation.

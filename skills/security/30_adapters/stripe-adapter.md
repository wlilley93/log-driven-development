---
name: stripe-adapter
type: adapter
domain: security
summary: Stripe payment security adapter.
---

# Stripe Adapter

Apply when Stripe SDK, webhooks, Checkout, billing, subscriptions, invoices, or Connect accounts are present.

## Required Checks

- Secret keys and webhook secrets are server-only and environment-specific.
- Webhooks verify signatures and use durable tenant/customer mapping.
- Client-provided price, amount, currency, account ID, customer ID, and subscription IDs are never trusted.
- Idempotency keys are used where retries can duplicate charges or objects.
- Tenant isolation applies to customer, account, invoice, subscription, and payment state.
- Logs redact keys, client secrets, billing details, and sensitive metadata.

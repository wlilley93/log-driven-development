---
name: plugin-mcp-sandboxing-review
type: skill
domain: security
summary: Review plugin, MCP, hook, and tool permissions for bounded automation.
outputs: [plugin-mcp-security-review.md]
---

# Plugin MCP Sandboxing Review

## Required Checks

- Every component has a declared permission level and data sensitivity.
- Tools validate inputs, classify side effects, redact outputs, and log mutations.
- Destructive actions require explicit human confirmation and rollback notes.
- Hooks have timeouts, deterministic tests, clear failure messages, and no prompt/file-content leakage.
- Settings and manifests do not contain secrets.
- External service scopes are least-privilege.
- Prompt injection paths through tool outputs, issues, PRs, documents, and MCP resources are considered.

## Output

Produce a component security matrix and findings for unbounded permissions, secret exposure, unsafe hooks, or missing dry-run controls.

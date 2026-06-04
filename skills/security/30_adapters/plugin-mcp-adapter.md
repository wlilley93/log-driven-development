---
name: plugin-mcp-adapter
type: adapter
domain: security
summary: Plugin and MCP security adapter.
---

# Plugin MCP Adapter

Apply when a project defines plugins, MCP servers, hooks, external tools, or automation manifests.

## Required Checks

- Tool schemas reject malformed or overbroad inputs.
- Mutating tools are side-effect classified and audited.
- External write scopes are least privilege.
- Prompt injection through tool results and repository content is considered.
- Local file access, shell execution, network access, and destructive actions are bounded.

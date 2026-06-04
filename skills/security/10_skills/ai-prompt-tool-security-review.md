---
name: ai-prompt-tool-security-review
type: skill
domain: security
summary: Review AI, prompt injection, tool calling, agent autonomy, and MCP security boundaries.
outputs: [ai-tool-security-findings.json]
---

# AI Prompt Tool Security Review

## Use When

Use when a system has LLM prompts, RAG, uploaded content passed to models, tool calling, autonomous agents, MCP bridges, browser automation, or external tool results.

## Required Checks

- Untrusted content is structurally separated from instructions.
- Tool results are treated as data, not directives.
- Tool calls enforce authorization, tenant scope, rate limits, spend caps, and autonomy level at the call boundary.
- Destructive tools require explicit approval or a verified policy gate.
- Prompt injection defenses are structural, not only blocklists.
- Agent logs redact sensitive data while preserving auditability.
- Public, lower-privilege, or customer-controlled text cannot trigger privileged actions.

## Output

Include at least one concrete adversarial scenario for each untrusted-text surface. If a scanner/blocklist is present, test bypass classes: leetspeak, word order, zero-width splits, encoding, and non-English variants.

## Added check  -  tool / memory output as an injection boundary
- **Untrusted tool/memory output.** Results returned to the model from tools,
  retrieved memory, RAG, or other agents are **untrusted data**, not instructions.
  Are they wrapped/tagged as inert reference data (explicit envelope the system
  prompt treats as content to reason about), or concatenated into the context
  where crafted text can act as instructions (indirect prompt injection)? Stored
  free-text memory recalled later is a classic vector.
- **Tool-scope vs transport.** Is a tool's authority bounded by the agent's
  identity at the transport (peer-cred / per-agent key), or only by *registration*
  (the tool "isn't listed" for this agent) while the underlying socket/secret is
  reachable anyway? (See `shared-secret-scoping-review`.)

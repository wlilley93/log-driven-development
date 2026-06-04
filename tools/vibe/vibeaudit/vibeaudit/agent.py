"""Agentic deep scan mode — LLM autonomously explores codebase for vulnerabilities."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console

from vibeaudit.agent_tools import ToolExecutor, get_agent_tools
from vibeaudit.config import VibeauditConfig
from vibeaudit.cost_tracker import CostTracker, BudgetExceededError
from vibeaudit.models import (
    CodeSnippet, Confidence, Finding, Severity, VulnClass,
)
from vibeaudit.provider import LLMProvider, ToolResult


AGENT_SYSTEM_PROMPT = """You are an expert security auditor performing a deep scan of a codebase.

Your goal is to find real, exploitable security vulnerabilities — not theoretical ones.
Focus on business logic flaws that static analysis tools miss:
- Authentication bypasses
- Authorization failures (IDOR, broken access control)
- Race conditions in critical flows
- Mass assignment vulnerabilities
- Data exposure in API responses
- Injection flaws (command, SQL, SSRF, path traversal)

You have tools to read files, search code, list directories, and trace middleware chains.

Strategy:
1. Start by listing the project structure to understand the architecture
2. Identify API routes, auth mechanisms, and data models
3. For each route/endpoint, trace the auth chain and check for gaps
4. Look for patterns that indicate specific vulnerability classes
5. When you find a vulnerability, use report_finding to submit it

Be thorough but focused. Only report findings you're confident about.
When you're done investigating, stop calling tools — just say "Scan complete."
"""


class AgentScanner:
    def __init__(
        self,
        config: VibeauditConfig,
        provider: LLMProvider,
        cost_tracker: CostTracker,
        console: Console | None = None,
    ):
        self.config = config
        self.provider = provider
        self.cost_tracker = cost_tracker
        self.console = console or Console()
        self.tool_executor = ToolExecutor(Path(config.scan.target_dir).resolve())
        self.tools = get_agent_tools()
        self.findings: list[Finding] = []
        self.max_iterations = config.agent.max_iterations

    async def run(self) -> list[Finding]:
        """Run the agentic scan loop."""
        self.console.print("[bold]Starting deep scan (agentic mode)...[/bold]")

        vuln_classes = ", ".join(self.config.scan.vuln_classes)
        messages: list[dict] = [
            {
                "role": "user",
                "content": f"Scan this codebase for security vulnerabilities. Focus on these classes: {vuln_classes}. "
                           f"The project root is the current directory. Start by exploring the structure.",
            }
        ]

        for iteration in range(self.max_iterations):
            # Budget check
            can_continue, msg = await self.cost_tracker.check_budget(self.config.cost.hard_cap_usd)
            if not can_continue:
                self.console.print(f"[yellow]Budget limit reached: {msg}[/yellow]")
                break

            # Warning at configured threshold
            if msg:
                # check_budget returns a non-empty message at 90% threshold
                messages.append({
                    "role": "user",
                    "content": "WARNING: You are approaching the token budget limit. Please wrap up your investigation and report any remaining findings.",
                })

            # Call LLM with tools
            try:
                response = await self.provider.complete_with_tools(
                    system=AGENT_SYSTEM_PROMPT,
                    messages=messages,
                    tools=self.tools,
                    max_tokens=self.config.provider.max_tokens,
                    temperature=self.config.provider.temperature,
                )
            except Exception as e:
                self.console.print(f"[red]Agent error: {e}[/red]")
                break

            await self.cost_tracker.record(response.model, response.input_tokens, response.output_tokens)

            # No tool calls = agent is done
            if not response.tool_calls:
                self.console.print(f"[dim]Agent: {response.content[:200]}[/dim]")
                break

            # Build assistant message with tool calls (provider-specific format handled by provider)
            # Store in a normalized format
            assistant_msg = {"role": "assistant", "content": response.content, "tool_calls": [
                {"id": tc.id, "name": tc.name, "arguments": tc.arguments} for tc in response.tool_calls
            ]}
            messages.append(assistant_msg)

            # Execute each tool call
            tool_results: list[ToolResult] = []
            for tc in response.tool_calls:
                if tc.name == "report_finding":
                    finding = self._create_finding(tc.arguments)
                    if finding:
                        self.findings.append(finding)
                        result_content = f"Finding recorded: {finding.title} ({finding.id})"
                    else:
                        result_content = "Error: Invalid finding data"
                else:
                    result_content = self.tool_executor.execute(tc.name, tc.arguments)

                # Truncate very long results to manage context
                if len(result_content) > 10000:
                    result_content = result_content[:10000] + "\n... (truncated)"

                tool_results.append(ToolResult(
                    tool_call_id=tc.id,
                    content=result_content,
                ))

            # Add tool results to messages (format depends on provider)
            # Anthropic: user message with tool_result content blocks
            # OpenAI: separate tool role messages
            if self.provider.name == "anthropic":
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "tool_result", "tool_use_id": tr.tool_call_id, "content": tr.content}
                        for tr in tool_results
                    ],
                })
            else:
                for tr in tool_results:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tr.tool_call_id,
                        "content": tr.content,
                    })

            self.console.print(f"[dim]  Agent iteration {iteration + 1}: {len(response.tool_calls)} tool calls, {len(self.findings)} findings[/dim]")

        self.console.print(f"[bold]Deep scan complete: {len(self.findings)} findings[/bold]")
        return self.findings

    def _create_finding(self, args: dict) -> Finding | None:
        """Create a Finding from report_finding tool arguments."""
        try:
            file_path = args.get("file_path", "")
            start_line = args.get("start_line", 1)
            end_line = args.get("end_line", start_line)

            # Try to read the actual code
            code_content = ""
            try:
                full_path = self.tool_executor._resolve_path(file_path)
                if full_path.is_file():
                    lines = full_path.read_text(errors="replace").split("\n")
                    code_content = "\n".join(lines[start_line - 1:end_line])
            except Exception:
                pass

            snippet = CodeSnippet(
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                content=code_content,
                language="unknown",
            )

            return Finding(
                vuln_class=VulnClass(args["vuln_class"]),
                severity=Severity(args["severity"]),
                confidence=Confidence(args.get("confidence", "medium")),
                title=args["title"],
                description=args["description"],
                attack_scenario=args.get("attack_scenario", ""),
                impact=args.get("impact", ""),
                remediation=args.get("remediation", ""),
                snippets=[snippet],
                cwe_id=args.get("cwe_id", ""),
                source="agent",
            )
        except (ValueError, KeyError) as e:
            return None

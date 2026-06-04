"""Scanner orchestration — targeted mode."""

from __future__ import annotations

import asyncio
import fnmatch
import json
import re
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from vibeaudit.config import VibeauditConfig
from vibeaudit.cost_tracker import CostTracker, BudgetExceededError
from vibeaudit.extractor import Extractor, ExtractionResult
from vibeaudit.models import (
    Confidence, Finding, ScanResult, Severity, VulnClass,
)
from vibeaudit.prompt_loader import PromptLoader
from vibeaudit.providers import create_provider


class Scanner:
    def __init__(self, config: VibeauditConfig, console: Console | None = None, quiet: bool = False):
        self.config = config
        self.console = console or Console()
        self.quiet = quiet
        self.extractor = Extractor(max_snippet_lines=config.scan.max_snippet_lines)
        self.prompt_loader = PromptLoader()
        self.cost_tracker = CostTracker()
        self._seen_ids: set[str] = set()

    async def run(self, since: str | None = None) -> ScanResult:
        """Full targeted scan."""
        provider = create_provider(self.config.provider)

        # 1. Collect files
        files = self._collect_files(since)
        if not files:
            if not self.quiet:
                self.console.print("[yellow]No files to scan.[/yellow]")
            return ScanResult(scanned_files=0)

        # 2. Detect project context
        project_context = self._detect_project_context(files)

        # 3. Determine vuln classes
        vuln_classes = [VulnClass(c) for c in self.config.scan.vuln_classes]

        # 4. Build work items: extract code regions for each (file, vuln_class) pair
        work_items: list[tuple] = []
        for file_path in files:
            try:
                content = file_path.read_text(errors="replace")
            except Exception:
                continue
            for vc in vuln_classes:
                results = self.extractor.extract(file_path, content, vc)
                for result in results:
                    if result.snippets:
                        work_items.append((file_path, vc, result, project_context))

        if not self.quiet:
            self.console.print(f"[bold]Scanning {len(files)} files across {len(vuln_classes)} vulnerability classes[/bold]")
            self.console.print(f"[dim]Found {len(work_items)} code regions to analyse[/dim]")

        if not work_items:
            return ScanResult(
                scanned_files=len(files),
                scanned_classes=[vc.value for vc in vuln_classes],
                provider=provider.name,
                model=self.config.provider.model or provider.default_model,
            )

        # 5. Send to LLM in parallel with semaphore
        findings: list[Finding] = []
        semaphore = asyncio.Semaphore(self.config.scan.concurrency)

        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
            BarColumn(), TaskProgressColumn(),
            console=self.console, disable=self.quiet,
        ) as progress:
            task = progress.add_task("Analysing...", total=len(work_items))

            async def process_item(fp, vc, extraction, ctx):
                async with semaphore:
                    can_continue, msg = await self.cost_tracker.check_budget(self.config.cost.hard_cap_usd)
                    if not can_continue:
                        raise BudgetExceededError(self.cost_tracker.total_cost_usd, self.config.cost.hard_cap_usd)
                    try:
                        result = await self._analyse_snippet(provider, vc, extraction, ctx)
                        return result
                    except BudgetExceededError:
                        raise
                    except Exception as e:
                        if not self.quiet:
                            self.console.print(f"[dim red]Error: {fp.name}:{vc.value}: {e}[/dim red]")
                        return []
                    finally:
                        progress.advance(task)

            tasks_list = [process_item(fp, vc, ext, ctx) for fp, vc, ext, ctx in work_items]

            try:
                results = await asyncio.gather(*tasks_list, return_exceptions=True)
            except BudgetExceededError:
                results = []

        # 6. Deduplicate
        for result in results:
            if isinstance(result, list):
                for finding in result:
                    if finding.id not in self._seen_ids:
                        self._seen_ids.add(finding.id)
                        findings.append(finding)

        # 7. Sort by severity
        findings.sort(key=lambda f: f.severity.rank)

        # 8. Apply baseline
        findings = self._apply_baseline(findings)

        # 9. Agent mode (deep scan) if enabled
        if self.config.agent.enabled:
            try:
                from vibeaudit.agent import AgentScanner
                agent = AgentScanner(self.config, provider, self.cost_tracker, self.console)
                agent_findings = await agent.run()
                for f in agent_findings:
                    if f.id not in self._seen_ids:
                        self._seen_ids.add(f.id)
                        findings.append(f)
                findings.sort(key=lambda f: f.severity.rank)
            except Exception as e:
                if not self.quiet:
                    self.console.print(f"[yellow]Agent scan error: {e}[/yellow]")

        return ScanResult(
            findings=findings,
            scanned_files=len(files),
            scanned_classes=[vc.value for vc in vuln_classes],
            total_tokens=self.cost_tracker.total_tokens,
            total_cost_usd=self.cost_tracker.total_cost_usd,
            provider=provider.name,
            model=self.config.provider.model or provider.default_model,
        )

    def extract_all(self, since: str | None = None) -> dict:
        """Extract all code regions without calling an LLM.

        Returns a JSON-serializable dict with project context and all
        extraction results.  Designed for Claude Code integration: the
        caller (Claude Code) reads the output, analyses each region,
        and feeds findings back via ``vibeaudit report``.
        """
        files = self._collect_files(since)
        vuln_classes = [VulnClass(c) for c in self.config.scan.vuln_classes]
        project_context = self._detect_project_context(files) if files else {}

        extractions: list[dict] = []
        for file_path in files:
            try:
                content = file_path.read_text(errors="replace")
            except Exception:
                continue
            target = Path(self.config.scan.target_dir).resolve()
            rel_path = str(file_path.relative_to(target))
            for vc in vuln_classes:
                results = self.extractor.extract(file_path, content, vc)
                for result in results:
                    if not result.snippets:
                        continue
                    extractions.append({
                        "file_path": rel_path,
                        "vuln_class": vc.value,
                        "route_path": result.context.get("route_path", ""),
                        "http_method": result.context.get("http_method", ""),
                        "language": result.snippets[0].language,
                        "snippets": [
                            {
                                "file_path": s.file_path,
                                "start_line": s.start_line,
                                "end_line": s.end_line,
                                "content": s.content,
                                "language": s.language,
                            }
                            for s in result.snippets
                        ],
                    })

        if not self.quiet:
            self.console.print(f"[bold]Extracted {len(extractions)} code regions from {len(files)} files[/bold]")
            self.console.print(f"[dim]Vulnerability classes: {len(vuln_classes)}[/dim]")

        return {
            "version": "0.1.0",
            "project": {
                "target_dir": self.config.scan.target_dir,
                "framework": project_context.get("framework", "unknown"),
                "language": project_context.get("language", "unknown"),
                "files_scanned": len(files),
            },
            "vuln_classes": [vc.value for vc in vuln_classes],
            "extractions": extractions,
        }

    async def dry_run(self, since: str | None = None) -> ScanResult:
        """Show what would be scanned without calling LLM."""
        files = self._collect_files(since)
        vuln_classes = [VulnClass(c) for c in self.config.scan.vuln_classes]

        total_snippets = 0
        for file_path in files:
            try:
                content = file_path.read_text(errors="replace")
            except Exception:
                continue
            for vc in vuln_classes:
                results = self.extractor.extract(file_path, content, vc)
                for r in results:
                    total_snippets += len(r.snippets)

        self.console.print(f"\n[bold]Dry Run Summary[/bold]")
        self.console.print(f"  Files: {len(files)}")
        self.console.print(f"  Classes: {len(vuln_classes)}")
        self.console.print(f"  Code regions: {total_snippets}")
        self.console.print(f"  Provider: {self.config.provider.name}")
        self.console.print(f"  Model: {self.config.provider.model or '(default)'}")

        return ScanResult(
            scanned_files=len(files),
            scanned_classes=[vc.value for vc in vuln_classes],
        )

    async def _analyse_snippet(self, provider, vc, extraction: ExtractionResult, project_ctx: dict) -> list[Finding]:
        """Send a single extraction to the LLM for analysis."""
        code = "\n\n".join(s.content for s in extraction.snippets)
        file_path = extraction.snippets[0].file_path if extraction.snippets else ""
        language = extraction.snippets[0].language if extraction.snippets else "unknown"

        system_prompt, user_prompt, prompt_version = self.prompt_loader.render_full_prompt(
            vuln_class=vc,
            code=code,
            file_path=file_path,
            language=language,
            framework=project_ctx.get("framework", "unknown"),
            route_path=extraction.context.get("route_path", ""),
            http_method=extraction.context.get("http_method", ""),
            additional_context=extraction.context,
        )

        messages = [{"role": "user", "content": user_prompt}]

        response = await provider.complete(
            system=system_prompt,
            messages=messages,
            max_tokens=self.config.provider.max_tokens,
            temperature=self.config.provider.temperature,
        )

        await self.cost_tracker.record(response.model, response.input_tokens, response.output_tokens)

        return self._parse_response(
            response.content, vc, extraction, prompt_version, response.model,
            response.input_tokens + response.output_tokens,
        )

    def _parse_response(self, content: str, vc: VulnClass, extraction: ExtractionResult,
                        prompt_version: str, model: str, tokens: int) -> list[Finding]:
        """Parse LLM JSON response into Finding objects."""
        json_str = content
        fence_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", content, re.DOTALL)
        if fence_match:
            json_str = fence_match.group(1)

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            obj_match = re.search(r"\{.*\}", content, re.DOTALL)
            if obj_match:
                try:
                    data = json.loads(obj_match.group())
                except json.JSONDecodeError:
                    return []
            else:
                return []

        if not isinstance(data, dict) or not data.get("is_vulnerable", False):
            return []

        try:
            finding = Finding(
                vuln_class=vc,
                severity=Severity(data.get("severity", "medium").lower()),
                confidence=Confidence(data.get("confidence", "medium").lower()),
                title=data.get("title", f"Potential {vc.value}"),
                description=data.get("description", ""),
                attack_scenario=data.get("attack_scenario", ""),
                impact=data.get("impact", ""),
                remediation=data.get("remediation", ""),
                fix_example=data.get("fix_example", ""),
                snippets=extraction.snippets,
                cwe_id=data.get("cwe_id", ""),
                owasp_category=data.get("owasp_category", ""),
                affected_lines=data.get("affected_lines", []),
                prompt_version=prompt_version,
                model=model,
                tokens_used=tokens,
                reasoning=data.get("reasoning", ""),
                false_positive_likelihood=data.get("false_positive_likelihood", ""),
                raw_response=content,
            )
            return [finding]
        except (ValueError, KeyError):
            return []

    def _collect_files(self, since: str | None = None) -> list[Path]:
        """Walk target dir, apply include/exclude globs, respect max_file_size."""
        target = Path(self.config.scan.target_dir).resolve()
        if not target.is_dir():
            return []

        changed_files: set[str] | None = None
        if since:
            try:
                import git
                repo = git.Repo(str(target), search_parent_directories=True)
                diffs = repo.git.diff("--name-only", since, "HEAD")
                changed_files = set(diffs.strip().split("\n")) if diffs.strip() else set()
            except Exception:
                changed_files = None

        max_size = self.config.scan.max_file_size_kb * 1024
        files: list[Path] = []

        for path in target.rglob("*"):
            if not path.is_file():
                continue
            rel = str(path.relative_to(target))

            if any(fnmatch.fnmatch(rel, pat) for pat in self.config.scan.exclude):
                continue
            if not any(fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(rel, pat.replace("**/", "")) for pat in self.config.scan.include):
                continue
            try:
                if path.stat().st_size > max_size:
                    continue
            except OSError:
                continue
            if changed_files is not None and rel not in changed_files:
                continue

            files.append(path)

        return sorted(files)

    def _detect_project_context(self, files: list[Path]) -> dict:
        """Detect language, framework, ORM, auth mechanism."""
        context = {"language": "unknown", "framework": "unknown"}

        sample = ""
        for f in files[:20]:
            try:
                sample += f.read_text(errors="replace")[:2000]
            except Exception:
                continue

        from vibeaudit.extractor import FRAMEWORK_PATTERNS
        for fw, patterns in FRAMEWORK_PATTERNS.items():
            for p in patterns:
                if re.search(p, sample):
                    context["framework"] = fw
                    break
            if context["framework"] != "unknown":
                break

        from vibeaudit.extractor import LANG_MAP
        lang_counts: dict[str, int] = {}
        for f in files:
            lang = LANG_MAP.get(f.suffix, "")
            if lang:
                lang_counts[lang] = lang_counts.get(lang, 0) + 1
        if lang_counts:
            context["language"] = max(lang_counts, key=lang_counts.get)  # type: ignore[arg-type]

        return context

    def _apply_baseline(self, findings: list[Finding]) -> list[Finding]:
        """Filter out baselined findings."""
        baseline_path = Path(self.config.scan.target_dir) / self.config.baseline.path
        if not baseline_path.exists():
            return findings
        try:
            from vibeaudit.baseline import load_baseline
            baseline_ids = load_baseline(baseline_path)
            return [f for f in findings if f.id not in baseline_ids]
        except Exception:
            return findings

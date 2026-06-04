"""CLI entrypoint — click commands, flags, dispatch."""

from __future__ import annotations

import sys

import click
from rich.console import Console

from vibetest import __version__
from vibetest.config import load_config
from vibetest.models import Severity


class VibetestGroup(click.Group):
    """Custom group that treats unknown subcommands as scan targets."""

    def parse_args(self, ctx, args):
        if args and args[0] not in self.commands and not args[0].startswith("-"):
            args = ["scan", *args]
        if not args:
            args = ["scan"]
        return super().parse_args(ctx, args)


@click.group(cls=VibetestGroup, invoke_without_command=True)
@click.version_option(__version__, prog_name="vibetest")
@click.pass_context
def main(ctx):
    """vibetest — test quality auditor for AI-generated codebases."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(scan)


@main.command()
@click.argument("target", default=".")
@click.option("--runners", default=None, help="Run only named runners (comma-separated)")
@click.option("--skip", default=None, help="Skip named runners (comma-separated)")
@click.option(
    "--fail-on",
    type=click.Choice(["critical", "high", "medium", "low", "info"], case_sensitive=False),
    default=None,
    help="Exit 1 threshold (default: high)",
)
@click.option(
    "--output",
    "output_format",
    type=click.Choice(["table", "json", "md"], case_sensitive=False),
    default=None,
    help="Report format (default: table)",
)
@click.option("--output-file", default=None, help="Write report to file")
@click.option("--config", "config_path", default=None, help="Config file path")
@click.option("--fix", is_flag=True, help="Include remediation hints")
@click.option("--json-pretty", is_flag=True, help="Pretty-print JSON output")
@click.option("--quiet", is_flag=True, help="Suppress progress, findings only")
@click.option("--verbose", is_flag=True, help="Debug output")
def scan(target, runners, skip, fail_on, output_format, output_file, config_path,
         fix, json_pretty, quiet, verbose):
    """Scan a directory for test quality issues (default command)."""
    overrides = {}
    if fail_on:
        overrides["fail_on"] = Severity(fail_on.upper())
    if output_format:
        overrides["output"] = output_format
    if output_file:
        overrides["output_file"] = output_file
    if fix:
        overrides["fix"] = True
    if json_pretty:
        overrides["json_pretty"] = True
    if quiet:
        overrides["quiet"] = True
    if verbose:
        overrides["verbose"] = True
    if runners:
        overrides["runners_include"] = [r.strip() for r in runners.split(",")]
    if skip:
        overrides["runners_exclude"] = [r.strip() for r in skip.split(",")]

    config = load_config(config_path=config_path, target_dir=target, **overrides)
    console = Console(quiet=config.quiet)

    from vibetest.scanner import Scanner

    scanner = Scanner(target, config)
    result = scanner.scan()

    _render_output(result, config, console)

    sys.exit(result.exit_code)


def _render_output(result, config, console):
    """Dispatch to the appropriate reporter."""
    from vibetest.reporters.table import TableReporter
    from vibetest.reporters.json_reporter import JsonReporter
    from vibetest.reporters.markdown import MarkdownReporter

    reporters = {
        "table": TableReporter,
        "json": JsonReporter,
        "md": MarkdownReporter,
    }

    reporter_cls = reporters.get(config.output, TableReporter)
    reporter = reporter_cls(result, config)

    if config.output_file:
        content = reporter.render_to_string()
        with open(config.output_file, "w") as f:
            f.write(content)
        if not config.quiet:
            console.print(f"Report written to {config.output_file}")
    else:
        reporter.render(console)


if __name__ == "__main__":
    main()

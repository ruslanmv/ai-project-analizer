"""
Entry-point module so that you can simply run

    python -m src /path/to/my_archive.zip

from anywhere.  It parses CLI flags, loads settings, spins up a BeeAI
workflow defined in `workflows.py`, prints live agent events, and exits
with a non-zero status code on any unrecoverable error.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict

try:
    from rich.console import Console
    from rich.panel import Panel
except ImportError:  # pragma: no cover
    # Fallback: cheap stub -- just use plain prints
    class _DummyConsole:
        def print(self, *a, **kw):  # noqa: D401
            print(*a)

    class _DummyPanel(str):  # noqa: D401
        pass

    Console = _DummyConsole  # type: ignore
    Panel = _DummyPanel      # type: ignore

# Local imports
from .config import settings
from .workflows import run_workflow

# --------------------------------------------------------------------------- #
# Configure logger for this module
# --------------------------------------------------------------------------- #
LOG = logging.getLogger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ai-project-analizer",
        description="Analyse a ZIPped code project and emit tree + per-file summaries + global overview.",
    )
    p.add_argument(
        "zip_path",
        type=Path,
        help="Path to the .zip archive you want to analyse",
    )
    p.add_argument(
        "--raw",
        action="store_true",
        help="Do not pretty-print with Rich, just dump JSON",
    )
    return p


def main(argv: list[str] | None = None) -> None:  # noqa: D401
    # Configure basic logging if not already configured
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format=(
            "%(asctime)s | %(levelname)s | %(name)s | "
            "%(module)s.%(funcName)s:%(lineno)d | ★ %(message)s"
        ),
        datefmt="%H:%M:%S",
        force=True,
    )
    LOG.info(">>> Starting CLI entry-point")

    args = build_arg_parser().parse_args(argv)
    LOG.info("Parsed arguments: zip_path=%r, raw=%r", args.zip_path, args.raw)

    console = Console()
    if not args.zip_path.exists():
        LOG.error("Archive %r does not exist", args.zip_path)
        console.print(Panel(f"[red]Archive {args.zip_path} does not exist[/]"))
        sys.exit(2)
    LOG.info("Archive %r exists, proceeding with analysis", args.zip_path)

    try:
        LOG.info(
            "Calling run_workflow with zip_path=%r, model=%r, print_events=%r",
            args.zip_path,
            settings.BEEAI_MODEL,
            not args.raw,
        )
        artifacts: Dict[str, Any] = run_workflow(
            zip_path=args.zip_path,
            model=settings.BEEAI_MODEL,
            print_events=not args.raw,
        )
        LOG.info("run_workflow completed successfully, received artifacts")
    except Exception as exc:  # pragma: no cover
        LOG.exception("Fatal error while running workflow: %s", exc)
        console.print(Panel(f"[bold red]Fatal error:[/] {exc}"))
        sys.exit(1)

    # -- Pretty output ---------------------------------------------------
    if args.raw:
        LOG.info("Raw flag set; dumping JSON output")
        # Dump everything as JSON to stdout
        import json

        print(json.dumps(artifacts, indent=2))
    else:
        LOG.info("Pretty-printing directory tree")
        console.rule("[bold green]Directory tree")
        console.print(artifacts["tree_text"])

        LOG.info("Pretty-printing per-file synopsis")
        console.rule("[bold green]Per-file synopsis")
        for entry in artifacts["file_summaries"]:
            LOG.debug(
                "Printing summary for %r: kind=%r, summary=%r",
                entry.get("rel_path"),
                entry.get("kind"),
                entry.get("summary"),
            )
            console.print(
                f"[cyan]{entry['rel_path']}[/]  "
                f"({entry['kind']})  {entry['summary']}"
            )

        LOG.info("Pretty-printing global project summary")
        console.rule("[bold green]Global project summary")
        console.print(artifacts["project_summary"])

    LOG.info("Analysis complete; exiting")
    sys.exit(0)


if __name__ == "__main__":  # pragma: no cover
    main()

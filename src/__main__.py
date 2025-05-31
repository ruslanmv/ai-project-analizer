"""
Entry-point module so that you can simply run

    python -m src /path/to/my_archive.zip

from anywhere.  It parses CLI flags, loads settings, spins up a BeeAI
workflow defined in `workflows.py`, prints live agent events, and exits
with a non-zero status code on any unrecoverable error.
"""

from __future__ import annotations

import argparse
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
    args = build_arg_parser().parse_args(argv)

    console = Console()
    if not args.zip_path.exists():
        console.print(Panel(f"[red]Archive {args.zip_path} does not exist[/]"))
        sys.exit(2)

    try:
        artifacts: Dict[str, Any] = run_workflow(
            zip_path=args.zip_path,
            model=settings.BEEAI_MODEL,
            print_events=not args.raw,
        )
    except Exception as exc:  # pragma: no cover
        console.print(Panel(f"[bold red]Fatal error:[/] {exc}"))
        sys.exit(1)

    # -- Pretty output ---------------------------------------------------
    if args.raw:
        # Dump everything as JSON to stdout
        import json

        print(json.dumps(artifacts, indent=2))
    else:
        console.rule("[bold green]Directory tree")
        console.print(artifacts["tree_text"])

        console.rule("[bold green]Per-file synopsis")
        for entry in artifacts["file_summaries"]:
            console.print(
                f"[cyan]{entry['rel_path']}[/]  "
                f"({entry['kind']})  {entry['summary']}"
            )

        console.rule("[bold green]Global project summary")
        console.print(artifacts["project_summary"])

    sys.exit(0)


if __name__ == "__main__":  # pragma: no cover
    main()

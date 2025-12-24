"""
Beautiful CLI application using Typer and Rich.

Provides an intuitive command-line interface with:
- Rich formatting and colors
- Progress bars and spinners
- Formatted tables for results
- Interactive prompts
- Comprehensive help
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

from ..core.config import settings
from ..core.exceptions import AnalyzerError
from ..core.logging import get_logger
from ..domain.models import FileAnalysisResult

# Initialize CLI components
app = typer.Typer(
    name="ai-analyzer",
    help="⚡ AI Project Analyzer - Transform any codebase into actionable insights",
    add_completion=True,
    rich_markup_mode="rich",
)
console = Console()
logger = get_logger(__name__)


def print_banner() -> None:
    """Display welcome banner."""
    banner = """
    ╔══════════════════════════════════════════════════════════════════╗
    ║                                                                  ║
    ║        ⚡ AI PROJECT ANALYZER                                     ║
    ║                                                                  ║
    ║        Enterprise-Grade Codebase Analysis                        ║
    ║        Powered by Multi-Agent AI                                 ║
    ║                                                                  ║
    ╚══════════════════════════════════════════════════════════════════╝
    """
    console.print(Panel(banner, style="bold blue", border_style="blue"))


def print_analysis_results(
    tree_text: str,
    file_summaries: list[FileAnalysisResult],
    project_summary: str,
) -> None:
    """
    Display analysis results in beautiful format.

    Args:
        tree_text: Directory tree visualization
        file_summaries: File analysis results
        project_summary: Project overview
    """
    # 1. Display directory tree
    console.print("\n")
    console.print(
        Panel(
            tree_text,
            title="📁 Project Structure",
            border_style="green",
            expand=False,
        )
    )

    # 2. Display file summaries in table
    console.print("\n")
    table = Table(
        title="📄 File Analysis",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        border_style="cyan",
    )
    table.add_column("Path", style="yellow", no_wrap=False)
    table.add_column("Type", style="magenta", width=12)
    table.add_column("Lines", justify="right", style="green", width=8)
    table.add_column("Summary", style="white", no_wrap=False)

    for file_info in file_summaries[:50]:  # Limit to first 50
        table.add_row(
            file_info.rel_path,
            file_info.kind.value,
            str(file_info.lines),
            file_info.summary[:100],
        )

    if len(file_summaries) > 50:
        table.add_row(
            "...",
            f"+{len(file_summaries) - 50} more",
            "...",
            "",
            style="dim",
        )

    console.print(table)

    # 3. Display project summary
    console.print("\n")
    console.print(
        Panel(
            project_summary,
            title="🎯 Project Overview",
            border_style="blue",
            expand=False,
        )
    )


@app.command()
def analyze(
    zip_path: Annotated[
        Path,
        typer.Argument(
            help="Path to ZIP file containing the codebase to analyze",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    model: Annotated[
        Optional[str],
        typer.Option(
            "--model",
            "-m",
            help="LLM model to use (e.g., 'openai/gpt-4o', 'ollama/llama3')",
        ),
    ] = None,
    output: Annotated[
        Optional[Path],
        typer.Option(
            "--output",
            "-o",
            help="Output file path for JSON results",
        ),
    ] = None,
    no_cleanup: Annotated[
        bool,
        typer.Option(
            "--no-cleanup",
            help="Keep temporary extracted files",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose logging",
        ),
    ] = False,
) -> None:
    """
    Analyze a codebase ZIP file and generate insights.

    This command processes a ZIP archive containing source code and produces:
    - A colorized directory tree
    - Per-file summaries with kind classification
    - A comprehensive project overview
    """
    print_banner()

    # Lazy import to avoid circular dependencies
    from ..services.workflow import analyze_codebase

    # Update settings
    if verbose:
        settings.log_level = "DEBUG"
    if no_cleanup:
        settings.delete_temp_after_run = False

    model_to_use = model or settings.beeai_model

    console.print(f"\n[cyan]📦 Analyzing:[/cyan] {zip_path}")
    console.print(f"[cyan]🤖 Model:[/cyan] {model_to_use}")
    console.print(f"[cyan]⚙️  Environment:[/cyan] {settings.environment}\n")

    # Create progress bar
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Analyzing codebase...", total=None)

        try:
            # Run analysis
            results = analyze_codebase(
                zip_path=zip_path,
                model=model_to_use,
            )

            progress.update(task, completed=True)
            console.print("✅ [green]Analysis completed successfully![/green]\n")

            # Display results
            print_analysis_results(
                tree_text=results.tree_text,
                file_summaries=results.file_summaries,
                project_summary=results.project_summary,
            )

            # Save to file if requested
            if output:
                import json

                output.write_text(json.dumps(results.to_dict(), indent=2))
                console.print(f"\n💾 [green]Results saved to:[/green] {output}")

        except AnalyzerError as e:
            progress.stop()
            console.print(f"\n❌ [red]Analysis failed:[/red] {e.message}")
            if verbose and e.context:
                console.print(f"[dim]Context: {e.context}[/dim]")
            logger.error("analysis_failed", error=str(e), **e.context)
            raise typer.Exit(1)
        except Exception as e:
            progress.stop()
            console.print(f"\n❌ [red]Unexpected error:[/red] {e}")
            logger.exception("unexpected_error")
            raise typer.Exit(1)


@app.command()
def version() -> None:
    """Display version information."""
    version_text = Text()
    version_text.append(f"{settings.app_name}\n", style="bold blue")
    version_text.append(f"Version: {settings.app_version}\n", style="green")
    version_text.append(f"Environment: {settings.environment}\n", style="yellow")
    version_text.append(f"Default Model: {settings.beeai_model}\n", style="cyan")

    console.print(Panel(version_text, border_style="blue"))


@app.command()
def config() -> None:
    """Display current configuration."""
    config_table = Table(
        title="⚙️  Current Configuration",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    config_table.add_column("Setting", style="yellow")
    config_table.add_column("Value", style="green")

    config_items = [
        ("Model", settings.beeai_model),
        ("Environment", settings.environment),
        ("Log Level", settings.log_level),
        ("ZIP Size Limit", f"{settings.zip_size_limit_mb} MB"),
        ("Max Files", str(settings.max_files_to_analyze)),
        ("Cleanup Temp", str(settings.delete_temp_after_run)),
    ]

    for key, value in config_items:
        config_table.add_row(key, str(value))

    console.print(config_table)


@app.command()
def server(
    host: Annotated[
        str,
        typer.Option(help="Host to bind the server to"),
    ] = "0.0.0.0",
    port: Annotated[
        int,
        typer.Option(help="Port to bind the server to"),
    ] = 8000,
    reload: Annotated[
        bool,
        typer.Option(help="Enable auto-reload on code changes"),
    ] = False,
) -> None:
    """
    Start the web server for browser-based analysis.

    Launches a FastAPI server with a web interface for uploading
    and analyzing codebases.
    """
    import uvicorn

    console.print(f"\n🚀 [green]Starting web server...[/green]")
    console.print(f"[cyan]📍 URL:[/cyan] http://{host}:{port}")
    console.print(f"[cyan]📖 API Docs:[/cyan] http://{host}:{port}/docs\n")

    try:
        uvicorn.run(
            "ai_project_analyzer.web.app:app",
            host=host,
            port=port,
            reload=reload,
            log_level=settings.log_level.lower(),
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped by user[/yellow]")
    except Exception as e:
        console.print(f"\n❌ [red]Server error:[/red] {e}")
        raise typer.Exit(1)


def main() -> None:
    """Main entry point for CLI."""
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]Fatal error:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

"""
rich_printer_tool.py

Wraps Rich library calls to render a directory tree in color/ASCII.
If Rich is unavailable or the process is headless, falls back to plain‐text.

Functions:
  • render_tree(paths, base_dir) → str
      Renders a Rich Tree (or ASCII fallback) showing the hierarchy of all
      discovered file paths under base_dir.

Imported by:
  • tree_builder_agent.py

Dependencies:
  • rich (optional)
"""

from __future__ import annotations

from pathlib import Path
from typing import List

try:
    from rich.tree import Tree
    from rich.console import Console
    RICH_AVAILABLE = True
except ImportError:
    Tree = None  # type: ignore
    Console = None  # type: ignore
    RICH_AVAILABLE = False


def render_tree(paths: List[Path], base_dir: Path) -> str:
    """
    Given a list of absolute file Paths and the base directory, build a
    hierarchical tree representation.

    If 'rich' is installed, returns a colored ASCII‐art tree using Rich.
    Otherwise, returns a simple indentation‐based ASCII representation.

    Parameters
    ----------
    paths : List[Path]
      All file paths discovered under base_dir.
    base_dir : Path
      The root directory to which all paths are relative.

    Returns
    -------
    str
      The textual tree representation ready for printing or storing.
    """
    if RICH_AVAILABLE and Tree and Console:
        console = Console(record=True, width=120)
        root_name = base_dir.name or str(base_dir)
        tree = Tree(f"[bold magenta]{root_name}/")

        # Sort paths so parents come before children
        sorted_paths = sorted(paths, key=lambda p: (len(p.relative_to(base_dir).parts), p.name))
        nodes_map: dict[tuple[str, ...], Tree] = {}
        nodes_map[(root_name,)] = tree

        for abs_path in sorted_paths:
            rel = abs_path.relative_to(base_dir)
            parts = rel.parts
            # Walk the tree structure, creating branches as needed
            parent_key = (root_name,)
            parent_node = tree
            for idx, part in enumerate(parts):
                current_key = parent_key + (part,)
                if current_key not in nodes_map:
                    # Add new branch if intermediate, or leaf if last
                    label = f"{part}/" if idx < len(parts) - 1 else part
                    new_node = parent_node.add(label)
                    nodes_map[current_key] = new_node
                parent_node = nodes_map[current_key]
                parent_key = current_key

        console.print(tree)
        return console.export_text()
    else:
        # Fallback: simple ASCII indent, no coloring
        tree_lines: list[str] = [f"{base_dir.name}/"]
        sorted_paths = sorted(paths, key=lambda p: (len(p.relative_to(base_dir).parts), p.name))
        last_parents: dict[Path, str] = {}
        for abs_path in sorted_paths:
            rel = abs_path.relative_to(base_dir)
            indent = "  " * (len(rel.parts) - 1)
            tree_lines.append(f"{indent}{rel.name}")
        return "\n".join(tree_lines)

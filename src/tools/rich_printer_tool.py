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

import logging
from pathlib import Path
from typing import List

# --------------------------------------------------------------------------- #
# Configure logger for this module
# --------------------------------------------------------------------------- #
LOG = logging.getLogger(__name__)

try:
    from rich.tree import Tree
    from rich.console import Console
    RICH_AVAILABLE = True
    LOG.info("[rich_printer_tool] Rich is available and will be used for rendering")
except ImportError:
    Tree = None  # type: ignore
    Console = None  # type: ignore
    RICH_AVAILABLE = False
    LOG.warning("[rich_printer_tool] Rich is not available; falling back to ASCII")

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
    LOG.info("[rich_printer_tool] render_tree() called with %d paths, base_dir=%r", len(paths), base_dir)

    # Sort paths so parents come before children
    try:
        sorted_paths = sorted(paths, key=lambda p: (len(p.relative_to(base_dir).parts), p.name))
    except Exception as e:
        LOG.error("[rich_printer_tool] Error sorting paths: %s", e, exc_info=True)
        sorted_paths = paths.copy()
    LOG.debug("[rich_printer_tool] Sorted paths: %s", [str(p.relative_to(base_dir)) for p in sorted_paths])

    if RICH_AVAILABLE and Tree and Console:
        LOG.info("[rich_printer_tool] Building tree using Rich")
        try:
            console = Console(record=True, width=120)
            root_name = base_dir.name or str(base_dir)
            tree = Tree(f"[bold magenta]{root_name}/")

            nodes_map: dict[tuple[str, ...], Tree] = {}
            nodes_map[(root_name,)] = tree

            for abs_path in sorted_paths:
                try:
                    rel = abs_path.relative_to(base_dir)
                except Exception as e:
                    LOG.warning("[rich_printer_tool] Path %r is not under base_dir %r: %s", abs_path, base_dir, e)
                    continue

                parts = rel.parts
                parent_key = (root_name,)
                parent_node = tree
                for idx, part in enumerate(parts):
                    current_key = parent_key + (part,)
                    if current_key not in nodes_map:
                        label = f"{part}/" if idx < len(parts) - 1 else part
                        new_node = parent_node.add(label)
                        nodes_map[current_key] = new_node
                        LOG.debug("[rich_printer_tool] Added node %r under parent %r", label, parent_key)
                    parent_node = nodes_map[current_key]
                    parent_key = current_key

            console.print(tree)
            tree_text: str = console.export_text()
            LOG.info("[rich_printer_tool] Rich tree rendered successfully (length=%d chars)", len(tree_text))
            return tree_text
        except Exception as e:
            LOG.exception("[rich_printer_tool] Exception while rendering with Rich: %s; falling back to ASCII", e)

    # Fallback: simple ASCII indent, no coloring
    LOG.info("[rich_printer_tool] Using ASCII fallback to build tree")
    try:
        tree_lines: list[str] = [f"{base_dir.name}/"]
        for abs_path in sorted_paths:
            try:
                rel = abs_path.relative_to(base_dir)
            except Exception as e:
                LOG.warning("[rich_printer_tool] Path %r is not under base_dir %r: %s", abs_path, base_dir, e)
                continue
            indent = "  " * (len(rel.parts) - 1)
            line = f"{indent}{rel.name}"
            tree_lines.append(line)
            LOG.debug("[rich_printer_tool] Added ASCII line: %r", line)

        tree_ascii = "\n".join(tree_lines)
        LOG.info("[rich_printer_tool] ASCII tree generated successfully (length=%d chars)", len(tree_ascii))
        return tree_ascii
    except Exception as e:
        LOG.exception("[rich_printer_tool] Unexpected error in ASCII fallback: %s", e)
        return ""

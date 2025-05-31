"""
tree_builder_agent.py
~~~~~~~~~~~~~~~~~~~~~

Accumulates every *FileDiscovered* event, then – once *ExtractionDone*
arrives – builds a Rich directory tree and stores it in BeeAI memory as
'project_tree.txt'.  Finally emits *TreeBuilt*.

Incoming events
---------------
• FileDiscovered     { path: str }
• ExtractionDone     { base_dir: str }

Outgoing events
---------------
• TreeBuilt          { tree_path: str }
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import beeai
from beeai.typing import Event

try:
    from rich.tree import Tree
    from rich.console import Console
except ImportError:  # pragma: no cover
    Tree = None  # type: ignore
    Console = None  # type: ignore


class TreeBuilderAgent(beeai.Agent):
    name = "tree_builder"

    def __init__(self) -> None:  # noqa: D401
        super().__init__()
        self._paths: List[Path] = []
        self._base_dir: Path | None = None

    # ---------------- Event handling ----------------
    def handle(self, event: Event) -> None:  # noqa: D401
        if event["type"] == "FileDiscovered":
            self._paths.append(Path(event["path"]))
        elif event["type"] == "ExtractionDone":
            self._base_dir = Path(event["base_dir"])
            self._build_and_emit_tree()

    # ---------------- Helpers ----------------
    def _build_and_emit_tree(self) -> None:
        if not self._base_dir:  # pragma: no cover
            return

        # Build a rich.Tree or fall back to plain text
        if Tree and Console:
            console = Console(record=True, width=120)
            tree = Tree(f"[bold magenta]{self._base_dir.name}/")
            self._add_branches(tree, self._paths)
            console.print(tree)
            tree_text: str = console.export_text()
        else:  # Simple fallback
            tree_text = self._fallback_ascii_tree()

        # Persist in memory and as artifact
        self.memory["project_tree.txt"] = tree_text
        self.emit("TreeBuilt", {"tree_path": "project_tree.txt"})

    # -------------- Internal recursive builders --------------
    @staticmethod
    def _add_branches(tree: "Tree", paths: List[Path]) -> None:  # type: ignore
        paths_sorted = sorted(paths, key=lambda p: (p.is_file(), p.parts))
        for p in paths_sorted:
            rel = p.relative_to(paths_sorted[0].parents[len(p.parts)])
            branch = tree
            for part in rel.parts[:-1]:
                # Walk existing children or create new
                next_child = None
                for child in branch.children:
                    if child.label.plain == f"{part}/":
                        next_child = child
                        break
                if next_child is None:
                    next_child = branch.add(f"{part}/")
                branch = next_child
            # finally add leaf
            branch.add(rel.parts[-1])

    def _fallback_ascii_tree(self) -> str:
        lines: Dict[Path, List[str]] = defaultdict(list)
        base = self._base_dir or Path("/tmp")
        for p in sorted(self._paths):
            rel = p.relative_to(base)
            indent = "  " * (len(rel.parts) - 1)
            lines[rel.parent].append(f"{indent}{rel.name}")
        out = [f"{base.name}/"]
        for parts in lines.values():
            out.extend(parts)
        return "\n".join(out)

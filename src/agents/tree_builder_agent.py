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

# Updated imports to use beeai_framework instead of beeai
from beeai_framework.agent import Agent
from beeai_framework.typing import Event

try:
    from rich.tree import Tree
    from rich.console import Console
except ImportError:  # pragma: no cover
    Tree = None  # type: ignore
    Console = None  # type: ignore


class TreeBuilderAgent(Agent):
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
            self._add_branches(tree, self._paths, self._base_dir)
            console.print(tree)
            tree_text: str = console.export_text()
        else:  # Simple fallback
            tree_text = self._fallback_ascii_tree()

        # Persist in memory and as artifact
        self.memory["project_tree.txt"] = tree_text
        self.emit("TreeBuilt", {"tree_path": "project_tree.txt"})

    # -------------- Internal recursive builders --------------
    @staticmethod
    def _add_branches(tree: "Tree", paths: List[Path], base_dir: Path) -> None:  # type: ignore
        # Sort by depth then name
        paths_sorted = sorted(paths, key=lambda p: (len(p.relative_to(base_dir).parts), p.name))
        node_map: Dict[tuple[str, ...], Tree] = {}
        root_key = (base_dir.name,)
        node_map[root_key] = tree

        for abs_path in paths_sorted:
            rel = abs_path.relative_to(base_dir)
            parent_key = root_key
            parent_node = tree
            for idx, part in enumerate(rel.parts):
                current_key = parent_key + (part,)
                if current_key not in node_map:
                    label = f"{part}/" if idx < len(rel.parts) - 1 else part
                    new_node = parent_node.add(label)
                    node_map[current_key] = new_node
                parent_node = node_map[current_key]
                parent_key = current_key

    def _fallback_ascii_tree(self) -> str:
        lines: Dict[Path, List[str]] = defaultdict(list)
        base = self._base_dir or Path("/tmp")
        for p in sorted(self._paths):
            try:
                rel = p.relative_to(base)
            except Exception:
                continue
            indent = "  " * (len(rel.parts) - 1)
            lines[rel.parent].append(f"{indent}{rel.name}")

        out: List[str] = [f"{base.name}/"]
        for parts in lines.values():
            out.extend(parts)
        return "\n".join(out)

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

import logging
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

# --------------------------------------------------------------------------- #
# Configure logger for this agent
# --------------------------------------------------------------------------- #
LOG = logging.getLogger(__name__)


class TreeBuilderAgent(Agent):
    name = "tree_builder"

    def __init__(self) -> None:  # noqa: D401
        super().__init__()
        self._paths: List[Path] = []
        self._base_dir: Path | None = None
        LOG.info("[tree_builder] Initialized with empty paths list and no base_dir")

    # ---------------- Event handling ----------------
    def handle(self, event: Event) -> None:  # noqa: D401
        LOG.info(">>> [tree_builder] handle() entered. event=%r", event)

        event_type = event.get("type")
        if event_type == "FileDiscovered":
            path = Path(event["path"])
            LOG.debug("[tree_builder] Received FileDiscovered for %r", path)
            self._paths.append(path)
            LOG.info("[tree_builder] Added %r to paths (total now: %d)", path, len(self._paths))

        elif event_type == "ExtractionDone":
            base_dir = event.get("base_dir")
            self._base_dir = Path(base_dir)
            LOG.info("[tree_builder] Received ExtractionDone, base_dir set to %r", self._base_dir)
            self._build_and_emit_tree()

        else:
            LOG.debug("[tree_builder] Ignoring event type %r", event_type)

    # ---------------- Helpers ----------------
    def _build_and_emit_tree(self) -> None:
        LOG.info("[tree_builder] _build_and_emit_tree() called with base_dir=%r and %d paths",
                 self._base_dir, len(self._paths))

        if not self._base_dir:  # pragma: no cover
            LOG.warning("[tree_builder] No base_dir set, cannot build tree")
            return

        # Build a rich.Tree or fall back to plain text
        if Tree and Console:
            LOG.debug("[tree_builder] Using rich to build tree")
            console = Console(record=True, width=120)
            tree = Tree(f"[bold magenta]{self._base_dir.name}/")
            self._add_branches(tree, self._paths, self._base_dir)
            console.print(tree)
            tree_text: str = console.export_text()
            LOG.info("[tree_builder] Rich tree built successfully (length=%d chars)", len(tree_text))
        else:  # Simple fallback
            LOG.debug("[tree_builder] Rich not available, using ASCII fallback")
            tree_text = self._fallback_ascii_tree()
            LOG.info("[tree_builder] Fallback ASCII tree built (length=%d chars)", len(tree_text))

        # Persist in memory and as artifact
        self.memory["project_tree.txt"] = tree_text
        LOG.info("[tree_builder] Stored 'project_tree.txt' in memory (length=%d)", len(tree_text))

        self.emit("TreeBuilt", {"tree_path": "project_tree.txt"})
        LOG.info("[tree_builder] Emitted TreeBuilt with path 'project_tree.txt'")

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
                    LOG.debug("[tree_builder] Added node %r under parent %r", label, parent_key)
                parent_node = node_map[current_key]
                parent_key = current_key

    def _fallback_ascii_tree(self) -> str:
        LOG.debug("[tree_builder] _fallback_ascii_tree() called")
        lines: Dict[Path, List[str]] = defaultdict(list)
        base = self._base_dir or Path("/tmp")
        for p in sorted(self._paths):
            try:
                rel = p.relative_to(base)
            except Exception:
                LOG.warning("[tree_builder] Could not compute relative path for %r", p)
                continue
            indent = "  " * (len(rel.parts) - 1)
            lines[rel.parent].append(f"{indent}{rel.name}")
            LOG.debug("[tree_builder] Fallback: adding line for %r as %r", p, f"{indent}{rel.name}")

        out: List[str] = [f"{base.name}/"]
        for parts in lines.values():
            out.extend(parts)
        tree_ascii = "\n".join(out)
        LOG.info("[tree_builder] Fallback ASCII tree generated (length=%d chars)", len(tree_ascii))
        return tree_ascii

"""
file_analysis_agent.py
~~~~~~~~~~~~~~~~~~~~~~

Parses text/code files, extracts a concise summary, and appends the result
to BeeAI memory (key: 'file_summaries.json').  Emits *FileAnalysed* for each
file so that the summariser can react incrementally.

Incoming events
---------------
• FileForAnalysis    { path: str, score: int }
• TriageComplete     {}

Outgoing events
---------------
• FileAnalysed       { rel_path, kind, summary }
• AnalysisComplete   {}
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any, Dict, List

import beeai
from beeai.typing import Event

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

from ..utils.encoding_helper import read_text_safe  # robust UTF-8 fallback

# --------------------------------------------------------------------------- #
#  Format-specific helpers
# --------------------------------------------------------------------------- #
ASSET_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".mp4", ".ico"}


def summarise_text(text: str, max_chars: int = 160) -> str:
    text = text.strip()
    heading = re.match(r"^#{1,6}\s+(.+)", text)
    if heading:
        return heading.group(1)
    first = re.search(r"[.!?]\s", text)
    if first and first.start() < max_chars:
        return text[: first.end()].strip()
    return (text[: max_chars] + "…") if len(text) > max_chars else text


def analyse_file(path: Path, base: Path) -> Dict[str, str]:
    rel = path.relative_to(base)
    ext = path.suffix.lower()

    if ext in ASSET_EXTS:
        return {"rel_path": str(rel), "kind": "asset", "summary": "(binary skipped)"}

    raw = read_text_safe(path)

    # -------- special parsers ----------
    if ext == ".json":
        try:
            obj = json.loads(raw)
            keys = ", ".join(list(obj)[:5])
            return {
                "rel_path": str(rel),
                "kind": "json",
                "summary": f"JSON with keys: {keys}",
            }
        except Exception:
            pass

    if ext in {".yml", ".yaml"} and yaml:
        try:
            obj = yaml.safe_load(raw)
            keys = ", ".join(list(obj)[:5])
            return {
                "rel_path": str(rel),
                "kind": "yaml",
                "summary": f"YAML with keys: {keys}",
            }
        except Exception:
            pass

    if ext == ".py":
        try:
            module = ast.parse(raw)
            funcs = [n.name for n in module.body if isinstance(n, ast.FunctionDef)]
            classes = [n.name for n in module.body if isinstance(n, ast.ClassDef)]
            parts: List[str] = ["Python"]
            if classes:
                parts.append(f"classes={', '.join(classes[:3])}")
            if funcs:
                parts.append(f"funcs={', '.join(funcs[:3])}")
            return {
                "rel_path": str(rel),
                "kind": "python",
                "summary": "; ".join(parts),
            }
        except SyntaxError:
            pass

    # fallback
    return {
        "rel_path": str(rel),
        "kind": "text",
        "summary": summarise_text(raw),
    }


class FileAnalysisAgent(beeai.Agent):
    name = "file_analysis"

    def __init__(self) -> None:  # noqa: D401
        super().__init__()
        self._base_dir: Path | None = None
        self._results: List[Dict[str, str]] = []

    def handle(self, event: Event) -> None:  # noqa: D401
        if event["type"] == "FileForAnalysis":
            self._analyse(Path(event["path"]))
        elif event["type"] == "ExtractionDone":
            self._base_dir = Path(event["base_dir"])
        elif event["type"] == "TriageComplete":
            self._finalise()

    # ---------------- helpers ---------------
    def _analyse(self, path: Path) -> None:
        base = self._base_dir or path.parents[1]  # best guess
        result = analyse_file(path, base)
        self._results.append(result)
        self.emit("FileAnalysed", result)

    def _finalise(self) -> None:
        # Persist the cumulative JSON array to memory
        self.memory["file_summaries.json"] = json.dumps(self._results, indent=2)
        self.emit("AnalysisComplete", {})

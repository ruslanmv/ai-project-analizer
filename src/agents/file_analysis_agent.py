# src/agents/file_analysis_agent.py

"""
file_analysis_agent.py
~~~~~~~~~~~~~~~~~~~~~~

Parses text/code files, extracts a concise summary, and appends the result
to an internal memory dictionary (key: 'file_summaries.json'). Emits *FileAnalysed*
for each file so that the summariser can react incrementally.

Incoming events
---------------
• FileForAnalysis    { path: str, score: int }
• TriageComplete     {}

Outgoing events
---------------
• FileAnalysed       { rel_path: str, kind: str, summary: str }
• AnalysisComplete   {}
"""

from __future__ import annotations

import ast
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

from ..utils.encoding_helper import read_text_safe  # robust UTF-8 fallback

# --------------------------------------------------------------------------- #
# Configure logger for this agent
# --------------------------------------------------------------------------- #
LOG = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
#  Format‐specific helpers
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

    LOG.debug("[file_analysis] analyse_file() called for %r, base=%r", path, base)

    if ext in ASSET_EXTS:
        LOG.info("[file_analysis] Skipping binary asset %r", path)
        return {"rel_path": str(rel), "kind": "asset", "summary": "(binary skipped)"}

    raw = read_text_safe(path)
    LOG.debug("[file_analysis] Read %d characters from %r", len(raw), path)

    # -------- special parsers ----------
    if ext == ".json":
        try:
            obj = json.loads(raw)
            keys = ", ".join(list(obj)[:5])
            LOG.info("[file_analysis] JSON parsed for %r, keys: %r", path, keys)
            return {
                "rel_path": str(rel),
                "kind": "json",
                "summary": f"JSON with keys: {keys}",
            }
        except Exception as e:
            LOG.warning("[file_analysis] JSON parse failed for %r: %s", path, e)

    if ext in {".yml", ".yaml"} and yaml:
        try:
            obj = yaml.safe_load(raw)
            keys = ", ".join(list(obj)[:5])
            LOG.info("[file_analysis] YAML parsed for %r, keys: %r", path, keys)
            return {
                "rel_path": str(rel),
                "kind": "yaml",
                "summary": f"YAML with keys: {keys}",
            }
        except Exception as e:
            LOG.warning("[file_analysis] YAML parse failed for %r: %s", path, e)

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
            summary = "; ".join(parts)
            LOG.info("[file_analysis] Python parse for %r, summary: %r", path, summary)
            return {
                "rel_path": str(rel),
                "kind": "python",
                "summary": summary,
            }
        except SyntaxError as e:
            LOG.warning("[file_analysis] Python syntax error for %r: %s", path, e)

    # fallback
    fallback_summary = summarise_text(raw)
    LOG.info("[file_analysis] Fallback text summary for %r: %r", path, fallback_summary)
    return {
        "rel_path": str(rel),
        "kind": "text",
        "summary": fallback_summary,
    }


# --------------------------------------------------------------------------- #
# Minimal Agent base‐class (no beeai_framework dependency)
# --------------------------------------------------------------------------- #
class Agent:
    """
    A minimal stand‐in for the BeeAI Agent base class.
    Subclasses should call self.emit(...) when they want to emit an event.
    """
    def __init__(self) -> None:
        # Initialize an internal memory dict if not already present
        if not hasattr(self, "memory"):
            self.memory: Dict[str, Any] = {}

    def emit(self, event_name: str, payload: Dict[str, Any]) -> None:
        """
        Stub method. Subclasses call this to “emit” events.
        In tests, override with e.g.:
            agent.emit = lambda name,payload: captured.append((name,payload))
        """
        return


class FileAnalysisAgent(Agent):
    name = "file_analysis"

    def __init__(self) -> None:
        super().__init__()
        self._base_dir: Path | None = None
        self._results: List[Dict[str, str]] = []

    def handle(self, event: Dict[str, Any]) -> None:
        """
        event is expected to be a dict with one of:
          • {"type": "FileForAnalysis", "path": str, "score": int}
          • {"type": "TriageComplete"}
          • {"type": "ExtractionDone", "base_dir": str}

        On FileForAnalysis: analyse the file and emit FileAnalysed.
        On TriageComplete: _finalise() to write memory and emit AnalysisComplete.
        On ExtractionDone: record base_dir for relative paths.
        """
        LOG.info(">>> [file_analysis] handle() entered. event=%r", event)

        event_type = event.get("type")
        if event_type == "FileForAnalysis":
            raw_path = event.get("path")
            if raw_path is None:
                LOG.warning("[file_analysis] FileForAnalysis missing 'path' key: %r", event)
                return
            path = Path(raw_path)
            LOG.info("[file_analysis] Received FileForAnalysis for %r", path)
            self._analyse(path)

        elif event_type == "ExtractionDone":
            raw_base = event.get("base_dir")
            if raw_base is None:
                LOG.warning("[file_analysis] ExtractionDone missing 'base_dir' key: %r", event)
                return
            self._base_dir = Path(raw_base)
            LOG.info("[file_analysis] Received ExtractionDone, base_dir set to %r", self._base_dir)

        elif event_type == "TriageComplete":
            LOG.info("[file_analysis] Received TriageComplete, finalising analysis")
            self._finalise()

        else:
            LOG.debug("[file_analysis] Ignoring event type %r", event_type)

    # ---------------- helpers ---------------
    def _analyse(self, path: Path) -> None:
        base = self._base_dir or path.parent
        LOG.debug("[file_analysis] _analyse() called with path=%r, base=%r", path, base)

        result = analyse_file(path, base)
        LOG.info("[file_analysis] Analysis result for %r: %r", path, result)

        self._results.append(result)
        LOG.debug("[file_analysis] Appended result, total results count=%d", len(self._results))

        self.emit("FileAnalysed", result)
        LOG.info("[file_analysis] Emitted FileAnalysed for %r", path)

    def _finalise(self) -> None:
        LOG.info("[file_analysis] _finalise() called, total files analysed=%d", len(self._results))
        try:
            # Persist the cumulative JSON array to memory
            payload = json.dumps(self._results, indent=2)
            self.memory["file_summaries.json"] = payload
            LOG.info("[file_analysis] Stored 'file_summaries.json' in memory (%d bytes)", len(payload))

            self.emit("AnalysisComplete", {})
            LOG.info("[file_analysis] Emitted AnalysisComplete")
        except Exception as e:
            LOG.exception("[file_analysis] Error while finalising and storing summaries: %s", e)

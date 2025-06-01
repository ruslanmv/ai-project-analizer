# src/agents/file_triage_agent.py

"""
file_triage_agent.py
~~~~~~~~~~~~~~~~~~~~~

Assigns a priority score to each discovered file and decides if it should be
analysed (text/code) or skipped (binary/asset). Emits:

  • FileForAnalysis  { path: str, score: int }
  • FileSkipped      { path: str, reason: str }
  • TriageComplete   {}

Incoming events
---------------
• FileDiscovered     { path: str }
• ExtractionDone     { base_dir: str }

Outgoing events
---------------
• FileForAnalysis    { path: str, score: int }
• FileSkipped        { path: str, reason: str }
• TriageComplete     {}
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple

from ..tools.file_io_tool import looks_binary, priority_score, ASSET_SKIP_EXTS

# --------------------------------------------------------------------------- #
# Configure logger for this agent
# --------------------------------------------------------------------------- #
LOG = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Minimal Agent base‐class (no beeai_framework dependency)
# --------------------------------------------------------------------------- #
class Agent:
    """
    A minimal stand‐in for the BeeAI Agent base class.
    Subclasses should call self.emit(...) when they want to emit an event.
    """
    def __init__(self) -> None:
        # by default, emit does nothing. In tests you can monkey‐patch it.
        pass

    def emit(self, event_name: str, payload: Dict[str, Any]) -> None:
        """
        Stub method. Subclasses call this to “emit” events.
        In tests, override with e.g.:
            agent.emit = lambda name,payload: captured.append((name,payload))
        """
        return


class FileTriageAgent(Agent):
    name = "file_triage"

    def __init__(self) -> None:
        super().__init__()
        self._queue: List[Tuple[int, Path]] = []
        self._extraction_done: bool = False
        LOG.info("[file_triage] Initialized with empty queue and extraction_done=False")

    def handle(self, event: Dict[str, Any]) -> None:
        """
        event is expected to be a dict with at least:
            {"type": "FileDiscovered", "path": str} or
            {"type": "ExtractionDone", "base_dir": str}

        • On FileDiscovered, decide skip vs. queue for analysis.
        • On ExtractionDone, emit FileForAnalysis for everything in queue,
          then TriageComplete.
        """
        LOG.info(">>> [file_triage] handle() entered. event=%r", event)

        event_type = event.get("type")
        if event_type == "FileDiscovered":
            raw_path = event.get("path")
            if raw_path is None:
                LOG.warning("[file_triage] FileDiscovered missing 'path' key: %r", event)
                return
            path = Path(raw_path)
            LOG.debug("[file_triage] Received FileDiscovered for %r", path)
            self._handle_file(path)

        elif event_type == "ExtractionDone":
            raw_base = event.get("base_dir")
            if raw_base is None:
                LOG.warning("[file_triage] ExtractionDone missing 'base_dir' key: %r", event)
                return
            LOG.info("[file_triage] Received ExtractionDone with base_dir=%r", raw_base)
            self._extraction_done = True
            self._flush_queue()

        else:
            LOG.debug("[file_triage] Ignoring event type %r", event_type)

    def _handle_file(self, path: Path) -> None:
        """
        Check whether to skip or queue this file. If skipped (binary or asset),
        emit FileSkipped. Otherwise, queue by priority.
        """
        LOG.debug("[file_triage] _handle_file() called with %r", path)

        # Skip binary or known asset extensions
        if looks_binary(path) or path.suffix.lower() in ASSET_SKIP_EXTS:
            LOG.info("[file_triage] Skipping binary/asset file %r", path)
            self.emit("FileSkipped", {"path": str(path), "reason": "binary/asset"})
            LOG.debug("[file_triage] Emitted FileSkipped for %r", path)
            return

        # Otherwise compute a priority score and queue for analysis
        score = priority_score(path)
        LOG.info("[file_triage] Queuing file %r with priority score %d", path, score)
        self._queue.append((score, path))

    def _flush_queue(self) -> None:
        """
        When ExtractionDone arrives, sort the queue descending by score, emit
        FileForAnalysis for each entry, then emit TriageComplete.
        """
        LOG.info("[file_triage] _flush_queue() called, queue length=%d", len(self._queue))

        # Sort descending by score, emit FileForAnalysis
        for score, path in sorted(self._queue, key=lambda t: -t[0]):
            LOG.info("[file_triage] Emitting FileForAnalysis for %r (score=%d)", path, score)
            self.emit(
                "FileForAnalysis",
                {"path": str(path), "score": priority_score(path)},
            )
            LOG.debug("[file_triage] Emitted FileForAnalysis event for %r", path)

        LOG.info("[file_triage] Emitting TriageComplete")
        self.emit("TriageComplete", {})
        LOG.debug("[file_triage] Emitted TriageComplete, handle() exiting")

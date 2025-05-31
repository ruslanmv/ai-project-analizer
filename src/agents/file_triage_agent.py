"""
file_triage_agent.py
~~~~~~~~~~~~~~~~~~~~

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
from typing import List, Tuple

# Updated imports to use beeai_framework instead of beeai
from beeai_framework.agent import Agent
from beeai_framework.typing import Event

from ..tools.file_io_tool import looks_binary, priority_score, ASSET_SKIP_EXTS

# --------------------------------------------------------------------------- #
# Configure logger for this agent
# --------------------------------------------------------------------------- #
LOG = logging.getLogger(__name__)


class FileTriageAgent(Agent):
    name = "file_triage"

    def __init__(self) -> None:
        super().__init__()
        self._queue: List[Tuple[int, Path]] = []
        self._extraction_done: bool = False
        LOG.info("[file_triage] Initialized with empty queue and extraction_done=False")

    def handle(self, event: Event) -> None:
        LOG.info(">>> [file_triage] handle() entered. event=%r", event)

        event_type = event.get("type")
        if event_type == "FileDiscovered":
            path = Path(event["path"])
            LOG.debug("[file_triage] Received FileDiscovered for %r", path)
            self._handle_file(path)
        elif event_type == "ExtractionDone":
            base_dir = event.get("base_dir")
            LOG.info("[file_triage] Received ExtractionDone with base_dir=%r", base_dir)
            self._extraction_done = True
            self._flush_queue()
        else:
            LOG.debug("[file_triage] Ignoring event type %r", event_type)

    def _handle_file(self, path: Path) -> None:
        LOG.debug("[file_triage] _handle_file() called with %r", path)

        # PFloop: skip binary or known asset extensions
        if looks_binary(path) or path.suffix.lower() in ASSET_SKIP_EXTS:
            LOG.info("[file_triage] Skipping binary/asset file %r", path)
            self.emit("FileSkipped", {"path": str(path), "reason": "binary/asset"})
            LOG.debug("[file_triage] Emitted FileSkipped for %r", path)
            return

        # Not skipped: compute priority score
        score = priority_score(path)
        LOG.info("[file_triage] Queuing file %r with priority score %d", path, score)
        self._queue.append((score, path))

    def _flush_queue(self) -> None:
        LOG.info("[file_triage] _flush_queue() called, queue length=%d", len(self._queue))

        # Sort descending by score and emit FileForAnalysis
        for score, path in sorted(self._queue, key=lambda t: -t[0]):
            LOG.info("[file_triage] Emitting FileForAnalysis for %r (score=%d)", path, score)
            self.emit(
                "FileForAnalysis",
                {
                    "path": str(path),
                    "score": priority_score(path),
                },
            )
            LOG.debug("[file_triage] Emitted FileForAnalysis event for %r", path)

        LOG.info("[file_triage] Emitting TriageComplete")
        self.emit("TriageComplete", {})
        LOG.debug("[file_triage] Emitted TriageComplete, handle() exiting")

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

from pathlib import Path
from typing import List, Tuple

# Updated imports to use beeai_framework instead of beeai
from beeai_framework.agent import Agent
from beeai_framework.typing import Event

from ..tools.file_io_tool import looks_binary, priority_score, ASSET_SKIP_EXTS


class FileTriageAgent(Agent):
    name = "file_triage"

    def __init__(self) -> None:
        super().__init__()
        self._queue: List[Tuple[int, Path]] = []
        self._extraction_done: bool = False

    def handle(self, event: Event) -> None:
        if event["type"] == "FileDiscovered":
            self._handle_file(Path(event["path"]))
        elif event["type"] == "ExtractionDone":
            self._extraction_done = True
            self._flush_queue()

    def _handle_file(self, path: Path) -> None:
        # PFloop: skip binary or known asset extensions
        if looks_binary(path) or path.suffix.lower() in ASSET_SKIP_EXTS:
            self.emit("FileSkipped", {"path": str(path), "reason": "binary/asset"})
            return

        # Not skipped: compute priority score
        score = priority_score(path)
        self._queue.append((score, path))

    def _flush_queue(self) -> None:
        # Sort descending by score and emit FileForAnalysis
        for _, path in sorted(self._queue, key=lambda t: -t[0]):
            self.emit(
                "FileForAnalysis",
                {
                    "path": str(path),
                    "score": priority_score(path),
                },
            )
        self.emit("TriageComplete", {})

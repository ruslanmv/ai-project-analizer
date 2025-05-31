"""
extraction_agent.py
~~~~~~~~~~~~~~~~~~~

Extracts the validated ZIP into a temporary directory using *safe_extract*,
defending against Zip-Slip and oversized members.  Emits a *FileDiscovered*
event for every file found and finally *ExtractionDone*.

Incoming events
---------------
• ZipValid           { zip_path: str }

Outgoing events
---------------
• FileDiscovered     { path: str }
• ExtractionFailed   { reason: str }
• ExtractionDone     { base_dir: str }
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List

# Updated imports to use beeai_framework instead of beeai
from beeai_framework.agent import Agent
from beeai_framework.typing import Event

from ..config import settings

# --------------------------------------------------------------------------- #
#  Minimal fallback implementations.  In the full repo they live in
#  src.tools.file_io_tool but are repeated here to keep the file standalone.
# --------------------------------------------------------------------------- #
import zipfile


def safe_extract(zip_path: Path) -> Path:
    """Extract *zip_path* into a fresh tmp dir with Zip-Slip defence."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="ai_analyser_")).resolve()

    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            # Member size guard
            if (
                member.file_size
                > settings.MAX_MEMBER_SIZE_MB * 1_048_576  # type: ignore[attr-defined]
            ):
                raise ValueError(
                    f"Member {member.filename} exceeds "
                    f"{settings.MAX_MEMBER_SIZE_MB} MB"
                )

            # Zip-Slip guard
            target = (tmp_dir / member.filename).resolve()
            if not str(target).startswith(str(tmp_dir)):
                raise ValueError(f"Illegal member path: {member.filename}")

        zf.extractall(tmp_dir)

    return tmp_dir


class ExtractionAgent(Agent):
    name = "extraction"

    def __init__(self) -> None:  # noqa: D401
        super().__init__()
        self._tmp_dir: Path | None = None

    def handle(self, event: Event) -> None:  # noqa: D401
        if event["type"] != "ZipValid":
            return

        zip_path = Path(event["zip_path"])
        try:
            self._tmp_dir = safe_extract(zip_path)
        except Exception as exc:
            self.emit("ExtractionFailed", {"reason": str(exc)})
            return

        # Walk the directory tree and emit one event per file
        for root, _, files in os.walk(self._tmp_dir):
            for fname in files:
                full = Path(root) / fname
                self.emit("FileDiscovered", {"path": str(full)})

        # Signal downstream agents that no more files are coming
        self.emit("ExtractionDone", {"base_dir": str(self._tmp_dir)})

    # Optional: tidy up temp dir when workflow stops
    def on_shutdown(self) -> None:  # noqa: D401
        if self._tmp_dir and settings.DELETE_TEMP_AFTER_RUN:
            shutil.rmtree(self._tmp_dir, ignore_errors=True)

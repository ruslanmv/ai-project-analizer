# src/agents/extraction_agent.py

"""
extraction_agent.py
~~~~~~~~~~~~~~~~~~~

Extracts the validated ZIP into a temporary directory using *safe_extract*,
defending against Zip‐Slip and oversized members.  Emits a *FileDiscovered*
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
import logging
import zipfile
from pathlib import Path
from typing import Dict, Any, List

from ..config import settings

# --------------------------------------------------------------------------- #
# Configure logger for this agent
# --------------------------------------------------------------------------- #
LOG = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Minimal Agent base‐class (no beeai_framework dependency)
# --------------------------------------------------------------------------- #
class Agent:
    """
    A minimal stand‐in for the BeeAI Agent base‐class.
    Subclasses should call self.emit(...) when they want to emit an event.
    """
    def __init__(self) -> None:
        # by default, emit does nothing. In your tests you can monkey‐patch it.
        pass

    def emit(self, event_name: str, payload: Dict[str, Any]) -> None:
        """
        Stub method. Subclasses call this to “emit” events.
        In tests, you can override `emit = lambda name,payload: ...`.
        """
        return


def safe_extract(zip_path: Path) -> Path:
    """
    Extract *zip_path* into a fresh tmp dir with Zip‐Slip defence.
    Returns the Path to the extracted directory.
    Raises on BadZipFile or if any member is too large or uses a malicious path.
    """
    LOG.info("[extraction] safe_extract() called with %r", zip_path)
    tmp_dir = Path(tempfile.mkdtemp(prefix="ai_analyser_")).resolve()
    LOG.info("[extraction] Created temporary directory %r", tmp_dir)

    with zipfile.ZipFile(zip_path, "r") as zf:
        # 1) Quick CRC check on entire archive
        bad_member = zf.testzip()
        if bad_member:
            msg = f"CRC check failed on {bad_member}"
            LOG.error("[extraction] %s", msg)
            raise zipfile.BadZipFile(msg)

        # 2) Iterate through all members to enforce Zip‐Slip and size checks
        for member in zf.infolist():
            LOG.debug("[extraction] Inspecting member %r (size=%d bytes)",
                      member.filename, member.file_size)

            # 2a) Check uncompressed size limit per member
            max_bytes = settings.MAX_MEMBER_SIZE_MB * 1_048_576
            if member.file_size > max_bytes:  # type: ignore[attr-defined]
                msg = (
                    f"Refusing to extract '{member.filename}': "
                    f"size {member.file_size} bytes > {settings.MAX_MEMBER_SIZE_MB} MB"
                )
                LOG.error("[extraction] %s", msg)
                raise ValueError(msg)

            # 2b) Construct target path and enforce Zip‐Slip defence
            target = (tmp_dir / member.filename).resolve()
            if not str(target).startswith(str(tmp_dir)):
                msg = f"Illegal file path detected: {member.filename!r}"
                LOG.error("[extraction] %s", msg)
                raise ValueError(msg)

        LOG.info("[extraction] All members passed size and Zip‐Slip checks, extracting now...")
        zf.extractall(tmp_dir)
        LOG.info("[extraction] Extraction completed into %r", tmp_dir)

    return tmp_dir


class ExtractionAgent(Agent):
    name = "extraction"

    def __init__(self) -> None:
        super().__init__()
        self._tmp_dir: Path | None = None

    def handle(self, event: Dict[str, Any]) -> None:
        """
        event is expected to be a dict with at least {"type": "ZipValid", "zip_path": "..."}.
        If event["type"] != "ZipValid", do nothing.
        Otherwise, attempt to extract, emitting FileDiscovered and ExtractionDone (or ExtractionFailed).
        """
        LOG.info(">>> [extraction] handle() entered. event=%r", event)

        # Only process ZipValid events
        if event.get("type") != "ZipValid":
            LOG.debug("[extraction] Ignoring event type %r", event.get("type"))
            return

        zip_path = Path(event["zip_path"])
        LOG.info("[extraction] Received ZipValid for %r", zip_path)

        try:
            LOG.debug("[extraction] Calling safe_extract for %r", zip_path)
            self._tmp_dir = safe_extract(zip_path)
            LOG.info("[extraction] safe_extract returned %r", self._tmp_dir)
        except Exception as exc:
            LOG.exception("[extraction] Extraction failed: %s", exc)
            self.emit("ExtractionFailed", {"reason": str(exc)})
            LOG.info("[extraction] Emitted ExtractionFailed (reason=%r)", str(exc))
            return

        # Once extraction is successful, list all files and emit one FileDiscovered per file
        discovered_files: List[Path] = []
        LOG.info("[extraction] Walking directory %r to discover files", self._tmp_dir)
        for root, _, files in os.walk(self._tmp_dir):
            for fname in files:
                full_path = Path(root) / fname
                discovered_files.append(full_path)
                LOG.debug("[extraction] Discovered file %r", full_path)
                self.emit("FileDiscovered", {"path": str(full_path)})
                LOG.info("[extraction] Emitted FileDiscovered for %r", full_path)

        # Print (once) the entire list of discovered files for clarity
        if discovered_files:
            LOG.info("[extraction] Full list of discovered files (total=%d):", len(discovered_files))
            for f in discovered_files:
                LOG.info("   - %r", f)
        else:
            LOG.warning("[extraction] No files were found under %r", self._tmp_dir)

        # Signal downstream agents that no more files are coming
        LOG.info("[extraction] All files discovered. Emitting ExtractionDone with base_dir=%r", self._tmp_dir)
        self.emit("ExtractionDone", {"base_dir": str(self._tmp_dir)})
        LOG.info("[extraction] Emitted ExtractionDone. handle() exiting normally.")

    def on_shutdown(self) -> None:
        """
        Optional cleanup. If settings.DELETE_TEMP_AFTER_RUN is True,
        delete the temporary directory when the workflow stops.
        """
        LOG.info("[extraction] on_shutdown() called.")
        if self._tmp_dir and settings.DELETE_TEMP_AFTER_RUN:
            LOG.info("[extraction] Deleting temp dir %r", self._tmp_dir)
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
            LOG.info("[extraction] Deleted temp dir %r", self._tmp_dir)

# src/agents/zip_validator_agent.py

"""
zip_validator_agent.py
~~~~~~~~~~~~~~~~~~~~~~

Stage‐0 guard: make sure the uploaded archive is truly a ZIP, not corrupted,
and below size limits.  Emits *ZipValid* or *ZipInvalid* so the rest of the
pipeline can continue or abort early.

Incoming events
---------------
• NewUpload          { zip_path: str }

Outgoing events
---------------
• ZipValid           { zip_path: str }
• ZipInvalid         { zip_path: str, reason: str }
"""

from __future__ import annotations

import zipfile
import logging
from pathlib import Path
from typing import Dict, Any

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


class ZipValidatorAgent(Agent):
    name = "zip_validator"

    def handle(self, event: Dict[str, Any]) -> None:  # noqa: D401
        """
        event is expected to be a dict with at least {"type": str, ...}
        If event["type"] != "NewUpload", we ignore it.
        Otherwise, we check that event["zip_path"] points to a real, non‐corrupt ZIP
        under size limits, and then emit either "ZipValid" or "ZipInvalid".
        """
        LOG.info(">>> [zip_validator] handle() entered. event=%r", event)

        # Only process NewUpload events
        if event.get("type") != "NewUpload":
            LOG.debug("[zip_validator] Ignoring event type %r", event.get("type"))
            return

        zip_path = Path(event["zip_path"])
        LOG.info("[zip_validator] Received NewUpload for %r", zip_path)

        # Check existence
        if not zip_path.exists():
            reason = "File does not exist"
            LOG.warning("[zip_validator] %s: %s", reason, zip_path)
            self.emit(
                "ZipInvalid",
                {"zip_path": str(zip_path), "reason": reason},
            )
            LOG.info("[zip_validator] Emitted ZipInvalid (file missing)")
            return

        # Hard limit on compressed size
        max_bytes = settings.ZIP_SIZE_LIMIT_MB * 1_048_576
        actual_size = zip_path.stat().st_size
        LOG.debug(
            "[zip_validator] Checking size: %d bytes (max %d bytes)",
            actual_size,
            max_bytes,
        )
        if actual_size > max_bytes:
            reason = f"Archive exceeds {settings.ZIP_SIZE_LIMIT_MB} MB"
            LOG.warning(
                "[zip_validator] %s: %0.2f MB", reason, actual_size / 1_048_576
            )
            self.emit(
                "ZipInvalid",
                {"zip_path": str(zip_path), "reason": reason},
            )
            LOG.info("[zip_validator] Emitted ZipInvalid (size limit)")
            return

        # Sanity check: real ZIP?
        LOG.debug("[zip_validator] Checking if %r is a zipfile", zip_path)
        if not zipfile.is_zipfile(zip_path):
            reason = "Not a ZIP archive"
            LOG.warning("[zip_validator] %s: %r", reason, zip_path)
            self.emit(
                "ZipInvalid",
                {"zip_path": str(zip_path), "reason": reason},
            )
            LOG.info("[zip_validator] Emitted ZipInvalid (not a zipfile)")
            return

        # CRC check on every member
        LOG.debug("[zip_validator] Performing CRC check on %r", zip_path)
        try:
            with zipfile.ZipFile(zip_path) as zf:
                corrupt = zf.testzip()
        except zipfile.BadZipFile as e:
            reason = f"ZIP read error: {e}"
            LOG.error("[zip_validator] %s", reason)
            self.emit(
                "ZipInvalid",
                {"zip_path": str(zip_path), "reason": reason},
            )
            LOG.info("[zip_validator] Emitted ZipInvalid (bad zip)")
            return

        if corrupt is not None:
            reason = f"CRC error in member: {corrupt}"
            LOG.error("[zip_validator] %s: %s", reason, corrupt)
            self.emit(
                "ZipInvalid",
                {"zip_path": str(zip_path), "reason": reason},
            )
            LOG.info("[zip_validator] Emitted ZipInvalid (CRC error)")
            return

        # ✅ All good
        LOG.info("[zip_validator] ZIP archive %r passed all checks", zip_path)
        self.emit("ZipValid", {"zip_path": str(zip_path)})
        LOG.info("[zip_validator] Emitted ZipValid for %r", zip_path)
        LOG.info("[zip_validator] handle() exiting normally.")

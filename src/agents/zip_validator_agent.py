"""
zip_validator_agent.py
~~~~~~~~~~~~~~~~~~~~~~

Stage-0 guard: make sure the uploaded archive is truly a ZIP, not corrupted,
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

# Updated imports to use beeai_framework instead of beeai
from beeai_framework.agent import Agent
from beeai_framework.typing import Event

from ..config import settings

# --------------------------------------------------------------------------- #
# Configure logger for this agent
# --------------------------------------------------------------------------- #
LOG = logging.getLogger(__name__)


class ZipValidatorAgent(Agent):
    name = "zip_validator"

    def handle(self, event: Event) -> None:  # noqa: D401
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
                {
                    "zip_path": str(zip_path),
                    "reason": reason,
                },
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
                {
                    "zip_path": str(zip_path),
                    "reason": reason,
                },
            )
            LOG.info("[zip_validator] Emitted ZipInvalid (CRC error)")
            return

        # ✅ All good
        LOG.info("[zip_validator] ZIP archive %r passed all checks", zip_path)
        self.emit("ZipValid", {"zip_path": str(zip_path)})
        LOG.info("[zip_validator] Emitted ZipValid for %r", zip_path)
        LOG.info("[zip_validator] handle() exiting normally.")

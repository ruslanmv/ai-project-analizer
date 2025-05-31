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
from pathlib import Path
from typing import Any, Dict

import beeai
from beeai.typing import Event

from ..config import settings


class ZipValidatorAgent(beeai.Agent):
    name = "zip_validator"

    def handle(self, event: Event) -> None:  # noqa: D401
        if event["type"] != "NewUpload":
            return  # Ignore anything else

        zip_path = Path(event["zip_path"])
        if not zip_path.exists():
            self.emit(
                "ZipInvalid",
                {"zip_path": str(zip_path), "reason": "File does not exist"},
            )
            return

        # Hard limit on compressed size
        max_bytes = settings.ZIP_SIZE_LIMIT_MB * 1_048_576
        if zip_path.stat().st_size > max_bytes:
            self.emit(
                "ZipInvalid",
                {
                    "zip_path": str(zip_path),
                    "reason": f"Archive exceeds {settings.ZIP_SIZE_LIMIT_MB} MB",
                },
            )
            return

        # Sanity check: real ZIP?
        if not zipfile.is_zipfile(zip_path):
            self.emit(
                "ZipInvalid",
                {"zip_path": str(zip_path), "reason": "Not a ZIP archive"},
            )
            return

        # CRC check on every member
        with zipfile.ZipFile(zip_path) as zf:
            corrupt = zf.testzip()
            if corrupt is not None:
                self.emit(
                    "ZipInvalid",
                    {
                        "zip_path": str(zip_path),
                        "reason": f"CRC error in member: {corrupt}",
                    },
                )
                return

        # ✅ All good
        self.emit("ZipValid", {"zip_path": str(zip_path)})

"""
file_io_tool.py

Reusable filesystem‐and‐archive helpers for:
  - ZIP validation and safe extraction
  - Zip‐Slip defence
  - Oversized‐member rejection
  - Binary/text sniff
  - Priority scoring by filename/extension

Imported by:
  • zip_validator_agent.py
  • extraction_agent.py
  • file_triage_agent.py

Dependencies:
  • Python ≥ 3.9 standard library
  • src.config.settings for configurable limits
"""

from __future__ import annotations

import os
import tempfile
import zipfile
from pathlib import Path
from typing import List

from ..config import settings

# --------------------------------------------------------------------------- #
#  safe_extract()
# --------------------------------------------------------------------------- #
def safe_extract(zip_path: Path) -> Path:
    """
    Extracts a ZIP archive to a new temporary directory, enforcing:
      1. Zip‐Slip defence: no member can escape the tmp_dir via '../'
      2. Per‐member uncompressed size limit (MAX_MEMBER_SIZE_MB)
      3. Rejects corrupt or malicious archives early

    Returns
    -------
    Path
        Directory where files were extracted.

    Raises
    ------
    ValueError
        If any member is too large or attempts Zip‐Slip.
    zipfile.BadZipFile
        If the archive is corrupted or invalid.
    """
    if not zipfile.is_zipfile(zip_path):
        raise zipfile.BadZipFile(f"{zip_path!s} is not a valid ZIP archive")

    tmp_dir = Path(tempfile.mkdtemp(prefix="ai_analyser_")).resolve()

    with zipfile.ZipFile(zip_path, "r") as zf:
        bad_member = zf.testzip()
        if bad_member:
            raise zipfile.BadZipFile(f"CRC check failed on {bad_member}")

        # Iterate through all members to enforce Zip‐Slip and size checks
        for member in zf.infolist():
            # 1) Check uncompressed size limit per member
            max_bytes = settings.MAX_MEMBER_SIZE_MB * 1_048_576  # MB → bytes
            if member.file_size > max_bytes:  # type: ignore[attr-defined]
                raise ValueError(
                    f"Refusing to extract '{member.filename}': "
                    f"size {member.file_size} bytes > {settings.MAX_MEMBER_SIZE_MB} MB"
                )

            # 2) Construct target path and enforce Zip‐Slip defence
            target = (tmp_dir / member.filename).resolve()
            if not str(target).startswith(str(tmp_dir)):
                raise ValueError(f"Illegal file path detected: {member.filename!r}")

        # All checks passed, do the actual extraction
        zf.extractall(tmp_dir)

    return tmp_dir


# --------------------------------------------------------------------------- #
#  looks_binary()
# --------------------------------------------------------------------------- #
def looks_binary(path: Path, sample: int = 1024) -> bool:
    """
    Heuristic to decide if a file is binary (non‐text). Reads up to `sample`
    bytes and computes the fraction of non‐printable bytes. If > 30%, call it binary.

    Returns
    -------
    bool
        True if file is likely binary (skip content), False if likely text.
    """
    try:
        with path.open("rb") as fh:
            chunk = fh.read(sample)
            if not chunk:
                return False  # empty file → treat as text

            non_printable = sum(b < 9 or 13 < b < 32 for b in chunk)
            ratio = non_printable / len(chunk)
            return ratio > 0.30
    except (OSError, IOError):
        # On any read error, treat conservatively as binary so we skip it
        return True


# --------------------------------------------------------------------------- #
#  priority_score()
# --------------------------------------------------------------------------- #
def priority_score(path: Path) -> int:
    """
    Assign an integer “priority” based on filename stem or extension.
    Higher → more urgent analysis.

    Rules (example weights):
      • High‐signal filenames (README, LICENSE, setup, etc.) → 100
      • Source or config code (.py, .js, .json, .yaml, .sh) → 80
      • Documentation (.md, .rst, .txt) → 70
      • All others (including assets) → 10

    Returns
    -------
    int
        Numerical score: higher means analyse earlier.
    """
    stem = path.stem.lower()
    ext = path.suffix.lower()

    if stem in {
        "readme",
        "license",
        "setup",
        "pyproject",
        "package",
        "requirements",
        "dockerfile",
        "compose",
        "makefile",
        "main",
        "app",
    }:
        return 100

    if ext in {".py", ".js", ".json", ".yml", ".yaml", ".toml", ".sh"}:
        return 80

    if ext in {".md", ".rst", ".txt"}:
        return 70

    # Everything else (images, binaries, etc.)
    return 10

"""
encoding_helper.py

Detects and handles text‐file encodings robustly:
  • Attempts UTF‐8
  • Falls back to a chardet‐based guess, then latin‐1
  • Always returns a Python str (with replacement characters if needed)

Imported by:
  • file_analysis_agent.py

Dependencies:
  • chardet (optional; for improved encoding detection)
"""

from __future__ import annotations

from pathlib import Path

try:
    import chardet
    CHARDET_AVAILABLE = True
except ImportError:
    chardet = None  # type: ignore
    CHARDET_AVAILABLE = False


def read_text_safe(path: Path, max_bytes: int = 64_000) -> str:
    """
    Read a text file into a string safely, handling unknown or mixed encodings.

    Strategy:
      1. Read up to `max_bytes` bytes from the file.
      2. Try decoding as UTF‐8.
      3. If that fails, and chardet is available, feed the sample to chardet to guess.
      4. Decode using the guessed encoding (or latin‐1 as fallback), with errors='replace'.

    Parameters
    ----------
    path : Path
      Path to the text file.
    max_bytes : int
      How many bytes to sample for encoding detection (default: 64 KB).

    Returns
    -------
    str
      The entire file’s text content decoded to Python str (may contain replacement chars).
    """
    raw_bytes = b""
    try:
        with path.open("rb") as fh:
            raw_bytes = fh.read(max_bytes)
    except (OSError, IOError):
        # If the file cannot be read at all, return empty string
        return ""

    # Try UTF-8 first
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        pass

    # If chardet is available, use it to guess
    if CHARDET_AVAILABLE:
        guess = chardet.detect(raw_bytes)
        encoding = guess.get("encoding", "utf-8")
    else:
        encoding = "latin-1"

    # Decode entire file, not just sample, using guessed encoding
    try:
        return path.read_text(encoding=encoding, errors="replace")
    except (OSError, IOError):
        # As a last resort, decode sample with latin-1
        return raw_bytes.decode("latin-1", errors="replace")

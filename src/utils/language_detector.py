"""
language_detector.py

Heuristics for:
  • Counting file extensions to detect the dominant language or tech stack.
  • Inferring project type (Python package vs. Node.js app vs. Dockerized service).
  • Generating a unified project summary from per‐file analyses + directory tree.

Imported by:
  • summary_synthesizer_agent.py

Dependencies:
  • Python ≥ 3.9 standard library
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# --------------------------------------------------------------------------- #
#  guess_stack()
# --------------------------------------------------------------------------- #
def guess_stack(file_summaries: List[Dict[str, Any]]) -> str:
    """
    Given a list of per-file summaries (each entry has 'rel_path', 'kind', etc.),
    infer a high-level “project type”:
      • If 'pyproject.toml' or 'setup.py' present → Python package
      • If 'package.json' present → Node.js project
      • If 'Dockerfile' present → Containerized service
      • If 'go.mod' present → Go module
      • If 'pom.xml' present → Java Maven project
      • Fallback: “Mixed” or “Unknown”

    Returns
    -------
    str
      Short description of the likely tech stack.
    """
    paths = [entry.get("rel_path", "").lower() for entry in file_summaries]
    if any(p.endswith("setup.py") or p.endswith("pyproject.toml") for p in paths):
        return "Python package"
    if any(p.endswith("package.json") for p in paths):
        return "Node.js project"
    if any(p.endswith("dockerfile") for p in paths):
        return "Containerized service"
    if any(p.endswith("go.mod") for p in paths):
        return "Go module"
    if any(p.endswith("pom.xml") for p in paths):
        return "Java Maven project"
    return "Unknown or mixed‐language project"


# --------------------------------------------------------------------------- #
#  detect_dominant_language()
# --------------------------------------------------------------------------- #
def detect_dominant_language(file_summaries: List[Dict[str, Any]]) -> Tuple[str, int]:
    """
    From the list of per-file analyses (each with a 'kind' key), count occurrences
    of each kind to find the dominant file type (e.g., 'python', 'json', 'text').

    Returns
    -------
    (language: str, count: int)
      The most common 'kind' value and its count. If no entries, returns ('unknown', 0).
    """
    counter = Counter(entry.get("kind", "unknown") for entry in file_summaries)
    if not counter:
        return ("unknown", 0)
    common, count = counter.most_common(1)[0]
    return (common, count)


# --------------------------------------------------------------------------- #
#  find_readme_first_line()
# --------------------------------------------------------------------------- #
def find_readme_first_line(file_summaries: List[Dict[str, Any]]) -> Optional[str]:
    """
    Locate the first README‐style entry (kind='text' with rel_path ~ 'README*').
    Return its summary (one‐liner) if available, else None.
    """
    for entry in file_summaries:
        rel = entry.get("rel_path", "").lower()
        if rel.startswith("readme") and entry.get("kind", "").startswith("text"):
            return entry.get("summary", "").rstrip(".") + "."
    return None


# --------------------------------------------------------------------------- #
#  synthesise_project()
# --------------------------------------------------------------------------- #
def synthesise_project(
    file_summaries: List[Dict[str, Any]],
    tree_text: str,
    max_summary_length: int = 300,
) -> str:
    """
    Combine:
      1) The first README line (if any)
      2) Dominant language from file_summaries
      3) Inferred tech stack from guess_stack()
      4) Any presence of Dockerfile or packaging files (from paths)
    into a coherent paragraph (≤ max_summary_length chars).

    For example:
      “MyProject is a Python package. The dominant file type is python. A
       Dockerfile suggests containerized deployment.”

    Returns
    -------
    str
      The composed project summary.
    """
    # 1) Extract README clue
    readme_snippet = find_readme_first_line(file_summaries)

    # 2) Dominant language
    dom_lang, dom_count = detect_dominant_language(file_summaries)

    # 3) Tech stack
    stack = guess_stack(file_summaries)

    # 4) Check for Dockerfile and packaging hints
    has_docker = any(entry["rel_path"].lower().endswith("dockerfile") for entry in file_summaries)
    has_setup = any(
        entry["rel_path"].lower().endswith(("setup.py", "pyproject.toml"))
        for entry in file_summaries
    )
    has_pkgjson = any(entry["rel_path"].lower().endswith("package.json") for entry in file_summaries)

    parts: list[str] = []
    if readme_snippet:
        parts.append(readme_snippet)
    parts.append(f"The dominant file type is *{dom_lang}* (count: {dom_count}).")
    if stack:
        parts.append(f"Inferred tech stack: {stack}.")
    if has_docker:
        parts.append("Presence of a Dockerfile suggests containerized deployment.")
    if has_setup:
        parts.append("Packaging metadata indicates a Python package.")
    if has_pkgjson:
        parts.append("Including 'package.json' reveals a Node.js component.")
    # If nothing else, at least include some generic fallback
    if len(parts) == 0:
        parts.append("No README or identifiable files found; unclear project purpose.")

    summary = " ".join(parts)
    # Truncate if too long
    if len(summary) > max_summary_length:
        summary = summary[: max_summary_length - 1].rstrip() + "…"
    return summary

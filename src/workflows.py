"""
Single place where we assemble the BeeAI agents into a runnable Workflow.

Two entry points are exposed:

    • `create_runtime()` -> beeai.Runtime
         - Returns a *configured but not yet started* runtime; handy for tests.

    • `run_workflow(zip_path: Path, model: str, print_events: bool)`
         - Fire-and-forget helper used by CLI & FastAPI layer.  Spins the
           runtime, waits for the blocking `.run()`, then collects artefacts
           that agent(s) have persisted in shared memory or workspace files.

This module is ‘code twin’ to the declarative `beeai.yaml`; keeping both
lets you spin the pipeline purely from Python (no YAML parsing needed in
tests) while still allowing `beeai run beeai.yaml ...` in prod.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

try:
    import beeai
    from beeai.runtime import Runtime
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "The 'beeai' package is required.  Install with   pip install beeai"
    ) from exc

from .config import settings

# --------------------------------------------------------------------------- #
#  Agent *file paths* (relative to repo root).  This makes it possible to run
#  the workflow even when the package is installed site-wide (as .pyz or
#  wheel).  It assumes the repo layout described in README.md.
# --------------------------------------------------------------------------- #
AGENT_PY = Path(__file__).parent / "agents"
AGENTS = {
    "zip_validator": AGENT_PY / "zip_validator_agent.py",
    "extractor": AGENT_PY / "extraction_agent.py",
    "tree_builder": AGENT_PY / "tree_builder_agent.py",
    "file_triage": AGENT_PY / "file_triage_agent.py",
    "file_analysis": AGENT_PY / "file_analysis_agent.py",
    "summary_synthesizer": AGENT_PY / "summary_synthesizer_agent.py",
    # optional
    "cleanup": AGENT_PY / "cleanup_agent.py",
}


def create_runtime(model: str | None = None) -> "Runtime":
    """
    Build a BeeAI Runtime with all agents wired together.

    The topology matches `beeai.yaml`:

        zip_validator  -> extractor
                                   \
                                     -> tree_builder
                                      \
         file_triage -> file_analysis   \
                                         -> summary_synthesizer -> cleanup

    Parameters
    ----------
    model : str | None
        Foundation-model ID used by LLM-enabled agents.  If `None`, fallback
        to settings from `src.config`.
    """
    model_id = model or settings.BEEAI_MODEL

    runtime = beeai.Runtime(log_level=settings.LOG_LEVEL)

    # -- Instantiate agents --------------------------------------------------
    zip_validator = runtime.add_agent("zip_validator", AGENTS["zip_validator"])
    extractor = runtime.add_agent("extractor", AGENTS["extractor"])
    tree_builder = runtime.add_agent("tree_builder", AGENTS["tree_builder"])
    file_triage = runtime.add_agent("file_triage", AGENTS["file_triage"])
    file_analysis = runtime.add_agent("file_analysis", AGENTS["file_analysis"])
    summarizer = runtime.add_agent(
        "summary_synthesizer",
        AGENTS["summary_synthesizer"],
        parameters={"model": model_id},
    )
    cleanup = runtime.add_agent("cleanup", AGENTS["cleanup"])

    # -- Wiring (publish/subscribe) -----------------------------------------
    runtime.link(zip_validator, extractor)
    runtime.link(extractor, tree_builder)        # FileDiscovered -> TreeBuilder
    runtime.link(extractor, file_triage)         # FileDiscovered -> FileTriage
    runtime.link(file_triage, file_analysis)     # FileForAnalysis -> Analysis
    runtime.link(tree_builder, summarizer)       # TreeBuilt -> Synth
    runtime.link(file_analysis, summarizer)      # FileAnalysed -> Synth
    runtime.link(summarizer, cleanup)            # SummaryPolished -> Cleanup

    return runtime


# --------------------------------------------------------------------------- #
#  High-level blocking helper
# --------------------------------------------------------------------------- #
def run_workflow(
    zip_path: Path,
    *,
    model: str | None = None,
    print_events: bool = True,
) -> Dict[str, Any]:
    """
    Single call that:
      1. Builds the BeeAI runtime
      2. Injects a ‘NewUpload’ event with initial payload
      3. Blocks until the agents emit `CleanupDone`
      4. Returns artefacts gathered from runtime's memory store

    Returns dict with keys:
        tree_text         -> str
        file_summaries    -> List[dict]
        project_summary   -> str
    """
    if zip_path.stat().st_size > settings.ZIP_SIZE_LIMIT_MB * 1_048_576:
        raise ValueError(
            f"Archive is larger than {settings.ZIP_SIZE_LIMIT_MB} MB "
            f"({zip_path.stat().st_size/1_048_576:.1f} MB)"
        )

    runtime = create_runtime(model)

    # 1️⃣  Fire initial event so ZipValidatorAgent can start
    runtime.emit("NewUpload", {"zip_path": str(zip_path)})

    # Optional: attach console logger for pretty live output
    if print_events:
        logging.basicConfig(
            level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
            format="%(asctime)s  %(name)s  %(message)s",
            datefmt="%H:%M:%S",
        )
        runtime.subscribe("*", lambda e: logging.info("★ %s", e["type"]))

    # 2️⃣  Run until blocking terminates (agents decide when to stop)
    runtime.run()

    # 3️⃣  Collect artefacts stored by agents
    mem = runtime.memory  # BeeAI key-value store (SQLite or shared dict)

    tree_text: str = mem.get("project_tree.txt", "")
    summaries_json: str = mem.get("file_summaries.json", "[]")
    file_summaries: List[dict[str, Any]] = json.loads(summaries_json)
    project_summary: str = mem.get("project_summary.txt", "")

    return {
        "tree_text": tree_text,
        "file_summaries": file_summaries,
        "project_summary": project_summary,
    }

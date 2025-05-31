"""
src/workflows.py
================

Assembles all BeeAI agents into a runnable Workflow, using beeai_framework.

Public helpers
--------------
create_workflow_engine(model=None) -> Workflow
run_workflow(zip_path, model=None, print_events=True) -> artefacts dict
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

# --------------------------------------------------------------------------- #
#  Import the workflow engine from beeai_framework
# --------------------------------------------------------------------------- #
try:
    from beeai_framework.workflows.workflow import Workflow
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "Cannot import Workflow from beeai_framework. "
        "Make sure `beeai-framework` is installed."
    ) from exc

from .config import settings

LOG = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
#  Agent file paths (relative to src/)
# --------------------------------------------------------------------------- #
AGENT_DIR = Path(__file__).parent / "agents"
AGENTS = {
    "zip_validator":         AGENT_DIR / "zip_validator_agent.py",
    "extractor":             AGENT_DIR / "extraction_agent.py",
    "tree_builder":          AGENT_DIR / "tree_builder_agent.py",
    "file_triage":           AGENT_DIR / "file_triage_agent.py",
    "file_analysis":         AGENT_DIR / "file_analysis_agent.py",
    "summary_synthesizer":   AGENT_DIR / "summary_synthesizer_agent.py",
    "cleanup":               AGENT_DIR / "cleanup_agent.py",   # optional
}


# --------------------------------------------------------------------------- #
#  Runtime / Workflow builder
# --------------------------------------------------------------------------- #
def create_workflow_engine(model: str | None = None) -> Workflow:
    """
    Build a beeai-framework Workflow with all agents wired together.

    Parameters
    ----------
    model : str | None
        Foundation-model identifier; falls back to settings.BEEAI_MODEL.
    """
    model_id = model or settings.BEEAI_MODEL
    wf = Workflow(log_level=settings.LOG_LEVEL)

    # ---- instantiate agents -------------------------------------------------
    zip_validator  = wf.add_agent("zip_validator",  AGENTS["zip_validator"])
    extractor      = wf.add_agent("extractor",      AGENTS["extractor"])
    tree_builder   = wf.add_agent("tree_builder",   AGENTS["tree_builder"])
    file_triage    = wf.add_agent("file_triage",    AGENTS["file_triage"])
    file_analysis  = wf.add_agent("file_analysis",  AGENTS["file_analysis"])
    summarizer     = wf.add_agent(
        "summary_synthesizer",
        AGENTS["summary_synthesizer"],
        parameters={"model": model_id},
    )

    cleanup = None
    if AGENTS["cleanup"].exists():
        cleanup = wf.add_agent("cleanup", AGENTS["cleanup"])
        LOG.info("Cleanup agent enabled")
    else:
        LOG.info("Cleanup agent not present (or disabled)")

    # ---- wire publish / subscribe ------------------------------------------
    wf.link(zip_validator, extractor)
    wf.link(extractor, tree_builder)
    wf.link(extractor, file_triage)
    wf.link(file_triage, file_analysis)
    wf.link(tree_builder, summarizer)
    wf.link(file_analysis, summarizer)
    if cleanup:
        wf.link(summarizer, cleanup)

    return wf


# Backward-compat alias for code that still calls create_runtime()
create_runtime = create_workflow_engine


# --------------------------------------------------------------------------- #
#  High-level helper
# --------------------------------------------------------------------------- #
def run_workflow(
    zip_path: Path,
    *,
    model: str | None = None,
    print_events: bool = True,
) -> Dict[str, Any]:
    """
    Run the multi-agent workflow and return its artefacts.
    """
    max_bytes = settings.ZIP_SIZE_LIMIT_MB * 1_048_576
    if zip_path.stat().st_size > max_bytes:
        raise ValueError(
            f"Archive exceeds {settings.ZIP_SIZE_LIMIT_MB} MB "
            f"({zip_path.stat().st_size/1_048_576:.1f} MB)"
        )

    wf = create_workflow_engine(model)
    wf.emit("NewUpload", {"zip_path": str(zip_path)})

    # Live event logging
    if print_events:
        logging.basicConfig(
            level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
            format="%(asctime)s | %(name)s | ★ %(message)s",
            datefmt="%H:%M:%S",
        )
        wf.subscribe("*", lambda e: LOG.info("%s", e["type"]))

    wf.run()  # (blocking) – call `await wf.run()` if your API is async

    mem = wf.memory
    tree_text        = mem.get("project_tree.txt", "")
    summaries_json   = mem.get("file_summaries.json", "[]")
    project_summary  = mem.get("project_summary.txt", "")

    try:
        file_summaries: List[Dict[str, Any]] = json.loads(summaries_json)
    except json.JSONDecodeError:  # pragma: no cover
        file_summaries = []

    return {
        "tree_text": tree_text,
        "file_summaries": file_summaries,
        "project_summary": project_summary,
    }

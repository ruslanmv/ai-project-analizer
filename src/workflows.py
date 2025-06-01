# src/workflows.py

"""
Assembles all agents into a runnable pipeline without beeai_framework.
Each agent is called in turn, and events are passed manually.

Stages:
  1. ZipValidatorAgent   – validates the ZIP, emits ZipValid or ZipInvalid
  2. ExtractionAgent     – on ZipValid, extracts archive, emits FileDiscovered and ExtractionDone
  3. TreeBuilderAgent    – on each FileDiscovered, accumulates paths; on ExtractionDone, builds project_tree.txt, emits TreeBuilt
  4. FileTriageAgent     – on each FileDiscovered, decides skip or queue; on ExtractionDone, emits FileForAnalysis and TriageComplete
  5. FileAnalysisAgent   – on FileForAnalysis, analyses each file; on TriageComplete, writes file_summaries.json and emits AnalysisComplete
  6. SummarySynthesizerAgent – waits for TreeBuilt + AnalysisComplete, synthesises summary, emits ProjectDraft and SummaryPolished

Outputs:
  • tree_text        – contents of project_tree.txt
  • file_summaries   – parsed JSON array from file_summaries.json
  • project_summary  – contents of project_summary.txt
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from src.config import settings
from src.agents.zip_validator_agent import ZipValidatorAgent
from src.agents.extraction_agent import ExtractionAgent
from src.agents.tree_builder_agent import TreeBuilderAgent
from src.agents.file_triage_agent import FileTriageAgent
from src.agents.file_analysis_agent import FileAnalysisAgent
from src.agents.summary_synthesizer_agent import SummarySynthesizerAgent

# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
LOG = logging.getLogger(__name__)
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format=(
        "%(asctime)s | %(levelname)s | %(name)s | "
        "%(module)s.%(funcName)s:%(lineno)d | ★ %(message)s"
    ),
    datefmt="%H:%M:%S",
    force=True,
)


def run_workflow(zip_path: Path) -> Dict[str, Any]:
    """
    Run the full pipeline on *zip_path* and return:
      • tree_text        – the directory tree as a string
      • file_summaries   – list[dict] of per-file summaries
      • project_summary  – final overall summary
    """
    LOG.info(">>> Starting run_workflow for ZIP: %s", zip_path)

    # -----------------------------
    # 1) ZIP validation
    # -----------------------------
    zip_validator = ZipValidatorAgent()
    zip_validator.emit = lambda name, payload: emitted_zip.append((name, payload))
    emitted_zip: List[Any] = []

    # Fire NewUpload event
    zip_validator.handle({"type": "NewUpload", "zip_path": str(zip_path)})

    # Check if valid
    if not emitted_zip:
        raise RuntimeError("ZipValidatorAgent produced no events.")
    event_name, payload = emitted_zip[-1]
    if event_name != "ZipValid":
        reason = payload.get("reason", "<unknown>")
        LOG.error("ZIP invalid: %s", reason)
        raise RuntimeError(f"ZIP invalid: {reason}")

    LOG.info("ZIP valid; proceeding to extraction.")

    # -----------------------------
    # 2) Extraction
    # -----------------------------
    extraction_agent = ExtractionAgent()
    extraction_agent.emit = lambda name, payload: emitted_ext.append((name, payload))
    emitted_ext: List[Any] = []

    extraction_agent.handle({"type": "ZipValid", "zip_path": str(zip_path)})

    # We expect a series of FileDiscovered events, then one ExtractionDone
    if not emitted_ext:
        raise RuntimeError("ExtractionAgent produced no events.")

    # Gather all FileDiscovered payloads, and locate base_dir
    file_discovered_events = [evt for evt in emitted_ext if evt[0] == "FileDiscovered"]
    done_events = [evt for evt in emitted_ext if evt[0] == "ExtractionDone"]
    if not done_events:
        raise RuntimeError("ExtractionDid not emit ExtractionDone.")
    base_dir = Path(done_events[-1][1]["base_dir"])
    LOG.info("Extraction complete; base_dir = %s", base_dir)

    # -----------------------------
    # 3) Tree building
    # -----------------------------
    tree_agent = TreeBuilderAgent()
    tree_agent.emit = lambda name, payload: emitted_tree.append((name, payload))
    emitted_tree: List[Any] = []

    # Send all FileDiscovered
    for (_, payload_fd) in file_discovered_events:
        tree_agent.handle({"type": "FileDiscovered", "path": payload_fd["path"]})

    # Fire ExtractionDone
    tree_agent.handle({"type": "ExtractionDone", "base_dir": str(base_dir)})

    # Expect exactly one TreeBuilt
    if not emitted_tree or emitted_tree[-1][0] != "TreeBuilt":
        raise RuntimeError("TreeBuilderAgent failed to emit TreeBuilt.")
    tree_text = tree_agent.memory.get("project_tree.txt", "")
    LOG.info("Project tree built (%d chars)", len(tree_text))

    # -----------------------------
    # 4) File triage
    # -----------------------------
    triage_agent = FileTriageAgent()
    triage_agent.emit = lambda name, payload: emitted_triage.append((name, payload))
    emitted_triage: List[Any] = []

    # Send all FileDiscovered to triage
    for (_, payload_fd) in file_discovered_events:
        triage_agent.handle({"type": "FileDiscovered", "path": payload_fd["path"]})

    # Fire ExtractionDone
    triage_agent.handle({"type": "ExtractionDone", "base_dir": str(base_dir)})

    # Collect FileForAnalysis and (possibly) FileSkipped events
    file_for_analysis_events = [evt for evt in emitted_triage if evt[0] == "FileForAnalysis"]
    LOG.info("Triage enqueued %d files for analysis", len(file_for_analysis_events))

    # -----------------------------
    # 5) File analysis
    # -----------------------------
    analysis_agent = FileAnalysisAgent()
    analysis_agent.emit = lambda name, payload: emitted_analysis.append((name, payload))
    emitted_analysis: List[Any] = []

    # Before analyzing, let analysis_agent know base_dir (in case it needs it)
    # We can send an ExtractionDone just in case
    analysis_agent.handle({"type": "ExtractionDone", "base_dir": str(base_dir)})

    # Now send each FileForAnalysis
    for _, payload_fa in file_for_analysis_events:
        analysis_agent.handle(
            {"type": "FileForAnalysis", "path": payload_fa["path"], "score": payload_fa.get("score", 0)}
        )

    # Finally, fire TriageComplete
    analysis_agent.handle({"type": "TriageComplete"})

    # At this point, FileAnalysisAgent.memory should hold "file_summaries.json"
    summaries_json = analysis_agent.memory.get("file_summaries.json", "[]")
    try:
        file_summaries: List[Dict[str, Any]] = json.loads(summaries_json)
    except Exception:
        file_summaries = []
    LOG.info("File analysis complete; %d summaries generated", len(file_summaries))

    # -----------------------------
    # 6) Summary synthesizer
    # -----------------------------
    summary_agent = SummarySynthesizerAgent(model=None)
    summary_agent.emit = lambda name, payload: emitted_summary.append((name, payload))
    emitted_summary: List[Any] = []

    # Populate memory for tree and file_summaries
    summary_agent.memory["project_tree.txt"] = tree_text
    summary_agent.memory["file_summaries.json"] = summaries_json

    # Send all FileAnalysed events
    file_analysed_events = [evt for evt in emitted_analysis if evt[0] == "FileAnalysed"]
    for _, payload_fanal in file_analysed_events:
        summary_agent.handle({"type": "FileAnalysed", **payload_fanal})

    # Fire AnalysisComplete
    summary_agent.handle({"type": "AnalysisComplete"})

    # Fire TreeBuilt
    summary_agent.handle({"type": "TreeBuilt", "tree_path": "project_tree.txt"})

    # project_summary now in memory
    project_summary = summary_agent.memory.get("project_summary.txt", "")
    if not project_summary:
        LOG.warning("No project_summary.txt generated.")

    LOG.info("Run complete. Returning artefacts.")
    return {
        "tree_text": tree_text,
        "file_summaries": file_summaries,
        "project_summary": project_summary,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run full pipeline on a ZIP file")
    parser.add_argument("zip_path", type=Path, help="Path to the ZIP file to analyze")
    args = parser.parse_args()

    LOG.info("Running pipeline on %s", args.zip_path)
    try:
        result = run_workflow(args.zip_path)
        print("\n=== Workflow Result ===\n")

        print("--- Project Tree ---\n")
        print(result["tree_text"] or "(no tree generated)")

        print("\n--- File Summaries ---\n")
        if result["file_summaries"]:
            print(json.dumps(result["file_summaries"], indent=2))
        else:
            print("(no file summaries)")

        print("\n--- Project Summary ---\n")
        print(result["project_summary"] or "(no summary generated)")

    except Exception as e:
        LOG.exception("Pipeline failed: %s", e)
        exit(1)

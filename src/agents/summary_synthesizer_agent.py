"""
summary_synthesizer_agent.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Aggregates two artefacts produced by earlier agents:

  • project_tree.txt      (from TreeBuilderAgent)
  • file_summaries.json   (from FileAnalysisAgent)

Workflow
--------
1. Wait until both:
      • TreeBuilt          event has arrived
      • AnalysisComplete   event has arrived
2. Run `synthesise_project()` (heuristic summary using README line,
   dominant language, tech-stack inference, etc.)
3. Optionally send the draft through an LLM “polish” pass – the back-end
   is chosen automatically via `BEEAI_MODEL` (OpenAI, watsonx.ai, Ollama)
   and executed by `utils.llm_router.generate_completion()`.
4. Store the final text in BeeAI memory as 'project_summary.txt'.
5. Emit     ProjectDraft        (raw draft)
6. Emit     SummaryPolished     (with memory path to final text)

Incoming events
---------------
• TreeBuilt          { tree_path: str }
• FileAnalysed       { … }               (one per file)
• AnalysisComplete   {}                  (signals no more FileAnalysed)

Outgoing events
---------------
• ProjectDraft       { draft: str }
• SummaryPolished    { summary_path: str }
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List

# Updated imports to use beeai_framework instead of beeai
from beeai_framework.agent import Agent
from beeai_framework.typing import Event

from ..config import settings
from ..utils.language_detector import synthesise_project
from ..utils.llm_router import generate_completion  # ← new router

# --------------------------------------------------------------------------- #
# Configure logger for this agent
# --------------------------------------------------------------------------- #
LOG = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
#  Agent implementation
# --------------------------------------------------------------------------- #
class SummarySynthesizerAgent(Agent):
    name = "summary_synthesizer"

    def __init__(self, model: str | None = None) -> None:  # noqa: D401
        super().__init__()
        self._tree_text: str | None = None
        self._analyses: List[Dict[str, str]] = []
        self._analysis_done: bool = False
        self._model = model or settings.BEEAI_MODEL
        LOG.info("[summary_synthesizer] Initialized with model=%r", self._model)

    # ---------------- Event handling ----------------
    def handle(self, event: Event) -> None:  # noqa: D401
        LOG.info(">>> [summary_synthesizer] handle() entered. event=%r", event)
        event_type = event.get("type")

        if event_type == "TreeBuilt":
            tree_path = event.get("tree_path")
            LOG.info("[summary_synthesizer] Received TreeBuilt event, tree_path=%r", tree_path)
            # Retrieve the tree text from BeeAI memory
            self._tree_text = self.memory.get(tree_path, "")
            if self._tree_text:
                LOG.debug("[summary_synthesizer] Loaded tree text (first 100 chars): %.100s%s",
                          self._tree_text[:100], "…" if len(self._tree_text) > 100 else "")
            else:
                LOG.warning("[summary_synthesizer] No tree text found at key %r", tree_path)
            self._maybe_finish()

        elif event_type == "FileAnalysed":
            LOG.debug("[summary_synthesizer] Received FileAnalysed event: %r", event)
            self._analyses.append(event)
            LOG.info("[summary_synthesizer] Appended analysis for %r, total analyses=%d",
                     event.get("rel_path"), len(self._analyses))

        elif event_type == "AnalysisComplete":
            LOG.info("[summary_synthesizer] Received AnalysisComplete event")
            self._analysis_done = True
            self._maybe_finish()

        else:
            LOG.debug("[summary_synthesizer] Ignoring event type %r", event_type)

    # ---------------- Internals ----------------
    def _maybe_finish(self) -> None:
        """Called after every relevant event to see if we can finalise."""
        LOG.info("[summary_synthesizer] _maybe_finish() called. analysis_done=%r, tree_text_set=%r",
                 self._analysis_done, bool(self._tree_text))

        if not (self._analysis_done and self._tree_text):
            LOG.debug("[summary_synthesizer] Waiting for both tree and analyses to be ready")
            return  # Need both tree + analyses complete

        LOG.info("[summary_synthesizer] Both prerequisites met, generating draft")
        # 1) Heuristic draft
        draft = synthesise_project(self._analyses, self._tree_text)
        LOG.debug("[summary_synthesizer] Draft generated (first 200 chars): %.200s%s",
                  draft[:200], "…" if len(draft) > 200 else "")
        self.emit("ProjectDraft", {"draft": draft})
        LOG.info("[summary_synthesizer] Emitted ProjectDraft")

        # 2) Optional polish through selected LLM back-end
        polished = self._polish(draft)

        # 3) Persist & emit final
        self.memory["project_summary.txt"] = polished
        LOG.info("[summary_synthesizer] Stored 'project_summary.txt' in memory (length=%d)", len(polished))
        self.emit("SummaryPolished", {"summary_path": "project_summary.txt"})
        LOG.info("[summary_synthesizer] Emitted SummaryPolished with path 'project_summary.txt'")

    # --------------------------------------------------------------------- #
    #  LLM polish step (OpenAI / watsonx.ai / Ollama, via llm_router)
    # --------------------------------------------------------------------- #
    def _polish(self, raw: str) -> str:
        """Try to polish *raw* using whichever LLM back-end is configured."""
        LOG.info("[summary_synthesizer] _polish() called with raw draft (first 200 chars): %.200s%s",
                 raw[:200], "…" if len(raw) > 200 else "")
        try:
            result = generate_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a professional copy-editor. "
                            "Rewrite the summary so it is clear, engaging and no "
                            "longer than 150 words."
                        ),
                    },
                    {"role": "user", "content": raw},
                ],
                model_id=self._model,
                temperature=0.3,
            )
            LOG.info("[summary_synthesizer] Received polished summary (first 200 chars): %.200s%s",
                     result[:200], "…" if len(result) > 200 else "")
            return result
        except Exception as exc:  # pragma: no cover
            # Log and fall back to the unpolished draft
            LOG.warning("[summary_synthesizer] LLM polish step failed: %s", exc)
            return raw

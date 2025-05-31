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
from pathlib import Path
from typing import Dict, List

import beeai
from beeai.typing import Event

from ..config import settings
from ..utils.language_detector import synthesise_project
from ..utils.llm_router import generate_completion  # ← new router

# --------------------------------------------------------------------------- #
#  Agent implementation
# --------------------------------------------------------------------------- #
class SummarySynthesizerAgent(beeai.Agent):
    name = "summary_synthesizer"

    def __init__(self, model: str | None = None) -> None:  # noqa: D401
        super().__init__()
        self._tree_text: str | None = None
        self._analyses: List[Dict[str, str]] = []
        self._analysis_done: bool = False
        self._model = model or settings.BEEAI_MODEL

    # ---------------- Event handling ----------------
    def handle(self, event: Event) -> None:  # noqa: D401
        if event["type"] == "TreeBuilt":
            # Retrieve the tree text from BeeAI memory
            self._tree_text = self.memory.get(event["tree_path"], "")
            self._maybe_finish()

        elif event["type"] == "FileAnalysed":
            self._analyses.append(event)

        elif event["type"] == "AnalysisComplete":
            self._analysis_done = True
            self._maybe_finish()

    # ---------------- Internals ----------------
    def _maybe_finish(self) -> None:
        """Called after every relevant event to see if we can finalise."""
        if not (self._analysis_done and self._tree_text):
            return  # Need both tree + analyses complete

        # 1) Heuristic draft
        draft = synthesise_project(self._analyses, self._tree_text)
        self.emit("ProjectDraft", {"draft": draft})

        # 2) Optional polish through selected LLM back-end
        polished = self._polish(draft)

        # 3) Persist & emit final
        self.memory["project_summary.txt"] = polished
        self.emit("SummaryPolished", {"summary_path": "project_summary.txt"})

    # --------------------------------------------------------------------- #
    #  LLM polish step (OpenAI / watsonx.ai / Ollama, via llm_router)
    # --------------------------------------------------------------------- #
    def _polish(self, raw: str) -> str:
        """Try to polish *raw* using whichever LLM back-end is configured."""
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
            return result
        except Exception as exc:  # pragma: no cover
            # Log and fall back to the unpolished draft
            self.logger.warning("LLM polish step failed: %s", exc)
            return raw

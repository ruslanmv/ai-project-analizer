"""
summary_synthesizer_agent.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Aggregates:
• project_tree.txt   (from TreeBuilderAgent)
• file_summaries.json (from FileAnalysisAgent)

Runs heuristic `synthesise_project()` and – optionally – an LLM ‘polish’
step.  Stores the final text in 'project_summary.txt', emits *SummaryPolished*,
and then – unless configured otherwise – deletes the temp dir by emitting
*CleanupRequest* (consumed by CleanupAgent).

Incoming events
---------------
• TreeBuilt          { tree_path: str }
• FileAnalysed       { … }
• AnalysisComplete   {}

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

# Optional openai / watsonx for polishing
try:
    import openai
except ImportError:  # pragma: no cover
    openai = None  # type: ignore


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
            self._tree_text = self.memory.get(event["tree_path"], "")
            self._maybe_finish()
        elif event["type"] == "FileAnalysed":
            self._analyses.append(event)
        elif event["type"] == "AnalysisComplete":
            self._analysis_done = True
            self._maybe_finish()

    # ---------------- helpers ----------------
    def _maybe_finish(self) -> None:
        if self._analysis_done and self._tree_text:
            draft = synthesise_project(self._analyses, self._tree_text)
            self.emit("ProjectDraft", {"draft": draft})

            # Optional LLM polish step
            final = self._polish(draft) if openai else draft

            # Persist & emit SummaryPolished
            self.memory["project_summary.txt"] = final
            self.emit("SummaryPolished", {"summary_path": "project_summary.txt"})

    def _polish(self, raw: str) -> str:
        try:
            response = openai.ChatCompletion.create(
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a copy-editor. Rewrite the summary so it "
                            "is concise (≤150 words) and well-phrased."
                        ),
                    },
                    {"role": "user", "content": raw},
                ],
                temperature=0.3,
            )
            polished = response.choices[0].message.content.strip()
            return polished
        except Exception:  # pragma: no cover
            return raw

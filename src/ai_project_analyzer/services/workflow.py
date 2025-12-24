"""
Main workflow orchestration service.

Coordinates the multi-agent analysis pipeline using BeeAI framework.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from beeai_framework.workflows.workflow import Workflow

from ..core.config import settings
from ..core.exceptions import WorkflowError
from ..core.logging import LoggerMixin
from ..domain.models import AnalysisArtifacts, FileAnalysisResult


class WorkflowService(LoggerMixin):
    """
    Orchestrates the multi-agent analysis workflow.

    This service manages the complete analysis pipeline:
    1. ZIP validation
    2. File extraction
    3. File triage (prioritization)
    4. Tree building
    5. File analysis
    6. Summary synthesis
    """

    def __init__(self, model: str | None = None) -> None:
        """
        Initialize workflow service.

        Args:
            model: LLM model identifier (uses settings default if None)
        """
        self.model = model or settings.beeai_model
        self.workflow: Workflow | None = None

    def create_workflow(self) -> Workflow:
        """
        Create and configure BeeAI workflow from manifest.

        Returns:
            Configured workflow instance
        """
        # Find beeai.yaml in project root
        manifest_path = Path(__file__).parent.parent.parent.parent / "beeai.yaml"

        if not manifest_path.exists():
            raise WorkflowError(
                "BeeAI manifest not found",
                path=str(manifest_path),
            )

        self.logger.info(
            "loading_workflow",
            manifest=str(manifest_path),
            model=self.model,
        )

        try:
            workflow = Workflow(schema=str(manifest_path))
            self.logger.info("workflow_loaded")
            return workflow
        except Exception as e:
            self.logger.exception("workflow_creation_failed")
            raise WorkflowError(
                "Failed to create workflow",
                error=str(e),
                manifest=str(manifest_path),
            ) from e

    def run(
        self,
        zip_path: Path,
        *,
        print_events: bool = False,
    ) -> AnalysisArtifacts:
        """
        Execute the analysis workflow.

        Args:
            zip_path: Path to ZIP file to analyze
            print_events: Whether to print workflow events

        Returns:
            Analysis artifacts containing results

        Raises:
            WorkflowError: If workflow execution fails
        """
        # Validate ZIP size
        self._validate_zip_size(zip_path)

        # Create workflow
        workflow = self.create_workflow()

        # Prepare initial state
        initial_state: dict[str, Any] = {
            "NewUpload": {"zip_path": str(zip_path.resolve())}
        }

        self.logger.info(
            "starting_workflow",
            zip_path=str(zip_path),
            size_mb=zip_path.stat().st_size / 1_048_576,
        )

        try:
            # Run workflow
            run_output = workflow.run(state=initial_state)

            # Extract results from workflow state
            results = self._extract_results(run_output)

            self.logger.info(
                "workflow_completed",
                file_count=len(results.file_summaries),
            )

            return results

        except Exception as e:
            self.logger.exception("workflow_execution_failed")
            raise WorkflowError(
                "Workflow execution failed",
                error=str(e),
                zip_path=str(zip_path),
            ) from e

    def _validate_zip_size(self, zip_path: Path) -> None:
        """Validate ZIP file size against limits."""
        size_bytes = zip_path.stat().st_size
        max_bytes = settings.zip_size_limit_bytes

        if size_bytes > max_bytes:
            from ..core.exceptions import FileSizeLimitError

            raise FileSizeLimitError(
                f"ZIP file exceeds {settings.zip_size_limit_mb} MB limit",
                actual_mb=size_bytes / 1_048_576,
                limit_mb=settings.zip_size_limit_mb,
            )

    def _extract_results(self, run_output: Any) -> AnalysisArtifacts:
        """
        Extract results from workflow run output.

        Args:
            run_output: BeeAI workflow run result

        Returns:
            Structured analysis artifacts
        """
        # Try different attributes to access state
        state_attrs = [
            "state",
            "outputs",
            "result",
            "data",
            "memory",
            "final_state",
            "state_data",
        ]

        memory: dict[str, Any] | None = None

        for attr in state_attrs:
            try:
                candidate = getattr(run_output, attr, None)
                if candidate is None:
                    continue

                # If callable, try calling it
                if callable(candidate):
                    try:
                        candidate = candidate()
                    except Exception:
                        continue

                # Check if it's a dict-like object
                if isinstance(candidate, dict):
                    memory = candidate
                    self.logger.debug("found_state", attribute=attr)
                    break
            except Exception:
                continue

        if memory is None:
            # Fallback: try __dict__
            if hasattr(run_output, "__dict__"):
                for key, val in run_output.__dict__.items():
                    if isinstance(val, dict):
                        memory = val
                        self.logger.debug("found_state_in_dict", key=key)
                        break

        if memory is None:
            raise WorkflowError(
                "Could not extract state from workflow output",
                output_type=str(type(run_output)),
                available_attrs=dir(run_output),
            )

        # Extract artifacts from memory
        tree_text = memory.get("project_tree.txt", "")
        summaries_json = memory.get("file_summaries.json", "[]")
        project_summary = memory.get("project_summary.txt", "")

        # Parse file summaries
        try:
            summaries_data = json.loads(summaries_json) if summaries_json else []
            file_summaries = [
                FileAnalysisResult(**item) for item in summaries_data
            ]
        except Exception as e:
            self.logger.warning("failed_to_parse_summaries", error=str(e))
            file_summaries = []

        return AnalysisArtifacts(
            tree_text=tree_text,
            file_summaries=file_summaries,
            project_summary=project_summary,
        )


def analyze_codebase(
    zip_path: Path,
    model: str | None = None,
) -> AnalysisArtifacts:
    """
    High-level convenience function to analyze a codebase.

    Args:
        zip_path: Path to ZIP file
        model: Optional model override

    Returns:
        Analysis artifacts

    Example:
        >>> results = analyze_codebase(Path("project.zip"))
        >>> print(results.project_summary)
    """
    service = WorkflowService(model=model)
    return service.run(zip_path)

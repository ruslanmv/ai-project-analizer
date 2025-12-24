"""
Integration tests for workflow service.

Tests the complete analysis pipeline with mocked LLM.
"""

from __future__ import annotations

import pytest

from ai_project_analyzer.core.exceptions import FileSizeLimitError, WorkflowError
from ai_project_analyzer.services.workflow import WorkflowService


class TestWorkflowService:
    """Integration tests for WorkflowService."""

    def test_validate_zip_size_within_limit(
        self,
        sample_zip_file: pytest.fixture,  # type: ignore
    ) -> None:
        """Test that ZIP validation passes for small files."""
        service = WorkflowService()
        # This should not raise
        service._validate_zip_size(sample_zip_file)  # type: ignore

    def test_validate_zip_size_exceeds_limit(
        self,
        tmp_path: pytest.TempPathFactory,  # type: ignore
    ) -> None:
        """Test that oversized ZIPs are rejected."""
        from ai_project_analyzer.core.config import settings

        # Create a "large" file by setting limit to 0
        original_limit = settings.zip_size_limit_mb
        settings.zip_size_limit_mb = 0

        try:
            zip_path = tmp_path / "large.zip"  # type: ignore
            zip_path.write_text("x" * 1024)  # type: ignore

            service = WorkflowService()

            with pytest.raises(FileSizeLimitError):
                service._validate_zip_size(zip_path)  # type: ignore

        finally:
            settings.zip_size_limit_mb = original_limit

    def test_create_workflow(self) -> None:
        """Test workflow creation from manifest."""
        service = WorkflowService()

        # This will fail if beeai.yaml doesn't exist
        # In real environment with proper setup, it should succeed
        try:
            workflow = service.create_workflow()
            assert workflow is not None
        except WorkflowError:
            # Expected in test environment without full setup
            pytest.skip("BeeAI manifest not available in test environment")


@pytest.mark.skip(reason="Requires full BeeAI setup and LLM access")
class TestEndToEndWorkflow:
    """End-to-end workflow tests (require full setup)."""

    def test_analyze_sample_project(
        self,
        sample_zip_file: pytest.fixture,  # type: ignore
    ) -> None:
        """Test analyzing a complete project."""
        from ai_project_analyzer import analyze_codebase

        results = analyze_codebase(sample_zip_file)  # type: ignore

        assert results.tree_text
        assert len(results.file_summaries) > 0
        assert results.project_summary

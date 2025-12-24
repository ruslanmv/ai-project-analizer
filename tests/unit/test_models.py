"""
Unit tests for domain models.

Tests Pydantic model validation and business logic.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_project_analyzer.domain.models import (
    AnalysisArtifacts,
    AnalysisJob,
    AnalysisStatus,
    FileAnalysisResult,
    FileKind,
    ProjectSummary,
)


class TestFileAnalysisResult:
    """Tests for FileAnalysisResult model."""

    def test_create_valid_result(self) -> None:
        """Test creating a valid file analysis result."""
        result = FileAnalysisResult(
            rel_path="src/main.py",
            kind=FileKind.PYTHON,
            summary="Main entry point",
            lines=100,
            size_bytes=2048,
            language="python",
        )

        assert result.rel_path == "src/main.py"
        assert result.kind == FileKind.PYTHON
        assert result.lines == 100
        assert result.language == "python"

    def test_path_normalization(self) -> None:
        """Test that Windows paths are normalized to forward slashes."""
        result = FileAnalysisResult(
            rel_path=r"src\utils\helper.py",
            kind=FileKind.PYTHON,
        )

        assert result.rel_path == "src/utils/helper.py"

    def test_invalid_negative_lines(self) -> None:
        """Test that negative lines count raises validation error."""
        with pytest.raises(ValidationError):
            FileAnalysisResult(
                rel_path="test.py",
                kind=FileKind.PYTHON,
                lines=-1,
            )

    def test_summary_max_length(self) -> None:
        """Test summary length validation."""
        long_summary = "x" * 501

        with pytest.raises(ValidationError):
            FileAnalysisResult(
                rel_path="test.py",
                kind=FileKind.TEXT,
                summary=long_summary,
            )

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        result = FileAnalysisResult(rel_path="test.txt")

        assert result.kind == FileKind.UNKNOWN
        assert result.summary == ""
        assert result.lines == 0
        assert result.size_bytes == 0
        assert result.language is None


class TestProjectSummary:
    """Tests for ProjectSummary model."""

    def test_create_valid_summary(self) -> None:
        """Test creating a valid project summary."""
        summary = ProjectSummary(
            project_name="my-app",
            description="A test application",
            languages=["Python", "TypeScript"],
            frameworks=["FastAPI", "React"],
            file_count=50,
            line_count=2000,
        )

        assert summary.project_name == "my-app"
        assert len(summary.languages) == 2
        assert summary.file_count == 50

    def test_empty_project_name_invalid(self) -> None:
        """Test that empty project name raises error."""
        with pytest.raises(ValidationError):
            ProjectSummary(project_name="")


class TestAnalysisArtifacts:
    """Tests for AnalysisArtifacts model."""

    def test_create_artifacts(self) -> None:
        """Test creating analysis artifacts."""
        file_result = FileAnalysisResult(
            rel_path="main.py",
            kind=FileKind.PYTHON,
        )

        artifacts = AnalysisArtifacts(
            tree_text="project/\n  main.py",
            file_summaries=[file_result],
            project_summary="A Python project",
        )

        assert len(artifacts.file_summaries) == 1
        assert artifacts.project_summary == "A Python project"

    def test_to_dict_conversion(self) -> None:
        """Test conversion to dictionary."""
        artifacts = AnalysisArtifacts(
            tree_text="tree",
            file_summaries=[],
            project_summary="summary",
        )

        result_dict = artifacts.to_dict()

        assert isinstance(result_dict, dict)
        assert "tree_text" in result_dict
        assert "file_summaries" in result_dict
        assert "project_summary" in result_dict

    def test_artifacts_immutable(self) -> None:
        """Test that artifacts are immutable (frozen)."""
        artifacts = AnalysisArtifacts(
            tree_text="tree",
            file_summaries=[],
            project_summary="summary",
        )

        with pytest.raises(ValidationError):
            artifacts.tree_text = "modified"  # type: ignore


class TestAnalysisJob:
    """Tests for AnalysisJob model."""

    def test_create_job(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test creating an analysis job."""
        zip_path = tmp_path / "test.zip"  # type: ignore
        zip_path.write_text("fake zip")  # type: ignore

        job = AnalysisJob(
            job_id="test-123",
            zip_path=zip_path,
        )

        assert job.job_id == "test-123"
        assert job.status == AnalysisStatus.PENDING
        assert not job.is_complete

    def test_job_completion_check(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test job completion status."""
        zip_path = tmp_path / "test.zip"  # type: ignore
        zip_path.write_text("fake zip")  # type: ignore

        job = AnalysisJob(
            job_id="test-123",
            zip_path=zip_path,
            status=AnalysisStatus.COMPLETED,
        )

        assert job.is_complete

    def test_job_duration(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test job duration calculation."""
        from datetime import datetime, timedelta

        zip_path = tmp_path / "test.zip"  # type: ignore
        zip_path.write_text("fake zip")  # type: ignore

        now = datetime.utcnow()
        job = AnalysisJob(
            job_id="test-123",
            zip_path=zip_path,
            created_at=now,
            completed_at=now + timedelta(seconds=10),
        )

        assert job.duration_seconds is not None
        assert 9 <= job.duration_seconds <= 11  # Allow small variance

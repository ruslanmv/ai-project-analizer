"""
Pytest configuration and fixtures.

Provides shared fixtures and configuration for all tests.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Generator
from zipfile import ZipFile

import pytest

from ai_project_analyzer.core.config import Settings
from ai_project_analyzer.domain.models import FileAnalysisResult, FileKind


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_zip_file(temp_dir: Path) -> Path:
    """Create a sample ZIP file for testing."""
    zip_path = temp_dir / "test_project.zip"

    # Create sample project structure
    project_dir = temp_dir / "project"
    project_dir.mkdir()

    # Create sample files
    (project_dir / "README.md").write_text("# Test Project\nA sample project.")
    (project_dir / "main.py").write_text(
        "def main():\n    print('Hello, World!')\n\nif __name__ == '__main__':\n    main()"
    )
    (project_dir / "config.json").write_text('{"version": "1.0.0"}')

    # Create ZIP
    with ZipFile(zip_path, "w") as zipf:
        for file_path in project_dir.rglob("*"):
            if file_path.is_file():
                zipf.write(file_path, file_path.relative_to(project_dir))

    return zip_path


@pytest.fixture
def mock_settings() -> Settings:
    """Provide mock settings for testing."""
    return Settings(
        beeai_model="ollama/test",
        environment="testing",
        log_level="DEBUG",
        zip_size_limit_mb=10,
    )


@pytest.fixture
def sample_file_analysis() -> FileAnalysisResult:
    """Provide a sample file analysis result."""
    return FileAnalysisResult(
        rel_path="src/main.py",
        kind=FileKind.PYTHON,
        summary="Main application entry point",
        lines=50,
        size_bytes=1024,
        language="python",
    )

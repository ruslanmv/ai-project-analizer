"""
Domain models using Pydantic V2.

Defines the core data structures for the analyzer with:
- Strict type validation
- Immutability where appropriate
- Rich serialization support
- Clear documentation
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FileKind(str, Enum):
    """Enumeration of supported file kinds."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JSON = "json"
    YAML = "yaml"
    MARKDOWN = "markdown"
    TEXT = "text"
    ASSET = "asset"
    CONFIG = "config"
    DOCUMENTATION = "documentation"
    UNKNOWN = "unknown"


class AnalysisStatus(str, Enum):
    """Enumeration of analysis statuses."""

    PENDING = "pending"
    VALIDATING = "validating"
    EXTRACTING = "extracting"
    TRIAGING = "triaging"
    ANALYZING = "analyzing"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    OLLAMA = "ollama"
    WATSONX = "watsonx"


class FileAnalysisResult(BaseModel):
    """
    Result of analyzing a single file.

    Attributes:
        rel_path: Relative path from project root
        kind: Type of file
        summary: One-line summary description
        lines: Number of lines in file
        size_bytes: File size in bytes
        language: Detected programming language
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    rel_path: str = Field(
        ...,
        description="Relative path from project root",
        min_length=1,
    )

    kind: FileKind = Field(
        default=FileKind.UNKNOWN,
        description="File type classification",
    )

    summary: str = Field(
        default="",
        description="One-line summary of file contents",
        max_length=500,
    )

    lines: int = Field(
        default=0,
        ge=0,
        description="Number of lines in file",
    )

    size_bytes: int = Field(
        default=0,
        ge=0,
        description="File size in bytes",
    )

    language: str | None = Field(
        default=None,
        description="Detected programming language",
    )

    @field_validator("rel_path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        """Ensure path uses forward slashes."""
        return v.replace("\\", "/")


class ProjectTreeNode(BaseModel):
    """
    Node in the project directory tree.

    Attributes:
        name: File or directory name
        is_dir: Whether this is a directory
        children: Child nodes (for directories)
        file_info: File analysis result (for files)
    """

    model_config = ConfigDict(frozen=False)

    name: str = Field(..., description="File or directory name")
    is_dir: bool = Field(default=False, description="Whether this is a directory")
    children: list[ProjectTreeNode] = Field(
        default_factory=list,
        description="Child nodes for directories",
    )
    file_info: FileAnalysisResult | None = Field(
        default=None,
        description="File analysis result",
    )


class ProjectSummary(BaseModel):
    """
    Complete project analysis summary.

    Attributes:
        project_name: Inferred project name
        description: High-level project description
        languages: Primary programming languages detected
        frameworks: Detected frameworks/libraries
        file_count: Total number of files analyzed
        line_count: Total lines of code
        key_components: Major components/modules
        architecture_notes: Architectural observations
    """

    model_config = ConfigDict(frozen=False)

    project_name: str = Field(
        ...,
        description="Inferred project name",
        min_length=1,
    )

    description: str = Field(
        default="",
        description="High-level project description",
        max_length=1000,
    )

    languages: list[str] = Field(
        default_factory=list,
        description="Primary programming languages",
    )

    frameworks: list[str] = Field(
        default_factory=list,
        description="Detected frameworks and libraries",
    )

    file_count: int = Field(
        default=0,
        ge=0,
        description="Total files analyzed",
    )

    line_count: int = Field(
        default=0,
        ge=0,
        description="Total lines of code",
    )

    key_components: list[str] = Field(
        default_factory=list,
        description="Major components or modules",
    )

    architecture_notes: str = Field(
        default="",
        description="Architectural observations",
        max_length=2000,
    )


class AnalysisJob(BaseModel):
    """
    Represents a complete analysis job.

    Attributes:
        job_id: Unique job identifier
        zip_path: Path to uploaded ZIP file
        status: Current analysis status
        tree_text: Colorized directory tree
        file_summaries: Per-file analysis results
        project_summary: Overall project summary
        error: Error message if failed
        created_at: Job creation timestamp
        completed_at: Job completion timestamp
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
    )

    job_id: str = Field(
        ...,
        description="Unique job identifier",
        min_length=1,
    )

    zip_path: Path = Field(
        ...,
        description="Path to ZIP file being analyzed",
    )

    status: AnalysisStatus = Field(
        default=AnalysisStatus.PENDING,
        description="Current job status",
    )

    tree_text: str = Field(
        default="",
        description="Colorized directory tree visualization",
    )

    file_summaries: list[FileAnalysisResult] = Field(
        default_factory=list,
        description="Analysis results for each file",
    )

    project_summary: ProjectSummary | None = Field(
        default=None,
        description="Overall project summary",
    )

    error: str | None = Field(
        default=None,
        description="Error message if job failed",
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Job creation timestamp",
    )

    completed_at: datetime | None = Field(
        default=None,
        description="Job completion timestamp",
    )

    @property
    def is_complete(self) -> bool:
        """Check if job is complete."""
        return self.status in {AnalysisStatus.COMPLETED, AnalysisStatus.FAILED}

    @property
    def duration_seconds(self) -> float | None:
        """Get job duration in seconds."""
        if self.completed_at:
            return (self.completed_at - self.created_at).total_seconds()
        return None


class AnalysisArtifacts(BaseModel):
    """
    Output artifacts from analysis workflow.

    Attributes:
        tree_text: Directory tree visualization
        file_summaries: List of file analysis results
        project_summary: Overall project summary text
    """

    model_config = ConfigDict(frozen=True)

    tree_text: str = Field(
        default="",
        description="Directory tree visualization",
    )

    file_summaries: list[FileAnalysisResult] = Field(
        default_factory=list,
        description="File analysis results",
    )

    project_summary: str = Field(
        default="",
        description="Project overview text",
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "tree_text": self.tree_text,
            "file_summaries": [f.model_dump() for f in self.file_summaries],
            "project_summary": self.project_summary,
        }

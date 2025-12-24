"""
AI Project Analyzer - Enterprise-grade codebase analysis with AI.

A production-ready multi-agent system for analyzing codebases and generating
comprehensive documentation, summaries, and insights.
"""

from __future__ import annotations

__version__ = "2.0.0"
__author__ = "Ruslan Magana"
__email__ = "contact@ruslanmv.com"

from .core.config import settings
from .domain.models import (
    AnalysisArtifacts,
    AnalysisJob,
    AnalysisStatus,
    FileAnalysisResult,
    FileKind,
    ProjectSummary,
)
from .services.workflow import analyze_codebase

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "settings",
    "analyze_codebase",
    "AnalysisArtifacts",
    "AnalysisJob",
    "AnalysisStatus",
    "FileAnalysisResult",
    "FileKind",
    "ProjectSummary",
]

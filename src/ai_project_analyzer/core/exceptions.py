"""
Custom exception hierarchy for the AI Project Analyzer.

Provides domain-specific exceptions with rich error context.
"""

from __future__ import annotations

from typing import Any


class AnalyzerError(Exception):
    """Base exception for all analyzer errors."""

    def __init__(self, message: str, **context: Any) -> None:
        """
        Initialize exception with message and context.

        Args:
            message: Human-readable error message
            **context: Additional error context for logging
        """
        super().__init__(message)
        self.message = message
        self.context = context

    def __str__(self) -> str:
        """Return formatted error message."""
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} ({context_str})"
        return self.message


class ValidationError(AnalyzerError):
    """Raised when input validation fails."""


class ZipFileError(AnalyzerError):
    """Raised when ZIP file processing fails."""


class FileSizeLimitError(ZipFileError):
    """Raised when file exceeds size limits."""


class UnsupportedFileError(AnalyzerError):
    """Raised when file type is not supported."""


class AnalysisError(AnalyzerError):
    """Raised when code analysis fails."""


class LLMError(AnalyzerError):
    """Raised when LLM communication fails."""


class WorkflowError(AnalyzerError):
    """Raised when workflow execution fails."""


class ConfigurationError(AnalyzerError):
    """Raised when configuration is invalid."""


class ResourceExhaustedError(AnalyzerError):
    """Raised when system resources are exhausted."""


class TimeoutError(AnalyzerError):
    """Raised when operation times out."""


# Convenience error creation functions
def raise_validation_error(message: str, **context: Any) -> None:
    """Raise a validation error with context."""
    raise ValidationError(message, **context)


def raise_zip_error(message: str, **context: Any) -> None:
    """Raise a ZIP file error with context."""
    raise ZipFileError(message, **context)


def raise_analysis_error(message: str, **context: Any) -> None:
    """Raise an analysis error with context."""
    raise AnalysisError(message, **context)

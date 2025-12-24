"""
Structured logging configuration using structlog.

Provides:
- JSON and console formatters
- Contextual logging with bound fields
- Performance-optimized logging
- Production-ready log aggregation support
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from rich.console import Console
from rich.logging import RichHandler

from .config import settings

# Initialize Rich console for beautiful console output
console = Console()


def configure_logging() -> None:
    """
    Configure application-wide structured logging.

    Sets up structlog with appropriate processors based on environment.
    """
    # Determine processors based on log format
    if settings.log_format == "json":
        processors: list[Any] = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ]
        renderer = structlog.processors.JSONRenderer()
    else:
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(),
        ]
        renderer = structlog.dev.ConsoleRenderer()

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    if settings.log_format == "console" and not settings.is_production:
        # Use Rich handler for beautiful console output in development
        handler: logging.Handler = RichHandler(
            console=console,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
            show_time=True,
            show_path=True,
        )
    else:
        # Use standard handler for production/JSON logging
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, settings.log_level))

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)

    # Optional file logging
    if settings.log_file:
        file_handler = logging.FileHandler(settings.log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured structlog logger

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("processing_file", filename="app.py", lines=100)
    """
    return structlog.get_logger(name)


class LoggerMixin:
    """
    Mixin class to add logging capability to any class.

    Automatically creates a logger with the class name.

    Example:
        >>> class MyService(LoggerMixin):
        ...     def process(self):
        ...         self.logger.info("processing_started")
    """

    @property
    def logger(self) -> structlog.stdlib.BoundLogger:
        """Get logger bound to this class."""
        if not hasattr(self, "_logger"):
            self._logger = get_logger(self.__class__.__name__)
        return self._logger


# Configure logging on module import
configure_logging()

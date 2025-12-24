"""
Core configuration management using Pydantic V2 Settings.

This module provides type-safe, validated configuration management with support for:
- Environment variables
- .env file loading
- Runtime validation
- Immutable settings
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application-wide configuration with environment variable support.

    All settings can be overridden via environment variables or .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # LLM Configuration
    # ═══════════════════════════════════════════════════════════════════════
    beeai_model: str = Field(
        default="openai/gpt-4o-mini",
        description="LLM model identifier (prefix: openai/, ollama/, watsonx/)",
    )

    openai_api_key: str | None = Field(
        default=None,
        description="OpenAI API key for GPT models",
    )

    ollama_url: str = Field(
        default="http://localhost:11434",
        description="Ollama server URL for local models",
    )

    watsonx_api_key: str | None = Field(
        default=None,
        description="IBM WatsonX API key",
    )

    watsonx_url: str | None = Field(
        default=None,
        description="IBM WatsonX endpoint URL",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # Application Configuration
    # ═══════════════════════════════════════════════════════════════════════
    app_name: str = Field(
        default="AI Project Analyzer",
        description="Application display name",
    )

    app_version: str = Field(
        default="2.0.0",
        description="Application version",
    )

    environment: Literal["development", "production", "testing"] = Field(
        default="development",
        description="Runtime environment",
    )

    debug: bool = Field(
        default=False,
        description="Enable debug mode",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # File Processing Configuration
    # ═══════════════════════════════════════════════════════════════════════
    zip_size_limit_mb: int = Field(
        default=300,
        ge=1,
        le=1000,
        description="Maximum compressed ZIP file size in MB",
    )

    max_member_size_mb: int = Field(
        default=150,
        ge=1,
        le=500,
        description="Maximum uncompressed file size in MB",
    )

    delete_temp_after_run: bool = Field(
        default=True,
        description="Delete temporary extracted files after analysis",
    )

    max_files_to_analyze: int = Field(
        default=500,
        ge=1,
        description="Maximum number of files to analyze in a project",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # Logging Configuration
    # ═══════════════════════════════════════════════════════════════════════
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level",
    )

    log_format: Literal["json", "console"] = Field(
        default="console",
        description="Log output format",
    )

    log_file: Path | None = Field(
        default=None,
        description="Optional log file path",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # Web Server Configuration
    # ═══════════════════════════════════════════════════════════════════════
    app_host: str = Field(
        default="0.0.0.0",
        description="Web server host",
    )

    app_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Web server port",
    )

    workers: int = Field(
        default=4,
        ge=1,
        le=16,
        description="Number of worker processes",
    )

    cors_origins: list[str] = Field(
        default_factory=lambda: ["*"],
        description="CORS allowed origins",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # Performance Configuration
    # ═══════════════════════════════════════════════════════════════════════
    max_concurrent_analyses: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum concurrent file analyses",
    )

    request_timeout_seconds: int = Field(
        default=300,
        ge=10,
        le=3600,
        description="HTTP request timeout in seconds",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # Validators
    # ═══════════════════════════════════════════════════════════════════════
    @field_validator("log_level", mode="before")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Ensure log level is uppercase."""
        return v.upper() if isinstance(v, str) else v

    @field_validator("beeai_model")
    @classmethod
    def validate_model_format(cls, v: str) -> str:
        """Validate model identifier format."""
        valid_prefixes = ("openai/", "ollama/", "watsonx/")
        if not any(v.startswith(prefix) for prefix in valid_prefixes) and "/" not in v:
            # Default to ollama if no prefix
            return f"ollama/{v}"
        return v

    # ═══════════════════════════════════════════════════════════════════════
    # Helper Methods
    # ═══════════════════════════════════════════════════════════════════════
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    @property
    def zip_size_limit_bytes(self) -> int:
        """Get ZIP size limit in bytes."""
        return self.zip_size_limit_mb * 1_048_576

    @property
    def max_member_size_bytes(self) -> int:
        """Get max member size in bytes."""
        return self.max_member_size_mb * 1_048_576


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Get cached application settings instance.

    Returns:
        Settings: Singleton settings object
    """
    return Settings()


# Convenience export
settings: Settings = get_settings()

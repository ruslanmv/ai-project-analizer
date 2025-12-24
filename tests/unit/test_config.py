"""
Unit tests for configuration management.

Tests settings validation and environment variable handling.
"""

from __future__ import annotations

from ai_project_analyzer.core.config import Settings


class TestSettings:
    """Tests for Settings configuration."""

    def test_default_settings(self) -> None:
        """Test that default settings are valid."""
        settings = Settings()

        assert settings.app_name == "AI Project Analyzer"
        assert settings.app_version == "2.0.0"
        assert settings.log_level == "INFO"
        assert settings.zip_size_limit_mb >= 1

    def test_model_validation(self) -> None:
        """Test model identifier validation."""
        settings = Settings(beeai_model="llama3")

        # Should auto-prefix with ollama/
        assert settings.beeai_model.startswith("ollama/")

    def test_environment_helpers(self) -> None:
        """Test environment check helper methods."""
        dev_settings = Settings(environment="development")
        prod_settings = Settings(environment="production")

        assert dev_settings.is_development
        assert not dev_settings.is_production
        assert prod_settings.is_production
        assert not prod_settings.is_development

    def test_size_limit_bytes_conversion(self) -> None:
        """Test MB to bytes conversion."""
        settings = Settings(zip_size_limit_mb=100)

        assert settings.zip_size_limit_bytes == 100 * 1_048_576

    def test_log_level_uppercase(self) -> None:
        """Test that log level is converted to uppercase."""
        settings = Settings(log_level="debug")

        assert settings.log_level == "DEBUG"

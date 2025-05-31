"""
Centralised configuration & environment variable management.

All tunables are exposed as a pydantic `BaseSettings` so they can be
overridden via:

  • real environment variables, e.g.   export BEEAI_MODEL=openai/gpt-4o
  • a local '.env' file in your project root
  • kwargs when instantiating `Settings(...)` (mainly in tests)
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

try:
    from pydantic import BaseSettings, Field
except ImportError:  # pragma: no cover
    # Stubs so that code completion still works when pydantic is absent
    class BaseSettings:  # type: ignore
        def __init__(self, **kw):  # noqa: D401
            for k, v in kw.items():
                setattr(self, k, v)

    def Field(default, **kw):  # type: ignore
        return default

# --------------------------------------------------------------------------- #
# Configure logger for this module
# --------------------------------------------------------------------------- #
LOG = logging.getLogger(__name__)


class Settings(BaseSettings):
    """App-wide settings (override with env-vars)."""

    BEEAI_MODEL: str = Field(
        default="openai/gpt-4o-mini",
        description="Default foundation-model ID used by BeeAI LLM-agents.",
    )
    DELETE_TEMP_AFTER_RUN: bool = Field(
        default=True,
        description="Delete extracted temp dir after workflow finishes.",
    )
    ZIP_SIZE_LIMIT_MB: int = Field(
        default=300,
        ge=1,
        description="Hard upper limit on *compressed* archive size.",
    )
    MAX_MEMBER_SIZE_MB: int = Field(
        default=150,
        ge=1,
        description="Max *uncompressed* size allowed for a single ZIP entry.",
    )
    LOG_LEVEL: str = Field(default="INFO")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return memoised singleton settings object."""
    env_override = os.getenv("AI_ANALYSER_ENV_FILE")
    if env_override and Path(env_override).exists():
        LOG.info(
            "[config] Loading settings from overridden .env file: %r", env_override
        )
        settings_obj = Settings(_env_file=env_override)
    else:
        LOG.info("[config] Loading settings from default environment or .env")
        settings_obj = Settings()

    # Log all loaded settings
    try:
        # Attempt to pretty-print the settings as a dict
        loaded = settings_obj.dict()
    except Exception:
        # Fallback: manually access attributes
        loaded = {
            "BEEAI_MODEL": settings_obj.BEEAI_MODEL,
            "DELETE_TEMP_AFTER_RUN": settings_obj.DELETE_TEMP_AFTER_RUN,
            "ZIP_SIZE_LIMIT_MB": settings_obj.ZIP_SIZE_LIMIT_MB,
            "MAX_MEMBER_SIZE_MB": settings_obj.MAX_MEMBER_SIZE_MB,
            "LOG_LEVEL": settings_obj.LOG_LEVEL,
        }
    LOG.debug("[config] Final settings: %r", loaded)
    return settings_obj


# Public, convenient alias
settings: Settings = get_settings()

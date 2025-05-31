"""
Centralised configuration & environment variable management.

All tunables are exposed as a pydantic `BaseSettings` so they can be
overridden via:

  • real environment variables, e.g.   export BEEAI_MODEL=openai/gpt-4o
  • a local '.env' file in your project root
  • kwargs when instantiating `Settings(...)` (mainly in tests)
"""

from __future__ import annotations

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
    # Allow test-suites to inject `AI_ANALYSER_ENV_FILE=/path/to/.env.test`
    env_override = os.getenv("AI_ANALYSER_ENV_FILE")
    if env_override and Path(env_override).exists():
        return Settings(_env_file=env_override)
    return Settings()


# Public, convenient alias
settings: Settings = get_settings()

"""Configuration management for ArtifactForge."""

import os
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = Field(
        default="postgresql://artifactforge:artifactforge@localhost:5432/artifactforge",
        description="PostgreSQL connection string",
    )

    # LLM Providers (OpenRouter preferred)
    openai_api_key: Optional[str] = Field(
        default=None, description="OpenAI/OpenRouter API key"
    )
    openai_api_base: Optional[str] = Field(
        default=None,
        description="OpenAI API base URL (defaults to OpenRouter)",
    )
    anthropic_api_key: Optional[str] = Field(
        default=None, description="Anthropic API key (unused if OpenRouter configured)"
    )

    # Application
    log_level: str = Field(default="INFO", description="Logging level")
    environment: str = Field(default="development", description="Environment")

    def get_openai_base_url(self) -> str:
        """Get the OpenAI-compatible base URL."""
        if self.openai_api_base:
            return self.openai_api_base
        # Default to OpenRouter
        return os.getenv("OPENAI_API_BASE", "https://openrouter.ai/api/v1")

    def get_openai_api_key(self) -> Optional[str]:
        """Get the OpenAI API key from settings or environment."""
        return self.openai_api_key or os.getenv("OPENAI_API_KEY")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

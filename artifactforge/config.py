"""Configuration management for artifactory."""

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
    database_url: Optional[str] = Field(
        default=None,
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

    # Optional Research Tool API Keys
    tavily_api_key: Optional[str] = Field(default=None, description="Tavily API key")
    exa_api_key: Optional[str] = Field(default=None, description="Exa API key")
    firecrawl_api_key: Optional[str] = Field(
        default=None, description="Firecrawl API key"
    )
    context7_api_key: Optional[str] = Field(
        default=None, description="Context7 API key"
    )

    ollama_base_url: Optional[str] = Field(
        default=None, description="Ollama base URL (e.g. http://localhost:11434)"
    )
    ollama_model: Optional[str] = Field(default=None, description="Ollama model name")

    # Unified LLM configuration (overrides provider-specific defaults)
    llm_provider: Optional[str] = Field(
        default=None,
        description="Force LLM provider: ollama, openai, openrouter, anthropic, mlx",
    )
    llm_model: Optional[str] = Field(
        default=None,
        description="Default model for all agents (e.g. kimi-k2.5:cloud, gpt-4o, claude-sonnet-4-20250514)",
    )

    # Multi-model routing: per-tier model overrides
    # When set, agents are routed to the appropriate tier model instead of llm_model.
    precision_llm_model: Optional[str] = Field(
        default=None,
        description="Model for precision tasks: intent parsing, evidence classification, verification, adversarial review",
    )
    writing_llm_model: Optional[str] = Field(
        default=None,
        description="Model for writing tasks: drafting, polishing, analysis, content strategy",
    )
    speed_llm_model: Optional[str] = Field(
        default=None,
        description="Model for speed tasks: research planning, arbitration, visual pipeline",
    )

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

"""Generic generator tool - schema-based artifact generation."""

import json
import os
from typing import Any, Dict

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from artifactforge.config import get_settings

settings = get_settings()
OPENAI_API_KEY = settings.openai_api_key or os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")


class GenerateInput(BaseModel):
    """Input for generic generator."""

    artifact_type: str = Field(description="Type of artifact to generate")
    schema: Dict[str, Any] = Field(description="Artifact schema definition")
    context: Dict[str, Any] = Field(description="Research context")
    user_description: str = Field(description="Original user description")


async def _generate_with_llm(
    artifact_type: str,
    schema: Dict[str, Any],
    context: Dict[str, Any],
    user_description: str,
) -> dict[str, Any]:
    """Generate artifact using LLM."""
    if ANTHROPIC_API_KEY:
        return await _generate_with_anthropic(
            artifact_type, schema, context, user_description
        )
    elif OPENAI_API_KEY:
        return await _generate_with_openai(
            artifact_type, schema, context, user_description
        )
    else:
        return _mock_generate(artifact_type, user_description)


async def _generate_with_anthropic(
    artifact_type: str,
    schema: Dict[str, Any],
    context: Dict[str, Any],
    user_description: str,
) -> dict[str, Any]:
    """Generate using Anthropic API."""
    prompt = f"""Generate a {artifact_type} based on the following:

User Request: {user_description}

Schema: {json.dumps(schema, indent=2)}

Research Context:
{json.dumps(context, indent=2)}

Generate the artifact in the specified format."""

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        response.raise_for_status()
        data = response.json()

    draft = data["content"][0]["text"]

    return {
        "artifact_type": artifact_type,
        "draft": draft,
        "metadata": {
            "confidence": 0.85,
            "model": "claude-3-5-sonnet",
            "requires_review": ["generic"],
        },
    }


async def _generate_with_openai(
    artifact_type: str,
    schema: Dict[str, Any],
    context: Dict[str, Any],
    user_description: str,
) -> dict[str, Any]:
    """Generate using OpenAI API."""
    prompt = f"""Generate a {artifact_type} based on the following:

User Request: {user_description}

Schema: {json.dumps(schema, indent=2)}

Research Context:
{json.dumps(context, indent=2)}

Generate the artifact in the specified format."""

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 4096,
            },
        )
        response.raise_for_status()
        data = response.json()

    draft = data["choices"][0]["message"]["content"]

    return {
        "artifact_type": artifact_type,
        "draft": draft,
        "metadata": {
            "confidence": 0.85,
            "model": "gpt-4o",
            "requires_review": ["generic"],
        },
    }


def _mock_generate(artifact_type: str, user_description: str) -> dict[str, Any]:
    """Mock generation when no API keys available."""
    return {
        "artifact_type": artifact_type,
        "draft": f"# {artifact_type.title()}\n\nGenerated from: {user_description}\n\n(This is a mock - no LLM API key configured)",
        "metadata": {
            "confidence": 0.3,
            "model": "mock",
            "requires_review": ["generic"],
        },
    }


@tool(args_schema=GenerateInput)
def generic_generator(
    artifact_type: str,
    schema: Dict[str, Any],
    context: Dict[str, Any],
    user_description: str,
) -> Dict[str, Any]:
    """Generate an artifact based on schema and context.

    Uses LLM to generate content based on research findings and schema.
    """
    import asyncio

    return asyncio.run(
        _generate_with_llm(artifact_type, schema, context, user_description)
    )


__all__ = ["generic_generator"]

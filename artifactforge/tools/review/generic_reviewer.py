"""Generic reviewer tool - reviews artifact drafts for quality."""

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


class ReviewInput(BaseModel):
    """Input for generic reviewer."""

    artifact_type: str = Field(description="Type of artifact")
    draft: str = Field(description="Artifact draft to review")
    context: Dict[str, Any] = Field(description="Research context")


async def _review_with_llm(
    artifact_type: str,
    draft: str,
    context: Dict[str, Any],
) -> dict[str, Any]:
    """Review artifact using LLM."""
    if ANTHROPIC_API_KEY:
        return await _review_with_anthropic(artifact_type, draft, context)
    elif OPENAI_API_KEY:
        return await _review_with_openai(artifact_type, draft, context)
    else:
        return _mock_review(artifact_type)


async def _review_with_anthropic(
    artifact_type: str,
    draft: str,
    context: Dict[str, Any],
) -> dict[str, Any]:
    """Review using Anthropic API."""
    prompt = f"""Review the following {artifact_type} draft:

Draft:
{draft[:4000]}

Context:
{json.dumps(context, indent=2)[:1000]}

Evaluate:
1. completeness (0-1)
2. clarity (0-1)
3. accuracy (0-1)

Respond with JSON:
{{"passed": true/false, "issues": [], "suggestions": [], "scores": {{"completeness": 0.0, "clarity": 0.0, "accuracy": 0.0}}}}"""

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
                "max_tokens": 2048,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        response.raise_for_status()
        data = response.json()

    text = data["content"][0]["text"]

    try:
        result = json.loads(text)
        return result
    except json.JSONDecodeError:
        return _parse_review_text(text)


async def _review_with_openai(
    artifact_type: str,
    draft: str,
    context: Dict[str, Any],
) -> dict[str, Any]:
    """Review using OpenAI API."""
    prompt = f"""Review the following {artifact_type} draft:

Draft:
{draft[:4000]}

Context:
{json.dumps(context, indent=2)[:1000]}

Evaluate:
1. completeness (0-1)
2. clarity (0-1)
3. accuracy (0-1)

Respond with JSON:
{{"passed": true/false, "issues": [], "suggestions": [], "scores": {{"completeness": 0.0, "clarity": 0.0, "accuracy": 0.0}}}}"""

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
                "max_tokens": 2048,
                "response_format": {"type": "json_object"},
            },
        )
        response.raise_for_status()
        data = response.json()

    text = data["choices"][0]["message"]["content"]

    try:
        result = json.loads(text)
        return result
    except json.JSONDecodeError:
        return _parse_review_text(text)


def _parse_review_text(text: str) -> dict[str, Any]:
    """Parse review text when JSON parsing fails."""
    lines = text.split("\n")
    issues = []
    suggestions = []
    scores = {"completeness": 0.5, "clarity": 0.5, "accuracy": 0.5}

    for line in lines:
        line = line.strip().lower()
        if "issue" in line or "problem" in line:
            issues.append(line)
        if "suggest" in line or "improve" in line:
            suggestions.append(line)

    passed = len(issues) < 3

    return {
        "passed": passed,
        "issues": issues,
        "suggestions": suggestions,
        "scores": scores,
    }


def _mock_review(artifact_type: str) -> dict[str, Any]:
    """Mock review when no API keys available."""
    return {
        "passed": True,
        "issues": [],
        "suggestions": ["Consider adding more details"],
        "scores": {"completeness": 0.6, "clarity": 0.7, "accuracy": 0.5},
    }


@tool(args_schema=ReviewInput)
def generic_reviewer(
    artifact_type: str,
    draft: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Review artifact draft for quality.

    Uses LLM to evaluate completeness, clarity, and accuracy.
    """
    import asyncio

    return asyncio.run(_review_with_llm(artifact_type, draft, context))


__all__ = ["generic_reviewer"]

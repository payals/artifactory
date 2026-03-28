"""Deep analyzer tool - analyzes search results in depth."""

import asyncio
import os
from typing import Any, List

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from artifactforge.config import get_settings

settings = get_settings()
OPENAI_API_KEY = settings.openai_api_key or os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")


class DeepAnalyzeInput(BaseModel):
    """Input for deep analyzer."""

    sources: List[str] = Field(description="List of URLs to analyze")
    query: str = Field(description="Original query context")


async def _fetch_url_content(url: str) -> str:
    """Fetch content from a URL."""
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            text = response.text
            return text[:10000]
    except Exception as e:
        return f"Error fetching {url}: {e}"


async def _analyze_with_llm(
    sources: List[str], content: str, query: str
) -> dict[str, Any]:
    """Analyze content using LLM."""
    if ANTHROPIC_API_KEY:
        return await _analyze_with_anthropic(sources, content, query)
    elif OPENAI_API_KEY:
        return await _analyze_with_openai(sources, content, query)
    else:
        return _mock_analysis(sources, query)


async def _analyze_with_anthropic(
    sources: List[str], content: str, query: str
) -> dict[str, Any]:
    """Analyze using Anthropic API."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": "claude-3-haiku-20240307",
                "max_tokens": 1024,
                "messages": [
                    {
                        "role": "user",
                        "content": f"""Analyze the following web content for the query: {query}

Sources: {", ".join(sources)}

Content:
{content[:8000]}

Provide:
1. Key findings (3-5 bullet points)
2. A brief summary""",
                    }
                ],
            },
        )
        response.raise_for_status()
        data = response.json()

    text = data["content"][0]["text"]
    lines = text.split("\n")
    findings = [l for l in lines if l.strip() and not l.startswith("Provide:")]
    summary = f"Analysis of {len(sources)} sources using Claude"

    return {"key_findings": findings[:5], "summary": summary}


async def _analyze_with_openai(
    sources: List[str], content: str, query: str
) -> dict[str, Any]:
    """Analyze using OpenAI API."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "user",
                        "content": f"""Analyze the following web content for the query: {query}

Sources: {", ".join(sources)}

Content:
{content[:8000]}

Provide:
1. Key findings (3-5 bullet points)
2. A brief summary""",
                    }
                ],
                "max_tokens": 1024,
            },
        )
        response.raise_for_status()
        data = response.json()

    text = data["choices"][0]["message"]["content"]
    lines = text.split("\n")
    findings = [l for l in lines if l.strip() and not l.startswith("Provide:")]
    summary = f"Analysis of {len(sources)} sources using GPT-4"

    return {"key_findings": findings[:5], "summary": summary}


def _mock_analysis(sources: List[str], query: str) -> dict[str, Any]:
    """Mock analysis when no API keys available."""
    return {
        "key_findings": [
            f"Found relevant information about {query}",
            "Multiple sources confirm key trends",
            "Content analysis reveals common themes",
        ],
        "summary": f"Analysis of {len(sources)} sources (no LLM API key - using mock)",
    }


@tool(args_schema=DeepAnalyzeInput)
def deep_analyzer(sources: List[str], query: str) -> dict[str, Any]:
    """Analyze search results in depth, extracting key information.

    Fetches content from URLs and uses LLM to extract insights.
    """
    import asyncio

    contents = asyncio.run(_fetch_all_sources(sources))

    combined = "\n\n---\n\n".join(contents)

    return asyncio.run(_analyze_with_llm(sources, combined, query))


async def _fetch_all_sources(sources: List[str]) -> List[str]:
    """Fetch all sources concurrently."""
    tasks = [_fetch_url_content(url) for url in sources]
    return await asyncio.gather(*tasks)


__all__ = ["deep_analyzer"]

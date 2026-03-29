"""Deep analyzer tool - analyzes search results in depth."""

import asyncio
import logging
import os
from typing import Any, List

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from artifactforge.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()
OPENAI_API_KEY = settings.openai_api_key or os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")


class FetchResult(BaseModel):
    """Result of fetching a URL."""

    url: str
    content: str = ""
    success: bool = True
    error: str | None = None


class DeepAnalyzeInput(BaseModel):
    """Input for deep analyzer."""

    sources: List[str] = Field(description="List of URLs to analyze")
    query: str = Field(description="Original query context")


async def _fetch_url_content(url: str) -> FetchResult:
    """Fetch content from a URL with proper error handling."""
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            text = response.text
            if len(text) < 100:
                return FetchResult(
                    url=url, success=False, error="Content too short (<100 chars)"
                )
            return FetchResult(url=url, content=text[:10000])
    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP error fetching {url}: {e.response.status_code}")
        return FetchResult(
            url=url, success=False, error=f"HTTP {e.response.status_code}"
        )
    except httpx.TimeoutException:
        logger.warning(f"Timeout fetching {url}")
        return FetchResult(url=url, success=False, error="Request timeout")
    except Exception as e:
        logger.warning(f"Error fetching {url}: {e}")
        return FetchResult(url=url, success=False, error=str(e))


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
    headers: dict[str, str] = {
        "x-api-key": ANTHROPIC_API_KEY or "",
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
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
    return run_deep_analyzer(sources=sources, query=query)


def run_deep_analyzer(sources: List[str], query: str) -> dict[str, Any]:
    import asyncio

    fetch_results = asyncio.run(_fetch_all_sources(sources))
    successful_results = [r for r in fetch_results if r.success]
    failed_results = [r for r in fetch_results if not r.success]

    if failed_results:
        logger.warning(
            f"Failed to fetch {len(failed_results)}/{len(sources)} URLs: "
            f"{[r.url for r in failed_results]}"
        )

    if not successful_results:
        logger.error("All URL fetches failed")
        return {
            "key_findings": [],
            "summary": "Failed to fetch any sources",
        }

    contents = [r.content for r in successful_results]
    valid_sources = [r.url for r in successful_results]
    combined = "\n\n---\n\n".join(contents)

    return asyncio.run(_analyze_with_llm(valid_sources, combined, query))


async def _fetch_all_sources(sources: List[str]) -> List[FetchResult]:
    """Fetch all sources concurrently."""
    tasks = [_fetch_url_content(url) for url in sources]
    return await asyncio.gather(*tasks)


__all__ = ["deep_analyzer", "run_deep_analyzer"]

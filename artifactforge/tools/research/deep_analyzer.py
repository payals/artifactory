"""Deep analyzer tool - analyzes search results in depth."""

import asyncio
import logging
from typing import Any, List

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from artifactforge.observability.middleware import emit_status, get_trace_id

logger = logging.getLogger(__name__)


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
    emit_status(
        f"Fetching source {url[:80]}",
        trace_id=get_trace_id(),
        node_name="deep_analyzer",
        metadata={"kind": "fetch", "url": url},
    )
    try:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
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


def _analyze_content(
    sources: List[str], content: str, query: str
) -> dict[str, Any]:
    """Analyze content using the centralized LLM gateway."""
    from artifactforge.agents.llm_gateway import call_llm

    text = call_llm(
        system_prompt="You are an analytical research assistant.",
        user_prompt=(
            f"Analyze the following web content for the query: {query}\n\n"
            f"Sources: {', '.join(sources)}\n\n"
            f"Content:\n{content[:8000]}\n\n"
            "Provide:\n1. Key findings (3-5 bullet points)\n2. A brief summary"
        ),
        agent_name="deep_analyzer",
    )
    lines = text.split("\n")
    findings = [l for l in lines if l.strip() and not l.startswith("Provide:")]
    return {
        "key_findings": findings[:5],
        "summary": f"Analysis of {len(sources)} sources",
    }


@tool(args_schema=DeepAnalyzeInput)
def deep_analyzer(sources: List[str], query: str) -> dict[str, Any]:
    """Analyze search results in depth, extracting key information.

    Fetches content from URLs and uses LLM to extract insights.
    """
    return run_deep_analyzer(sources=sources, query=query)


async def _fetch_and_analyze(
    sources: List[str], query: str
) -> dict[str, Any]:
    """Fetch all sources and analyze them in one coroutine."""
    fetch_results = await _fetch_all_sources(sources)
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

    return _analyze_content(valid_sources, combined, query)


def run_deep_analyzer(sources: List[str], query: str) -> dict[str, Any]:
    from artifactforge.tools.research.async_compat import run_async_safely

    emit_status(
        f"Starting deep analysis of {len(sources)} sources",
        trace_id=get_trace_id(),
        node_name="deep_analyzer",
        metadata={"kind": "status", "query": query, "source_count": len(sources)},
    )

    result = run_async_safely(_fetch_and_analyze(sources, query))

    emit_status(
        f"Analysis complete with {len(result.get('key_findings', []))} findings",
        trace_id=get_trace_id(),
        node_name="deep_analyzer",
        metadata={"kind": "complete", "query": query},
    )

    return result


async def _fetch_all_sources(sources: List[str]) -> List[FetchResult]:
    """Fetch all sources concurrently."""
    tasks = [_fetch_url_content(url) for url in sources]
    return await asyncio.gather(*tasks)


__all__ = ["deep_analyzer", "run_deep_analyzer"]

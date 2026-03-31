"""Web searcher tool - searches the web for information."""

from datetime import datetime
import logging
import os
from typing import Any

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from artifactforge.observability.middleware import emit_status, get_trace_id

logger = logging.getLogger(__name__)

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")


class SearchError(Exception):
    """Raised when all search backends fail."""

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or []


class SearchResult(BaseModel):
    """Structured search result with success/error information."""

    success: bool = True
    query: str = ""
    results: list[dict[str, str]] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    error: str | None = None


class WebSearchInput(BaseModel):
    """Input for web searcher."""

    query: str = Field(description="The search query")
    num_results: int = Field(default=5, description="Number of results")


async def _search_tavily(query: str, num_results: int) -> SearchResult:
    """Search using Tavily API."""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={"query": query, "max_results": num_results},
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

        results = data.get("results", [])
        return SearchResult(
            success=True,
            query=query,
            results=[
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", ""),
                }
                for r in results
            ],
            sources=[r.get("url", "") for r in results],
        )
    except httpx.HTTPStatusError as e:
        logger.warning(
            f"Tavily HTTP error for query '{query}': {e.response.status_code}"
        )
        return SearchResult(
            success=False,
            query=query,
            error=f"HTTP {e.response.status_code}: {e.response.text[:200] if e.response.text else 'No response body'}",
        )
    except Exception as e:
        logger.warning(f"Tavily error for query '{query}': {e}")
        return SearchResult(success=False, query=query, error=str(e))


async def _search_ddg(query: str, num_results: int) -> SearchResult:
    """Search using DuckDuckGo HTML (no API key needed)."""
    try:
        encoded_query = httpx.URL("https://html.duckduckgo.com/html/")
        params: dict[str, str | int] = {"q": query, "b": num_results}

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(encoded_query, params=params)
            response.raise_for_status()
            html = response.text

        results = _parse_ddg_html(html, num_results)
        return SearchResult(
            success=True,
            query=query,
            results=results,
            sources=[r["url"] for r in results],
        )
    except httpx.HTTPStatusError as e:
        logger.warning(
            f"DuckDuckGo HTTP error for query '{query}': {e.response.status_code}"
        )
        return SearchResult(
            success=False,
            query=query,
            error=f"HTTP {e.response.status_code}",
        )
    except Exception as e:
        logger.warning(f"DuckDuckGo error for query '{query}': {e}")
        return SearchResult(success=False, query=query, error=str(e))


def _parse_ddg_html(html: str, num_results: int) -> list[dict[str, str]]:
    """Parse DuckDuckGo HTML results."""
    results: list[dict[str, str]] = []
    import re

    pattern = re.compile(
        r'<a rel="nofollow" class="result__a" href="([^"]+)">([^<]+)</a>.*?'
        r'<a class="result__snippet"[^>]*>([^<]*)',
        re.DOTALL,
    )

    for match in pattern.finditer(html):
        if len(results) >= num_results:
            break
        url = match.group(1)
        if url.startswith("//"):
            url = "https:" + url
        results.append(
            {
                "title": match.group(2).strip(),
                "url": url,
                "snippet": match.group(3).strip() if match.group(3) else "",
            }
        )

    return results


@tool(args_schema=WebSearchInput)
def web_searcher(query: str, num_results: int = 5) -> dict[str, Any]:
    """Search the web for information. Returns URLs and summaries.

    Uses Tavily API if TAVILY_API_KEY is set, otherwise falls back to DuckDuckGo.
    Raises SearchError if all backends fail.
    """
    emit_status(
        f'Searching for "{query[:60]}..."',
        trace_id=get_trace_id(),
        node_name="web_searcher",
        metadata={"kind": "search", "query": query, "num_results": num_results},
    )
    result = run_web_searcher(query=query, num_results=num_results)
    emit_status(
        f"Search complete with {len(result.get('results', []))} results",
        trace_id=get_trace_id(),
        node_name="web_searcher",
        metadata={"kind": "complete", "query": query},
    )
    return result


async def _search_with_fallback(query: str, num_results: int) -> SearchResult:
    """Run Tavily search with DuckDuckGo fallback, all in one coroutine."""
    if TAVILY_API_KEY:
        result = await _search_tavily(query, num_results)
        if not result.success:
            fallback = await _search_ddg(query, num_results)
            if not fallback.success:
                raise SearchError(
                    f"All search backends failed for query '{query}'",
                    errors=[e for e in [result.error, fallback.error] if e],
                )
            result = fallback
    else:
        result = await _search_ddg(query, num_results)
        if not result.success:
            raise SearchError(
                f"Search failed for query '{query}'",
                errors=[result.error] if result.error else [],
            )
    return result


def run_web_searcher(query: str, num_results: int = 5) -> dict[str, Any]:
    from artifactforge.tools.research.async_compat import run_async_safely

    result = run_async_safely(_search_with_fallback(query, num_results))

    return {
        "query": result.query,
        "results": result.results,
        "sources": result.sources,
    }


__all__ = ["run_web_searcher", "web_searcher"]

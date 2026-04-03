"""Exa AI search tool - semantic/similarity-based web search."""

import logging
import os
from typing import Any

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from artifactforge.observability.middleware import emit_status, get_trace_id

logger = logging.getLogger(__name__)

EXA_API_KEY = os.getenv("EXA_API_KEY")


class ExaSearchError(Exception):
    """Raised when Exa search fails."""

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or []


class ExaSearchResult(BaseModel):
    """Structured Exa search result."""

    success: bool = True
    query: str = ""
    results: list[dict[str, str]] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    error: str | None = None


class ExaSearchInput(BaseModel):
    """Input for Exa searcher."""

    query: str = Field(description="The search query")
    num_results: int = Field(default=10, description="Number of results")


class ExaSimilarInput(BaseModel):
    """Input for Exa similar content search."""

    url: str = Field(description="URL to find similar content to")
    num_results: int = Field(default=10, description="Number of similar results")


async def _search_exa_api(query: str, num_results: int = 10) -> ExaSearchResult:
    """Search using Exa API."""
    if not EXA_API_KEY:
        return ExaSearchResult(
            success=False,
            query=query,
            error="EXA_API_KEY not set",
        )

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "https://api.exa.ai/search",
                json={
                    "query": query,
                    "numResults": num_results,
                    "useAutoprompt": True,
                    "type": "neural",
                    "contents": {"text": True, "highlights": True},
                },
                headers={
                    "Authorization": f"Bearer {EXA_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()

        results_data = data.get("results", [])
        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("text", "")[:500] if r.get("text") else "",
                "score": r.get("score", 0),
            }
            for r in results_data
        ]

        return ExaSearchResult(
            success=True,
            query=query,
            results=results,
            sources=[r["url"] for r in results],
        )
    except httpx.HTTPStatusError as e:
        logger.warning(f"Exa HTTP error for query '{query}': {e.response.status_code}")
        return ExaSearchResult(
            success=False,
            query=query,
            error=f"HTTP {e.response.status_code}: {e.response.text[:200] if e.response.text else 'No response body'}",
        )
    except Exception as e:
        logger.warning(f"Exa error for query '{query}': {e}")
        return ExaSearchResult(success=False, query=query, error=str(e))


async def _find_similar_exa(url: str, num_results: int = 10) -> ExaSearchResult:
    """Find similar content using Exa API."""
    if not EXA_API_KEY:
        return ExaSearchResult(
            success=False,
            query=url,
            error="EXA_API_KEY not set",
        )

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "https://api.exa.ai/findSimilar",
                json={
                    "url": url,
                    "numResults": num_results,
                    "contents": {"text": True, "highlights": True},
                },
                headers={
                    "Authorization": f"Bearer {EXA_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()

        results_data = data.get("results", [])
        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("text", "")[:500] if r.get("text") else "",
                "score": r.get("score", 0),
            }
            for r in results_data
        ]

        return ExaSearchResult(
            success=True,
            query=f"similar to: {url}",
            results=results,
            sources=[r["url"] for r in results],
        )
    except httpx.HTTPStatusError as e:
        logger.warning(
            f"Exa similar search HTTP error for URL '{url}': {e.response.status_code}"
        )
        return ExaSearchResult(
            success=False,
            query=url,
            error=f"HTTP {e.response.status_code}",
        )
    except Exception as e:
        logger.warning(f"Exa similar search error for URL '{url}': {e}")
        return ExaSearchResult(success=False, query=url, error=str(e))


@tool(args_schema=ExaSearchInput)
def exa_searcher(query: str, num_results: int = 10) -> dict[str, Any]:
    """Search the web using Exa AI semantic search.

    Uses embeddings-based neural search for finding semantically relevant content.
    Best for discovering related articles, papers, and websites.
    Raises ExaSearchError if the search fails.
    """
    emit_status(
        f'Searching Exa for "{query[:60]}..."',
        trace_id=get_trace_id(),
        node_name="exa_searcher",
        metadata={"kind": "search", "query": query, "num_results": num_results},
    )
    result = run_exa_searcher(query=query, num_results=num_results)
    emit_status(
        f"Exa search complete with {len(result.get('results', []))} results",
        trace_id=get_trace_id(),
        node_name="exa_searcher",
        metadata={"kind": "complete", "query": query},
    )
    return result


@tool(args_schema=ExaSimilarInput)
def exa_similar_finder(url: str, num_results: int = 10) -> dict[str, Any]:
    """Find similar content to a given URL using Exa AI.

    Discovers content semantically similar to the provided URL.
    Useful for finding related articles, competitors, or reference materials.
    Raises ExaSearchError if the search fails.
    """
    emit_status(
        f'Finding similar content to "{url[:60]}..."',
        trace_id=get_trace_id(),
        node_name="exa_similar_finder",
        metadata={"kind": "similar", "url": url, "num_results": num_results},
    )
    result = run_exa_similar_finder(url=url, num_results=num_results)
    emit_status(
        f"Exa similar search complete with {len(result.get('results', []))} results",
        trace_id=get_trace_id(),
        node_name="exa_similar_finder",
        metadata={"kind": "complete", "url": url},
    )
    return result


def run_exa_searcher(query: str, num_results: int = 10) -> dict[str, Any]:
    """Run Exa search synchronously."""
    import asyncio

    result = asyncio.run(_search_exa_api(query, num_results))

    if not result.success:
        raise ExaSearchError(
            f"Exa search failed for query '{query}': {result.error}",
            errors=[result.error] if result.error else [],
        )

    return {
        "query": result.query,
        "results": result.results,
        "sources": result.sources,
    }


def run_exa_similar_finder(url: str, num_results: int = 10) -> dict[str, Any]:
    """Run Exa similar search synchronously."""
    import asyncio

    result = asyncio.run(_find_similar_exa(url, num_results))

    if not result.success:
        raise ExaSearchError(
            f"Exa similar search failed for URL '{url}': {result.error}",
            errors=[result.error] if result.error else [],
        )

    return {
        "query": result.query,
        "results": result.results,
        "sources": result.sources,
    }


__all__ = [
    "exa_searcher",
    "exa_similar_finder",
    "run_exa_searcher",
    "run_exa_similar_finder",
    "ExaSearchError",
]

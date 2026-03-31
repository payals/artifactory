"""Context7 search tool - library and framework documentation retrieval."""

import logging
import os
from typing import Any

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from artifactforge.observability.middleware import emit_status, get_trace_id

logger = logging.getLogger(__name__)

CONTEXT7_API_KEY = os.getenv("CONTEXT7_API_KEY")  # Optional for higher rate limits


class Context7SearchError(Exception):
    """Raised when Context7 search fails."""

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or []


class Context7SearchResult(BaseModel):
    """Structured Context7 search result."""

    success: bool = True
    query: str = ""
    library: str = ""
    results: list[dict[str, str]] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    error: str | None = None


class Context7SearchInput(BaseModel):
    """Input for Context7 documentation search."""

    library: str = Field(
        description="Library name (e.g., 'react', 'next.js', 'prisma')"
    )
    query: str = Field(description="The documentation query")
    num_results: int = Field(default=5, description="Number of results")


async def _resolve_library_id(library: str) -> str | None:
    """Resolve library name to Context7 library ID."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"https://context7.com/api/libraries/search?q={library}",
                headers=(
                    {"Authorization": f"Bearer {CONTEXT7_API_KEY}"}
                    if CONTEXT7_API_KEY
                    else {}
                ),
            )
            response.raise_for_status()
            data = response.json()

            libraries = data.get("libraries", [])
            if libraries:
                # Return exact match or first result
                for lib in libraries:
                    if lib.get("name", "").lower() == library.lower():
                        return lib.get("id")
                return libraries[0].get("id")
        return None
    except Exception as e:
        logger.warning(f"Failed to resolve library ID for '{library}': {e}")
        return None


async def _search_context7_api(
    library: str, query: str, num_results: int = 5
) -> Context7SearchResult:
    """Search using Context7 API."""

    # Resolve library ID
    library_id = await _resolve_library_id(library)
    if not library_id:
        return Context7SearchResult(
            success=False,
            library=library,
            query=query,
            error=f"Could not resolve library ID for '{library}'",
        )

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://context7.com/api/query",
                json={
                    "libraryId": library_id,
                    "query": query,
                    "numResults": num_results,
                },
                headers=(
                    {
                        "Authorization": f"Bearer {CONTEXT7_API_KEY}",
                        "Content-Type": "application/json",
                    }
                    if CONTEXT7_API_KEY
                    else {"Content-Type": "application/json"}
                ),
            )
            response.raise_for_status()
            data = response.json()

        results_data = data.get("results", [])
        results = [
            {
                "title": r.get("title", ""),
                "content": r.get("content", "")[:1000],
                "source": r.get("source", ""),
                "score": r.get("relevance_score", 0),
            }
            for r in results_data
        ]

        return Context7SearchResult(
            success=True,
            library=library,
            query=query,
            results=results,
            sources=[r.get("source", "") for r in results_data if r.get("source")],
        )
    except httpx.HTTPStatusError as e:
        logger.warning(
            f"Context7 HTTP error for library '{library}': {e.response.status_code}"
        )
        return Context7SearchResult(
            success=False,
            library=library,
            query=query,
            error=f"HTTP {e.response.status_code}: {e.response.text[:200] if e.response.text else 'No response body'}",
        )
    except Exception as e:
        logger.warning(f"Context7 error for library '{library}': {e}")
        return Context7SearchResult(
            success=False,
            library=library,
            query=query,
            error=str(e),
        )


@tool(args_schema=Context7SearchInput)
def context7_searcher(library: str, query: str, num_results: int = 5) -> dict[str, Any]:
    """Search library documentation using Context7.

    Retrieves up-to-date documentation and code examples for popular libraries
    and frameworks (React, Next.js, Prisma, etc.).
    Best for getting accurate API documentation and usage examples.
    Raises Context7SearchError if the search fails.
    """
    emit_status(
        f'Searching Context7 for "{library}" docs: {query[:60]}...',
        trace_id=get_trace_id(),
        node_name="context7_searcher",
        metadata={"kind": "docs", "library": library, "query": query},
    )
    result = run_context7_searcher(
        library=library, query=query, num_results=num_results
    )
    emit_status(
        f"Context7 search complete with {len(result.get('results', []))} results",
        trace_id=get_trace_id(),
        node_name="context7_searcher",
        metadata={"kind": "complete", "library": library, "query": query},
    )
    return result


def run_context7_searcher(
    library: str, query: str, num_results: int = 5
) -> dict[str, Any]:
    """Run Context7 search synchronously."""
    import asyncio

    result = asyncio.run(_search_context7_api(library, query, num_results))

    if not result.success:
        raise Context7SearchError(
            f"Context7 search failed for '{library}': {result.error}",
            errors=[result.error] if result.error else [],
        )

    return {
        "library": result.library,
        "query": result.query,
        "results": result.results,
        "sources": result.sources,
    }


__all__ = [
    "context7_searcher",
    "run_context7_searcher",
    "Context7SearchError",
]

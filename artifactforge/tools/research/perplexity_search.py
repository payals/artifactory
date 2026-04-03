"""Perplexity AI search tool - semantic web search with citations."""

import logging
import os
from typing import Any

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from artifactforge.observability.middleware import emit_status, get_trace_id

logger = logging.getLogger(__name__)

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")


class PerplexitySearchError(Exception):
    """Raised when Perplexity search fails."""

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or []


class PerplexitySearchResult(BaseModel):
    """Structured Perplexity search result."""

    success: bool = True
    query: str = ""
    answer: str = ""
    citations: list[dict[str, str]] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    error: str | None = None


class PerplexitySearchInput(BaseModel):
    """Input for Perplexity searcher."""

    query: str = Field(description="The search query")
    num_results: int = Field(default=10, description="Number of results")


async def _search_perplexity_api(
    query: str, num_results: int = 10
) -> PerplexitySearchResult:
    """Search using Perplexity API."""
    if not PERPLEXITY_API_KEY:
        return PerplexitySearchResult(
            success=False,
            query=query,
            error="PERPLEXITY_API_KEY not set",
        )

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "https://api.perplexity.ai/chat/completions",
                json={
                    "model": "sonar",
                    "messages": [
                        {
                            "role": "system",
                            "content": "Be precise and concise. Provide citations for facts.",
                        },
                        {"role": "user", "content": query},
                    ],
                    "max_tokens": 4096,
                    "temperature": 0.2,
                    "top_p": 0.9,
                    "return_images": False,
                    "return_related_questions": False,
                },
                headers={
                    "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()

        # Extract answer and citations
        message = data.get("choices", [{}])[0].get("message", {})
        answer = message.get("content", "")
        citations_raw = data.get("citations", [])

        # Format citations
        citations = [
            {
                "index": i + 1,
                "url": url,
                "title": "Source",  # Perplexity doesn't provide titles in response
            }
            for i, url in enumerate(citations_raw[:num_results])
        ]

        return PerplexitySearchResult(
            success=True,
            query=query,
            answer=answer,
            citations=citations,
            sources=citations_raw[:num_results],
        )
    except httpx.HTTPStatusError as e:
        logger.warning(
            f"Perplexity HTTP error for query '{query}': {e.response.status_code}"
        )
        return PerplexitySearchResult(
            success=False,
            query=query,
            error=f"HTTP {e.response.status_code}: {e.response.text[:200] if e.response.text else 'No response body'}",
        )
    except Exception as e:
        logger.warning(f"Perplexity error for query '{query}': {e}")
        return PerplexitySearchResult(success=False, query=query, error=str(e))


@tool(args_schema=PerplexitySearchInput)
def perplexity_searcher(query: str, num_results: int = 10) -> dict[str, Any]:
    """Search the web using Perplexity AI for answers with citations.

    Provides AI-generated answers based on web search with source citations.
    Best for getting quick, synthesized answers to questions.
    Raises SearchError if the search fails.
    """
    emit_status(
        f'Searching Perplexity for "{query[:60]}..."',
        trace_id=get_trace_id(),
        node_name="perplexity_searcher",
        metadata={"kind": "search", "query": query, "num_results": num_results},
    )
    result = run_perplexity_searcher(query=query, num_results=num_results)
    emit_status(
        f"Perplexity search complete with {len(result.get('citations', []))} citations",
        trace_id=get_trace_id(),
        node_name="perplexity_searcher",
        metadata={"kind": "complete", "query": query},
    )
    return result


def run_perplexity_searcher(query: str, num_results: int = 10) -> dict[str, Any]:
    """Run Perplexity search synchronously."""
    import asyncio

    result = asyncio.run(_search_perplexity_api(query, num_results))

    if not result.success:
        raise PerplexitySearchError(
            f"Perplexity search failed for query '{query}': {result.error}",
            errors=[result.error] if result.error else [],
        )

    return {
        "query": result.query,
        "answer": result.answer,
        "citations": result.citations,
        "sources": result.sources,
    }


__all__ = ["perplexity_searcher", "run_perplexity_searcher", "PerplexitySearchError"]

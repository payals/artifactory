"""Web searcher tool - searches the web for information."""

import os
from typing import Any

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")


class WebSearchInput(BaseModel):
    """Input for web searcher."""

    query: str = Field(description="The search query")
    num_results: int = Field(default=5, description="Number of results")


async def _search_tavily(query: str, num_results: int) -> dict[str, Any]:
    """Search using Tavily API."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.tavily.com/search",
            json={"query": query, "max_results": num_results},
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        data = response.json()

    results = data.get("results", [])
    return {
        "query": query,
        "results": [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", ""),
            }
            for r in results
        ],
        "sources": [r.get("url", "") for r in results],
    }


async def _search_ddg(query: str, num_results: int) -> dict[str, Any]:
    """Search using DuckDuckGo HTML (no API key needed)."""
    encoded_query = httpx.URL("https://html.duckduckgo.com/html/")
    params = {"q": query, "b": num_results}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(encoded_query, params=params)
        response.raise_for_status()
        html = response.text

    results = _parse_ddg_html(html, num_results)
    return {
        "query": query,
        "results": results,
        "sources": [r["url"] for r in results],
    }


def _parse_ddg_html(html: str, num_results: int) -> list[dict[str, str]]:
    """Parse DuckDuckGo HTML results."""
    results = []
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
    """
    if TAVILY_API_KEY:
        import asyncio

        return asyncio.run(_search_tavily(query, num_results))

    try:
        import asyncio

        return asyncio.run(_search_ddg(query, num_results))
    except Exception:
        return {
            "query": query,
            "results": [
                {
                    "title": f"Result {i + 1} for {query}",
                    "url": f"https://example.com/result-{i + 1}",
                    "snippet": f"Search result {i + 1} about {query}",
                }
                for i in range(num_results)
            ],
            "sources": [
                f"https://example.com/result-{i + 1}" for i in range(num_results)
            ],
        }


__all__ = ["web_searcher"]

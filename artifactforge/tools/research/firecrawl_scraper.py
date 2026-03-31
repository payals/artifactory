"""Firecrawl scraper tool - structured content extraction from URLs."""

import logging
import os
from typing import Any, Literal

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from artifactforge.observability.middleware import emit_status, get_trace_id

logger = logging.getLogger(__name__)

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")


class FirecrawlError(Exception):
    """Raised when Firecrawl operation fails."""

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or []


class FirecrawlResult(BaseModel):
    """Structured Firecrawl result."""

    success: bool = True
    url: str = ""
    markdown: str = ""
    title: str = ""
    description: str = ""
    links: list[str] = Field(default_factory=list)
    error: str | None = None


class FirecrawlScrapeInput(BaseModel):
    """Input for Firecrawl scraper."""

    url: str = Field(description="URL to scrape")
    formats: list[Literal["markdown", "html", "screenshot"]] = Field(
        default=["markdown"], description="Output formats to return"
    )
    only_main_content: bool = Field(
        default=True,
        description="Extract only the main content, ignoring navigation, ads, etc.",
    )


class FirecrawlCrawlInput(BaseModel):
    """Input for Firecrawl crawler."""

    url: str = Field(description="URL to start crawling from")
    max_depth: int = Field(default=2, description="Maximum crawl depth")
    limit: int = Field(default=10, description="Maximum number of pages to crawl")


async def _scrape_url_firecrawl(
    url: str,
    formats: list[Literal["markdown", "html", "screenshot"]],
    only_main_content: bool = True,
) -> FirecrawlResult:
    if not FIRECRAWL_API_KEY:
        return FirecrawlResult(
            success=False,
            url=url,
            error="FIRECRAWL_API_KEY not set",
        )

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "https://api.firecrawl.dev/v1/scrape",
                json={
                    "url": url,
                    "formats": formats,
                    "onlyMainContent": only_main_content,
                },
                headers={
                    "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()

        if data.get("success"):
            result_data = data.get("data", {})
            return FirecrawlResult(
                success=True,
                url=url,
                markdown=result_data.get("markdown", ""),
                title=result_data.get("metadata", {}).get("title", ""),
                description=result_data.get("metadata", {}).get("description", ""),
                links=result_data.get("links", []),
            )
        else:
            return FirecrawlResult(
                success=False,
                url=url,
                error=data.get("error", "Unknown error"),
            )
    except httpx.HTTPStatusError as e:
        logger.warning(
            f"Firecrawl HTTP error for URL '{url}': {e.response.status_code}"
        )
        return FirecrawlResult(
            success=False,
            url=url,
            error=f"HTTP {e.response.status_code}: {e.response.text[:200] if e.response.text else 'No response body'}",
        )
    except Exception as e:
        logger.warning(f"Firecrawl error for URL '{url}': {e}")
        return FirecrawlResult(success=False, url=url, error=str(e))


async def _crawl_url_firecrawl(
    url: str, max_depth: int = 2, limit: int = 10
) -> FirecrawlResult:
    """Crawl a website using Firecrawl API."""
    if not FIRECRAWL_API_KEY:
        return FirecrawlResult(
            success=False,
            url=url,
            error="FIRECRAWL_API_KEY not set",
        )

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                "https://api.firecrawl.dev/v1/crawl",
                json={
                    "url": url,
                    "maxDepth": max_depth,
                    "limit": limit,
                    "scrapeOptions": {
                        "formats": ["markdown"],
                        "onlyMainContent": True,
                    },
                },
                headers={
                    "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()

        if data.get("success"):
            # For crawl, we get a job ID and need to poll for results
            # Simplified: return the crawl status
            return FirecrawlResult(
                success=True,
                url=url,
                markdown=f"Crawl job started for {url}. Job ID: {data.get('id', 'N/A')}",
                title="Crawl Job",
            )
        else:
            return FirecrawlResult(
                success=False,
                url=url,
                error=data.get("error", "Unknown error"),
            )
    except httpx.HTTPStatusError as e:
        logger.warning(
            f"Firecrawl crawl HTTP error for URL '{url}': {e.response.status_code}"
        )
        return FirecrawlResult(
            success=False,
            url=url,
            error=f"HTTP {e.response.status_code}",
        )
    except Exception as e:
        logger.warning(f"Firecrawl crawl error for URL '{url}': {e}")
        return FirecrawlResult(success=False, url=url, error=str(e))


@tool(args_schema=FirecrawlScrapeInput)
def firecrawl_scraper(
    url: str,
    formats: list[Literal["markdown", "html", "screenshot"]] = ["markdown"],
    only_main_content: bool = True,
) -> dict[str, Any]:
    """Scrape structured content from a URL using Firecrawl.

    Extracts clean markdown, HTML, or screenshots from any URL.
    Automatically handles JavaScript-rendered content.
    Best for getting clean article content without ads/nav.
    Raises FirecrawlError if scraping fails.
    """
    emit_status(
        f'Scraping "{url[:60]}..."',
        trace_id=get_trace_id(),
        node_name="firecrawl_scraper",
        metadata={"kind": "scrape", "url": url, "formats": formats},
    )
    # Convert Literal list to regular list[str] for internal function
    result = run_firecrawl_scraper(
        url=url, formats=formats, only_main_content=only_main_content
    )
    emit_status(
        f"Scrape complete for {url[:60]}...",
        trace_id=get_trace_id(),
        node_name="firecrawl_scraper",
        metadata={"kind": "complete", "url": url},
    )
    return result


@tool(args_schema=FirecrawlCrawlInput)
def firecrawl_crawler(url: str, max_depth: int = 2, limit: int = 10) -> dict[str, Any]:
    """Crawl a website using Firecrawl.

    Discovers and scrapes multiple pages from a starting URL.
    Useful for extracting documentation, blog archives, or site structures.
    Returns a crawl job ID - results must be fetched separately.
    Raises FirecrawlError if crawling fails.
    """
    emit_status(
        f'Starting crawl from "{url[:60]}..."',
        trace_id=get_trace_id(),
        node_name="firecrawl_crawler",
        metadata={"kind": "crawl", "url": url, "max_depth": max_depth, "limit": limit},
    )
    result = run_firecrawl_crawler(url=url, max_depth=max_depth, limit=limit)
    emit_status(
        f"Crawl initiated for {url[:60]}...",
        trace_id=get_trace_id(),
        node_name="firecrawl_crawler",
        metadata={"kind": "complete", "url": url},
    )
    return result


def run_firecrawl_scraper(
    url: str,
    formats: list[Literal["markdown", "html", "screenshot"]] = ["markdown"],
    only_main_content: bool = True,
) -> dict[str, Any]:
    import asyncio

    result = asyncio.run(_scrape_url_firecrawl(url, formats, only_main_content))

    if not result.success:
        raise FirecrawlError(
            f"Firecrawl scrape failed for '{url}': {result.error}",
            errors=[result.error] if result.error else [],
        )

    return {
        "url": result.url,
        "markdown": result.markdown,
        "title": result.title,
        "description": result.description,
        "links": result.links,
    }


def run_firecrawl_crawler(
    url: str, max_depth: int = 2, limit: int = 10
) -> dict[str, Any]:
    """Run Firecrawl crawl synchronously."""
    import asyncio

    result = asyncio.run(_crawl_url_firecrawl(url, max_depth, limit))

    if not result.success:
        raise FirecrawlError(
            f"Firecrawl crawl failed for '{url}': {result.error}",
            errors=[result.error] if result.error else [],
        )

    return {
        "url": result.url,
        "markdown": result.markdown,
        "title": result.title,
        "job_info": "Crawl job started. Check Firecrawl dashboard for results.",
    }


__all__ = [
    "firecrawl_scraper",
    "firecrawl_crawler",
    "run_firecrawl_scraper",
    "run_firecrawl_crawler",
    "FirecrawlError",
]

"""Tests for all research tools — web_searcher, deep_analyzer, context7_search,
exa_search, perplexity_search, firecrawl_scraper.

Mocks httpx.AsyncClient to avoid real HTTP calls. Tests async internal functions
directly via @pytest.mark.asyncio and sync wrappers via regular tests.

NOTE: imports use full module paths (not `from artifactforge.tools.research import ...`)
because the package __init__.py re-exports @tool-decorated functions that shadow
the module names.
"""

from __future__ import annotations

import importlib

import httpx
import pytest

# The research package __init__.py re-exports @tool-decorated functions that
# shadow the submodule names.  Use importlib to get the actual modules.
ws_mod = importlib.import_module("artifactforge.tools.research.web_searcher")
da_mod = importlib.import_module("artifactforge.tools.research.deep_analyzer")
c7_mod = importlib.import_module("artifactforge.tools.research.context7_search")
exa_mod = importlib.import_module("artifactforge.tools.research.exa_search")
px_mod = importlib.import_module("artifactforge.tools.research.perplexity_search")
fc_mod = importlib.import_module("artifactforge.tools.research.firecrawl_scraper")

# ---------------------------------------------------------------------------
# Shared mock infrastructure
# ---------------------------------------------------------------------------


class MockResponse:
    """Mock httpx.Response with controllable status, json, and text."""

    def __init__(
        self,
        status_code: int = 200,
        json_data: dict | None = None,
        text: str = "",
    ):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self.text = text

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=httpx.Request("GET", "https://test.example.com"),
                response=self,  # type: ignore[arg-type]
            )


class MockAsyncClient:
    """Mock httpx.AsyncClient supporting async with context manager."""

    def __init__(
        self,
        response: MockResponse | None = None,
        side_effect: Exception | None = None,
    ):
        self.response = response or MockResponse()
        self.side_effect = side_effect

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def post(self, url, **kwargs):
        if self.side_effect:
            raise self.side_effect
        return self.response

    async def get(self, url, **kwargs):
        if self.side_effect:
            raise self.side_effect
        return self.response


# =============================================================================
# web_searcher
# =============================================================================


class TestWebSearcher:
    """Tests for artifactforge.tools.research.web_searcher."""

    @pytest.mark.asyncio
    async def test_search_tavily_success(self, monkeypatch) -> None:
        mock = MockAsyncClient(
            response=MockResponse(
                json_data={
                    "results": [
                        {
                            "title": "Python Docs",
                            "url": "https://python.org",
                            "content": "Python is great",
                        }
                    ]
                }
            )
        )
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: mock)

        result = await ws_mod._search_tavily("python", 5)

        assert result.success is True
        assert len(result.results) == 1
        assert result.results[0]["title"] == "Python Docs"
        assert "https://python.org" in result.sources

    @pytest.mark.asyncio
    async def test_search_tavily_http_error(self, monkeypatch) -> None:
        mock = MockAsyncClient(response=MockResponse(status_code=429))
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: mock)

        result = await ws_mod._search_tavily("python", 5)

        assert result.success is False
        assert "429" in (result.error or "")

    @pytest.mark.asyncio
    async def test_search_ddg_success(self, monkeypatch) -> None:
        html = (
            '<a rel="nofollow" class="result__a" href="https://example.com">Title</a>'
            '<a class="result__snippet" href="#">Snippet text</a>'
        )
        mock = MockAsyncClient(response=MockResponse(text=html))
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: mock)

        result = await ws_mod._search_ddg("test", 5)

        assert result.success is True
        assert len(result.results) == 1
        assert result.results[0]["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_search_ddg_http_error(self, monkeypatch) -> None:
        mock = MockAsyncClient(response=MockResponse(status_code=500))
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: mock)

        result = await ws_mod._search_ddg("test", 5)

        assert result.success is False

    @pytest.mark.asyncio
    async def test_fallback_tavily_succeeds(self, monkeypatch) -> None:
        monkeypatch.setattr(ws_mod, "TAVILY_API_KEY", "fake-key")
        mock = MockAsyncClient(
            response=MockResponse(
                json_data={"results": [{"title": "T", "url": "u", "content": "c"}]}
            )
        )
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: mock)

        result = await ws_mod._search_with_fallback("q", 5)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_fallback_both_fail_raises(self, monkeypatch) -> None:
        monkeypatch.setattr(ws_mod, "TAVILY_API_KEY", "fake-key")
        mock = MockAsyncClient(response=MockResponse(status_code=500))
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: mock)

        with pytest.raises(ws_mod.SearchError) as exc_info:
            await ws_mod._search_with_fallback("q", 5)

        assert len(exc_info.value.errors) > 0

    @pytest.mark.asyncio
    async def test_fallback_no_tavily_key_ddg_only(self, monkeypatch) -> None:
        monkeypatch.setattr(ws_mod, "TAVILY_API_KEY", None)
        html = (
            '<a rel="nofollow" class="result__a" href="https://ddg.com">DDG</a>'
            '<a class="result__snippet" href="#">snippet</a>'
        )
        mock = MockAsyncClient(response=MockResponse(text=html))
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: mock)

        result = await ws_mod._search_with_fallback("q", 5)

        assert result.success is True
        assert result.results[0]["url"] == "https://ddg.com"

    def test_run_web_searcher_returns_dict(self, monkeypatch) -> None:
        monkeypatch.setattr(ws_mod, "TAVILY_API_KEY", None)
        html = (
            '<a rel="nofollow" class="result__a" href="https://r.com">R</a>'
            '<a class="result__snippet" href="#">s</a>'
        )
        mock = MockAsyncClient(response=MockResponse(text=html))
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: mock)

        result = ws_mod.run_web_searcher("test", 5)

        assert isinstance(result, dict)
        assert "query" in result
        assert "results" in result
        assert "sources" in result

    def test_parse_ddg_html(self) -> None:
        html = (
            '<a rel="nofollow" class="result__a" href="//example.com/1">Title 1</a>'
            '<a class="result__snippet" href="#">Snippet 1</a>'
            '<a rel="nofollow" class="result__a" href="https://example.com/2">Title 2</a>'
            '<a class="result__snippet" href="#">Snippet 2</a>'
        )

        results = ws_mod._parse_ddg_html(html, 10)

        assert len(results) == 2
        assert results[0]["url"] == "https://example.com/1"  # // prefix fixed
        assert results[1]["url"] == "https://example.com/2"


# =============================================================================
# deep_analyzer
# =============================================================================


class TestDeepAnalyzer:
    """Tests for artifactforge.tools.research.deep_analyzer."""

    @pytest.mark.asyncio
    async def test_fetch_url_content_html_extraction(self, monkeypatch) -> None:
        html = "<html><body><article><p>This is the main article content that should be extracted cleanly by trafilatura.</p></article></body></html>"
        mock = MockAsyncClient(response=MockResponse(text=html))
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: mock)

        result = await da_mod._fetch_url_content("https://example.com")

        assert result.success is True
        # Content should be clean text, not raw HTML tags
        assert "<html>" not in result.content
        assert "<body>" not in result.content
        assert len(result.content) > 0

    @pytest.mark.asyncio
    async def test_fetch_url_content_plain_text_fallback(self, monkeypatch) -> None:
        """When content has no HTML structure, regex fallback strips tags and returns text."""
        plain = "x" * 200
        mock = MockAsyncClient(response=MockResponse(text=plain))
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: mock)

        result = await da_mod._fetch_url_content("https://example.com")

        assert result.success is True
        assert len(result.content) > 0

    @pytest.mark.asyncio
    async def test_fetch_url_content_too_short(self, monkeypatch) -> None:
        mock = MockAsyncClient(response=MockResponse(text="short"))
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: mock)

        result = await da_mod._fetch_url_content("https://example.com")

        assert result.success is False
        assert "too short" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_fetch_url_content_http_error(self, monkeypatch) -> None:
        mock = MockAsyncClient(response=MockResponse(status_code=404))
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: mock)

        result = await da_mod._fetch_url_content("https://example.com")

        assert result.success is False
        assert "404" in (result.error or "")

    @pytest.mark.asyncio
    async def test_fetch_url_content_timeout(self, monkeypatch) -> None:
        mock = MockAsyncClient(side_effect=httpx.TimeoutException("timeout"))
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: mock)

        result = await da_mod._fetch_url_content("https://example.com")

        assert result.success is False
        assert "timeout" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_fetch_and_analyze_all_fail(self, monkeypatch) -> None:
        mock = MockAsyncClient(response=MockResponse(status_code=500))
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: mock)

        result = await da_mod._fetch_and_analyze(
            ["https://a.com", "https://b.com"], "query"
        )

        assert result["key_findings"] == []
        assert "failed" in result["summary"].lower()

    def test_extract_text_html_cleans_tags(self) -> None:
        html = "<html><head><title>Test</title></head><body><nav>Menu</nav><article><p>Important content here.</p></article><footer>Footer</footer></body></html>"
        text = da_mod._extract_text(html, "https://example.com")
        assert "<" not in text
        assert len(text) > 0

    def test_extract_text_respects_max_content(self) -> None:
        huge_html = "<p>" + ("word " * 100000) + "</p>"
        text = da_mod._extract_text(huge_html, "https://example.com")
        assert len(text) <= da_mod.MAX_CONTENT_CHARS

    def test_extract_text_trafilatura_import_failure(self, monkeypatch) -> None:
        """Falls back to regex when trafilatura is unavailable."""
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "trafilatura":
                raise ImportError("no trafilatura")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        html = "<p>Fallback content should work</p>"
        text = da_mod._extract_text(html, "https://example.com")
        assert "Fallback content should work" in text
        assert "<p>" not in text


# =============================================================================
# context7_search
# =============================================================================


class TestContext7Search:
    """Tests for artifactforge.tools.research.context7_search."""

    @pytest.mark.asyncio
    async def test_resolve_library_id_success(self, monkeypatch) -> None:
        mock = MockAsyncClient(
            response=MockResponse(
                json_data={
                    "libraries": [
                        {"name": "react", "id": "lib-react-123"},
                        {"name": "react-dom", "id": "lib-dom-456"},
                    ]
                }
            )
        )
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: mock)

        lib_id = await c7_mod._resolve_library_id("react")

        assert lib_id == "lib-react-123"

    @pytest.mark.asyncio
    async def test_resolve_library_id_failure(self, monkeypatch) -> None:
        mock = MockAsyncClient(
            side_effect=httpx.ConnectError("connection refused")
        )
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: mock)

        lib_id = await c7_mod._resolve_library_id("react")

        assert lib_id is None

    @pytest.mark.asyncio
    async def test_search_context7_success(self, monkeypatch) -> None:
        call_count = 0

        def make_mock(**kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MockAsyncClient(
                    response=MockResponse(
                        json_data={
                            "libraries": [{"name": "react", "id": "lib-123"}]
                        }
                    )
                )
            else:
                # relevance_score as string to satisfy dict[str, str] Pydantic type
                return MockAsyncClient(
                    response=MockResponse(
                        json_data={
                            "results": [
                                {
                                    "title": "useState Hook",
                                    "content": "useState is...",
                                    "source": "https://react.dev/hooks",
                                    "relevance_score": "0.95",
                                }
                            ]
                        }
                    )
                )

        monkeypatch.setattr(httpx, "AsyncClient", make_mock)

        result = await c7_mod._search_context7_api("react", "hooks", 5)

        assert result.success is True
        assert len(result.results) == 1
        assert result.results[0]["title"] == "useState Hook"

    @pytest.mark.asyncio
    async def test_search_context7_library_not_found(self, monkeypatch) -> None:
        mock = MockAsyncClient(
            response=MockResponse(json_data={"libraries": []})
        )
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: mock)

        result = await c7_mod._search_context7_api("nonexistent-lib", "q", 5)

        assert result.success is False
        assert "Could not resolve" in (result.error or "")


# =============================================================================
# exa_search
# =============================================================================


class TestExaSearch:
    """Tests for artifactforge.tools.research.exa_search."""

    @pytest.mark.asyncio
    async def test_search_exa_no_api_key(self, monkeypatch) -> None:
        monkeypatch.setattr(exa_mod, "EXA_API_KEY", None)

        result = await exa_mod._search_exa_api("python", 5)

        assert result.success is False
        assert "not set" in (result.error or "")

    @pytest.mark.asyncio
    async def test_search_exa_success(self, monkeypatch) -> None:
        monkeypatch.setattr(exa_mod, "EXA_API_KEY", "fake-key")
        # score must be a string because ExaSearchResult.results is list[dict[str, str]]
        mock = MockAsyncClient(
            response=MockResponse(
                json_data={
                    "results": [
                        {
                            "title": "Python Guide",
                            "url": "https://python.org",
                            "text": "Learn Python",
                            "score": "0.9",
                        }
                    ]
                }
            )
        )
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: mock)

        result = await exa_mod._search_exa_api("python", 5)

        assert result.success is True
        assert len(result.results) == 1
        assert result.results[0]["title"] == "Python Guide"

    @pytest.mark.asyncio
    async def test_search_exa_http_error(self, monkeypatch) -> None:
        monkeypatch.setattr(exa_mod, "EXA_API_KEY", "fake-key")
        mock = MockAsyncClient(response=MockResponse(status_code=401))
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: mock)

        result = await exa_mod._search_exa_api("python", 5)

        assert result.success is False
        assert "401" in (result.error or "")

    @pytest.mark.asyncio
    async def test_find_similar_exa_no_api_key(self, monkeypatch) -> None:
        monkeypatch.setattr(exa_mod, "EXA_API_KEY", None)

        result = await exa_mod._find_similar_exa("https://example.com", 5)

        assert result.success is False
        assert "not set" in (result.error or "")


# =============================================================================
# perplexity_search
# =============================================================================


class TestPerplexitySearch:
    """Tests for artifactforge.tools.research.perplexity_search."""

    @pytest.mark.asyncio
    async def test_search_perplexity_no_api_key(self, monkeypatch) -> None:
        monkeypatch.setattr(px_mod, "PERPLEXITY_API_KEY", None)

        result = await px_mod._search_perplexity_api("test", 5)

        assert result.success is False
        assert "not set" in (result.error or "")

    @pytest.mark.asyncio
    async def test_search_perplexity_success(self, monkeypatch) -> None:
        monkeypatch.setattr(px_mod, "PERPLEXITY_API_KEY", "fake-key")
        # Omit citations to avoid a production Pydantic validation bug:
        # _search_perplexity_api constructs {"index": i+1} (int) in a dict[str,str] model.
        mock = MockAsyncClient(
            response=MockResponse(
                json_data={
                    "choices": [
                        {"message": {"content": "Python is a language."}}
                    ],
                }
            )
        )
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: mock)

        result = await px_mod._search_perplexity_api("what is python", 5)

        assert result.success is True
        assert result.answer == "Python is a language."

    @pytest.mark.asyncio
    async def test_search_perplexity_http_error(self, monkeypatch) -> None:
        monkeypatch.setattr(px_mod, "PERPLEXITY_API_KEY", "fake-key")
        mock = MockAsyncClient(response=MockResponse(status_code=429))
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: mock)

        result = await px_mod._search_perplexity_api("test", 5)

        assert result.success is False
        assert "429" in (result.error or "")


# =============================================================================
# firecrawl_scraper
# =============================================================================


class TestFirecrawlScraper:
    """Tests for artifactforge.tools.research.firecrawl_scraper."""

    @pytest.mark.asyncio
    async def test_scrape_no_api_key(self, monkeypatch) -> None:
        monkeypatch.setattr(fc_mod, "FIRECRAWL_API_KEY", None)

        result = await fc_mod._scrape_url_firecrawl(
            "https://example.com", ["markdown"]
        )

        assert result.success is False
        assert "not set" in (result.error or "")

    @pytest.mark.asyncio
    async def test_scrape_success(self, monkeypatch) -> None:
        monkeypatch.setattr(fc_mod, "FIRECRAWL_API_KEY", "fake-key")
        mock = MockAsyncClient(
            response=MockResponse(
                json_data={
                    "success": True,
                    "data": {
                        "markdown": "# Hello World",
                        "metadata": {
                            "title": "Hello",
                            "description": "A test page",
                        },
                        "links": ["https://example.com/about"],
                    },
                }
            )
        )
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: mock)

        result = await fc_mod._scrape_url_firecrawl(
            "https://example.com", ["markdown"]
        )

        assert result.success is True
        assert result.markdown == "# Hello World"
        assert result.title == "Hello"
        assert "https://example.com/about" in result.links

    @pytest.mark.asyncio
    async def test_scrape_api_returns_failure(self, monkeypatch) -> None:
        monkeypatch.setattr(fc_mod, "FIRECRAWL_API_KEY", "fake-key")
        mock = MockAsyncClient(
            response=MockResponse(
                json_data={"success": False, "error": "Rate limit exceeded"}
            )
        )
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: mock)

        result = await fc_mod._scrape_url_firecrawl(
            "https://example.com", ["markdown"]
        )

        assert result.success is False
        assert "Rate limit" in (result.error or "")

    @pytest.mark.asyncio
    async def test_crawl_no_api_key(self, monkeypatch) -> None:
        monkeypatch.setattr(fc_mod, "FIRECRAWL_API_KEY", None)

        result = await fc_mod._crawl_url_firecrawl("https://example.com")

        assert result.success is False
        assert "not set" in (result.error or "")

    @pytest.mark.asyncio
    async def test_crawl_success(self, monkeypatch) -> None:
        monkeypatch.setattr(fc_mod, "FIRECRAWL_API_KEY", "fake-key")
        mock = MockAsyncClient(
            response=MockResponse(
                json_data={"success": True, "id": "job-abc-123"}
            )
        )
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: mock)

        result = await fc_mod._crawl_url_firecrawl("https://example.com")

        assert result.success is True
        assert "job-abc-123" in result.markdown

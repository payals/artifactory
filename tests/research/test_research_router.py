"""Tests for ResearchRouter."""

import pytest

from artifactforge.tools.research.research_router import (
    ResearchRouter,
    ResearchStrategy,
    research_router,
)


class TestResearchStrategy:
    def test_get_num_results_shallow(self) -> None:
        strategy = ResearchStrategy(artifact_type="test", depth="shallow")
        assert strategy.get_num_results() == 3

    def test_get_num_results_medium(self) -> None:
        strategy = ResearchStrategy(artifact_type="test", depth="medium")
        assert strategy.get_num_results() == 5

    def test_get_num_results_deep(self) -> None:
        strategy = ResearchStrategy(artifact_type="test", depth="deep")
        assert strategy.get_num_results() == 10


class TestResearchRouter:
    def setup_method(self) -> None:
        self.router = ResearchRouter()

    def test_route_rfp_returns_deep_strategy(self) -> None:
        strategy = self.router.route("rfp", "cloud migration")
        assert strategy.depth == "deep"
        assert len(strategy.search_queries) >= 3
        assert "cloud migration" in strategy.search_queries[0]

    def test_route_blog_post_returns_medium_strategy(self) -> None:
        strategy = self.router.route("blog-post", "LLM agents")
        assert strategy.depth == "medium"
        assert len(strategy.search_queries) >= 3

    def test_route_simple_report_returns_adaptive_strategy(self) -> None:
        strategy = self.router.route(
            "simple_report",
            "Assess the feasibility of opening an Indian takeout restaurant in Chincoteague",
        )
        assert strategy.depth == "medium"
        assert len(strategy.search_queries) >= 4
        assert any("competitor" in q.lower() for q in strategy.search_queries)
        assert any(
            "regulation" in q.lower() or "license" in q.lower()
            for q in strategy.search_queries
        )

    def test_route_unknown_returns_default(self) -> None:
        strategy = self.router.route("unknown_type", "test query")
        assert strategy.depth == "medium"
        assert strategy.search_queries == ["test query"]

    def test_query_substitution_removes_placeholder(self) -> None:
        strategy = self.router.route("rfp", "AWS deployment")
        for q in strategy.search_queries:
            assert "{topic}" not in q

    def test_query_substitution_includes_user_description(self) -> None:
        user_desc = "Kubernetes orchestration"
        strategy = self.router.route("rfp", user_desc)
        for q in strategy.search_queries:
            assert user_desc in q or "Kubernetes" in q or "orchestration" in q.lower()

    def test_research_router_singleton(self) -> None:
        from artifactforge.tools.research.research_router import research_router

        assert isinstance(research_router, ResearchRouter)

"""Research router - intelligent strategy selection for research phase."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class ResearchStrategy(BaseModel):
    """Defines how to conduct research for an artifact type."""

    artifact_type: str
    depth: Literal["shallow", "medium", "deep"] = "medium"
    search_queries: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    parallel_searches: bool = True

    def get_num_results(self) -> int:
        """Get number of results based on depth."""
        return {"shallow": 3, "medium": 5, "deep": 10}[self.depth]


class ResearchRouter:
    """Routes to appropriate research strategy based on artifact type."""

    DEFAULT_STRATEGIES: dict[str, ResearchStrategy] = {
        "rfp": ResearchStrategy(
            artifact_type="rfp",
            depth="deep",
            search_queries=[
                "competitor analysis {topic}",
                "industry best practices {topic}",
                "{topic} requirements template",
            ],
            domains=["competitor-analysis", "requirements-gathering"],
        ),
        "blog-post": ResearchStrategy(
            artifact_type="blog-post",
            depth="medium",
            search_queries=[
                "{topic} latest trends 2026",
                "{topic} SEO keywords",
                "related topics to {topic}",
            ],
            domains=["seo", "trending-topics"],
        ),
        "simple_report": ResearchStrategy(
            artifact_type="simple_report",
            depth="medium",
            search_queries=[
                "{topic} overview",
                "{topic} key facts",
                "{topic} risks and opportunities",
            ],
            domains=[],
        ),
    }

    def route(
        self,
        artifact_type: str,
        user_description: str,
    ) -> ResearchStrategy:
        """Determine research strategy for artifact type."""
        # Get base strategy or create default
        base_strategy = self.DEFAULT_STRATEGIES.get(
            artifact_type,
            ResearchStrategy(
                artifact_type=artifact_type,
                depth="medium",
                search_queries=[user_description],
            ),
        )
        strategy = base_strategy.model_copy(deep=True)

        # Substitute {topic} placeholder with user description
        if "{topic}" in " ".join(strategy.search_queries):
            strategy.search_queries = [
                q.replace("{topic}", user_description) for q in strategy.search_queries
            ]

        # Enhance with specialized researcher if available
        specialized = self._get_specialized_researcher(artifact_type)
        if specialized:
            strategy = specialized.enhance_strategy(strategy, user_description)

        return strategy

    def _get_specialized_researcher(
        self, artifact_type: str
    ) -> "SpecializedResearcher | None":
        """Get specialized researcher for artifact type if available."""
        # Lazy import to avoid circular dependencies
        from artifactforge.tools.research.specialized import (
            get_researcher,
        )

        return get_researcher(artifact_type)


class SpecializedResearcher:
    """Base class for specialized research strategies."""

    artifact_type: str

    def enhance_strategy(
        self, strategy: ResearchStrategy, user_description: str
    ) -> ResearchStrategy:
        expanded_queries = self.expand_queries(
            user_description, strategy.search_queries
        )
        strategy.search_queries = list(dict.fromkeys(expanded_queries))
        return strategy

    def expand_queries(
        self, user_description: str, base_queries: list[str]
    ) -> list[str]:
        """Expand queries with specialized research."""
        return base_queries

    def analyze_results(
        self, sources: list[dict[str, Any]], query: str
    ) -> dict[str, Any]:
        """Analyze search results with specialized insights."""
        return {}


# Module-level singleton
research_router = ResearchRouter()

__all__ = [
    "ResearchStrategy",
    "ResearchRouter",
    "SpecializedResearcher",
    "research_router",
]

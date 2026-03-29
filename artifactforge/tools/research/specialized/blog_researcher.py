"""Blog post-specific research strategies."""

import re
from typing import Any

from artifactforge.tools.research.research_router import SpecializedResearcher


class BlogSpecializedResearcher(SpecializedResearcher):
    """Expands blog research with content marketing strategies."""

    artifact_type = "blog-post"

    def expand_queries(
        self, user_description: str, base_queries: list[str]
    ) -> list[str]:
        """Add blog-specific research queries."""
        expanded = list(base_queries)

        # Add trending analysis
        expanded.append(f"{user_description} trends 2026")
        expanded.append(f"popular {user_description} articles")

        # Add SEO research
        expanded.append(f"{user_description} SEO keywords")
        expanded.append(f"{user_description} search volume")

        # Add related topics
        expanded.append(f"{user_description} related topics")
        expanded.append(f"questions about {user_description}")

        return expanded

    def analyze_results(
        self, sources: list[dict[str, Any]], query: str
    ) -> dict[str, Any]:
        """Extract blog-specific insights from search results."""
        return {
            "trending_angles": self._extract_trending_angles(sources),
            "seo_keywords": self._extract_seo_keywords(sources, query),
            "related_topics": self._extract_related_topics(sources),
            "content_gaps": self._identify_content_gaps(sources, query),
        }

    def _extract_trending_angles(self, sources: list[dict[str, Any]]) -> list[str]:
        """Extract trending angles from top articles."""
        angles = []
        for source in sources[:5]:
            title = source.get("title", "")
            # Heuristic: titles with numbers, how-to, guide, tips
            if any(
                kw in title.lower() for kw in ["how", "guide", "tips", "best", "top"]
            ):
                angles.append(title[:100])
        return angles

    def _extract_seo_keywords(
        self, sources: list[dict[str, Any]], query: str
    ) -> list[str]:
        """Extract SEO keywords from search results."""
        keywords = set()

        for source in sources[:10]:
            title = source.get("title", "")
            snippet = source.get("snippet", "")

            # Extract phrases in parentheses (often keywords)
            parens = re.findall(r"\(([^)]+)\)", title + snippet)
            keywords.update(parens)

            # Extract quoted phrases
            quoted = re.findall(r'"([^"]+)"', title + snippet)
            keywords.update(quoted)

        return list(keywords)[:10]

    def _extract_related_topics(self, sources: list[dict[str, Any]]) -> list[str]:
        """Extract related topics for internal linking."""
        topics = []
        for source in sources[:5]:
            title = source.get("title", "")
            if title:
                topics.append(title[:80])
        return topics

    def _identify_content_gaps(
        self, sources: list[dict[str, Any]], query: str
    ) -> list[str]:
        """Identify content gaps that new article could fill."""
        gaps = []
        existing_titles = [s.get("title", "").lower() for s in sources]

        # Simple gap analysis based on common patterns
        common_patterns = ["beginner", "advanced", "comparison", "vs"]
        for pattern in common_patterns:
            if not any(pattern in t for t in existing_titles):
                gaps.append(f"No {pattern} guide found - potential gap")

        return gaps[:3]

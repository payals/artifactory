"""RFP-specific research strategies."""

import re
from typing import Any

from artifactforge.tools.research.research_router import SpecializedResearcher


class RFPSpecializedResearcher(SpecializedResearcher):
    """Expands RFP research with domain-specific queries."""

    artifact_type = "rfp"

    def expand_queries(
        self, user_description: str, base_queries: list[str]
    ) -> list[str]:
        """Add RFP-specific research queries."""
        expanded = list(base_queries)

        # Add competitor analysis
        expanded.append(f"competitor analysis {user_description} RFP vendors")
        expanded.append(f"successful RFP examples {user_description}")

        # Add requirements gathering
        expanded.append(f"RFP requirements checklist best practices {user_description}")
        expanded.append(f"industry standards for {user_description}")

        # Add compliance
        expanded.append(f"compliance requirements for {user_description}")

        return expanded

    def analyze_results(
        self, sources: list[dict[str, Any]], query: str
    ) -> dict[str, Any]:
        """Extract RFP-specific insights from search results."""
        return {
            "competitors": self._extract_competitors(sources),
            "requirements_patterns": self._extract_requirements_patterns(),
            "compliance_requirements": self._extract_compliance(sources),
            "best_practices": self._extract_best_practices(sources),
        }

    def _extract_competitors(self, sources: list[dict[str, Any]]) -> list[str]:
        """Identify named competitors in results."""
        competitor_keywords = ["vendor", "solution", "platform", "provider"]
        competitors = []
        for source in sources:
            title = source.get("title", "").lower()
            snippet = source.get("snippet", "").lower()
            # Simple heuristic - in production would use NER
            if any(kw in title for kw in competitor_keywords):
                competitors.append(source.get("title", "")[:100])
        return list(set(competitors))[:5]

    def _extract_requirements_patterns(self) -> list[str]:
        """Extract common requirements from RFP examples."""
        return [
            "Technical requirements section",
            "Pricing and payment terms",
            "Implementation timeline",
            "Support and maintenance",
            "Security and compliance",
        ]

    def _extract_compliance(self, sources: list[dict[str, Any]]) -> list[str]:
        """Extract compliance/regulatory requirements."""
        compliance_keywords = [
            "compliance",
            "regulation",
            "certification",
            "GDPR",
            "SOC",
            "ISO",
        ]
        compliance = []
        for source in sources:
            content = (
                source.get("title", "") + " " + source.get("snippet", "")
            ).lower()
            for kw in compliance_keywords:
                if kw.lower() in content:
                    compliance.append(kw)
        return list(set(compliance))

    def _extract_best_practices(
        self, sources: list[dict[str, Any]]
    ) -> list[dict[str, str]]:
        """Extract RFP best practices from sources."""
        return [
            {"source": s.get("url", ""), "practice": s.get("snippet", "")[:200]}
            for s in sources[:3]
        ]

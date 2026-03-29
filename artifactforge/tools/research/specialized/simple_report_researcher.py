from typing import Any

from artifactforge.schemas.simple_report import infer_report_kind
from artifactforge.tools.research.research_router import SpecializedResearcher


class SimpleReportSpecializedResearcher(SpecializedResearcher):
    artifact_type = "simple_report"

    def expand_queries(
        self, user_description: str, base_queries: list[str]
    ) -> list[str]:
        report_kind = infer_report_kind(user_description)
        expanded = list(base_queries)

        if report_kind == "market_feasibility":
            expanded.extend(
                [
                    f"{user_description} competitor landscape",
                    f"{user_description} regulation license permits",
                    f"{user_description} labor staffing seasonality",
                    f"{user_description} startup costs break-even economics",
                ]
            )
            return expanded

        if report_kind == "comparison":
            expanded.extend(
                [
                    f"{user_description} pricing differences",
                    f"{user_description} decision criteria",
                    f"{user_description} migration or implementation tradeoffs",
                ]
            )
            return expanded

        if report_kind == "implementation_plan":
            expanded.extend(
                [
                    f"{user_description} implementation milestones",
                    f"{user_description} dependencies and risks",
                    f"{user_description} rollout checklist",
                ]
            )
            return expanded

        expanded.extend(
            [
                f"{user_description} recommendations",
                f"{user_description} evidence gaps",
            ]
        )
        return expanded

    def analyze_results(
        self, sources: list[dict[str, Any]], query: str
    ) -> dict[str, Any]:
        return {
            "key_findings": [source.get("title", "") for source in sources[:5]],
            "research_gaps": [
                "Validate any claims that are repeated without a primary source."
            ],
        }


__all__ = ["SimpleReportSpecializedResearcher"]

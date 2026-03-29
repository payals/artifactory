from typing import Any


def infer_report_kind(user_description: str) -> str:
    description = user_description.lower()

    if any(
        keyword in description
        for keyword in ["feasibility", "viable", "market", "should i", "takeout"]
    ):
        return "market_feasibility"

    if any(
        keyword in description for keyword in ["compare", "comparison", "vs", "versus"]
    ):
        return "comparison"

    if any(
        keyword in description
        for keyword in ["implementation", "rollout", "migration", "plan"]
    ):
        return "implementation_plan"

    return "general"


def _section(title: str, prompt: str) -> dict[str, str]:
    return {"title": title, "prompt": prompt}


SECTION_LIBRARY: dict[str, list[dict[str, str]]] = {
    "market_feasibility": [
        _section("Executive Summary", "Summarize the opportunity in plain language."),
        _section("Recommendation", "State whether to proceed, wait, or avoid."),
        _section(
            "Local Demand and Market Conditions",
            "Explain customer demand, market size, and local fit.",
        ),
        _section(
            "Competition and Alternatives",
            "Describe direct competitors, substitutes, and positioning.",
        ),
        _section(
            "Operations and Seasonality",
            "Cover staffing, operating constraints, and seasonality.",
        ),
        _section(
            "Unit Economics",
            "Summarize startup costs, pricing, margins, and break-even factors.",
        ),
        _section("Risks and Unknowns", "List key risks and unresolved evidence gaps."),
        _section(
            "Sources and Evidence Gaps",
            "List supporting sources and call out missing validation data.",
        ),
    ],
    "comparison": [
        _section("Executive Summary", "State the decision context and bottom line."),
        _section("Recommendation", "Recommend the strongest option and why."),
        _section("Options Compared", "List the options in scope and their roles."),
        _section(
            "Comparison Criteria",
            "Define the criteria used to compare the options.",
        ),
        _section("Trade-Offs and Risks", "Explain important trade-offs and risks."),
        _section(
            "Sources and Evidence Gaps",
            "List supporting evidence and unresolved gaps.",
        ),
    ],
    "implementation_plan": [
        _section("Executive Summary", "Summarize the plan and desired outcome."),
        _section("Goal and Scope", "Define scope, success criteria, and constraints."),
        _section("Current State", "Describe the starting point and known issues."),
        _section("Proposed Approach", "Explain the recommended implementation path."),
        _section("Delivery Plan", "List milestones, dependencies, and sequencing."),
        _section("Risks and Dependencies", "Describe main risks and dependencies."),
        _section(
            "Sources and Open Questions",
            "List supporting evidence and unresolved questions.",
        ),
    ],
    "general": [
        _section("Executive Summary", "Summarize the topic and key point."),
        _section("Background", "Provide the needed context for the reader."),
        _section("Key Findings", "List the most important findings."),
        _section("Recommendations", "Describe the recommended next steps."),
        _section(
            "Sources and Evidence Gaps",
            "List supporting evidence and unresolved questions.",
        ),
    ],
}


def build_simple_report_schema(
    user_description: str, context: dict[str, Any] | None = None
) -> dict[str, Any]:
    report_kind = infer_report_kind(user_description)
    context = context or {}

    return {
        "type": "simple_report",
        "report_kind": report_kind,
        "title": user_description.strip(),
        "audience": "decision-maker",
        "tone": "specific, reader-focused, evidence-aware",
        "sections": SECTION_LIBRARY[report_kind],
        "review_focus": _build_review_focus(report_kind),
        "context_summary": context.get("summary", ""),
    }


def _build_review_focus(report_kind: str) -> list[str]:
    base_focus = ["completeness", "clarity", "accuracy", "readability", "specificity"]

    if report_kind in {"market_feasibility", "comparison"}:
        return [*base_focus, "decision_usefulness"]

    return base_focus


def _coerce_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]

    if value:
        return [str(value)]

    return []


def _section_points(
    title: str, context: dict[str, Any], schema: dict[str, Any]
) -> list[str]:
    summary = context.get("summary")
    findings = _coerce_list(context.get("key_findings"))
    gaps = _coerce_list(context.get("research_gaps") or context.get("missing_data"))
    report_kind = schema.get("report_kind", "general")

    if title == "Executive Summary":
        return findings[:2] or ([str(summary)] if summary else [schema["title"]])

    if title == "Recommendation":
        if report_kind == "market_feasibility":
            return [
                "Proceed only if local regulatory details and seasonal staffing can be validated.",
                "Use the strongest demand signals and evidence gaps to frame the go/no-go call.",
            ]
        if report_kind == "comparison":
            return [
                "Choose the option that best matches the stated criteria and trade-offs."
            ]
        return ["Turn the main findings into a direct next-step recommendation."]

    if title in {"Local Demand and Market Conditions", "Background", "Key Findings"}:
        return findings or (
            [str(summary)] if summary else ["Add topic-specific findings."]
        )

    if title == "Competition and Alternatives":
        return [
            "Document direct competitors, substitutes, and whitespace in the market.",
            "Note where the available evidence is strong versus assumed.",
        ]

    if title == "Operations and Seasonality":
        return [
            "Summarize staffing, capacity, and seasonal operating constraints.",
            "Call out the periods where demand or execution risk changes materially.",
        ]

    if title == "Unit Economics":
        return [
            "Estimate startup costs, pricing, contribution margin, and break-even drivers.",
            "Flag any missing economic inputs that prevent a confident decision.",
        ]

    if title == "Options Compared":
        return findings or ["List the options and their most relevant differences."]

    if title == "Comparison Criteria":
        return [
            "Define the criteria that matter most to the reader.",
            "Explain how each option performs against those criteria.",
        ]

    if title in {
        "Trade-Offs and Risks",
        "Risks and Unknowns",
        "Risks and Dependencies",
    }:
        return gaps or [
            "Capture the main risks, assumptions, and unresolved questions."
        ]

    if title in {"Sources and Evidence Gaps", "Sources and Open Questions"}:
        source_titles = [
            source.get("title", source.get("url", "Source"))
            for source in context.get("sources", [])
            if isinstance(source, dict)
        ]
        combined_sources = [str(item) for item in [*source_titles, *gaps] if item]
        return combined_sources or ["List sources and unresolved validation needs."]

    return findings or ([str(summary)] if summary else [schema["title"]])


def generate_simple_report(
    user_description: str,
    context: dict[str, Any],
    schema: dict[str, Any] | None = None,
) -> str:
    active_schema = schema or build_simple_report_schema(user_description, context)

    lines = [f"# {active_schema['title']}", ""]

    for section in active_schema["sections"]:
        lines.append(f"## {section['title']}")
        lines.append("")
        for point in _section_points(section["title"], context, active_schema):
            lines.append(f"- {point}")
        lines.append("")

    return "\n".join(lines).strip()


__all__ = [
    "build_simple_report_schema",
    "generate_simple_report",
    "infer_report_kind",
]

"""Output Strategist Agent - Designs optimal communication structure."""

import json
from typing import Any

from artifactforge.agents.llm_gateway import extract_json
from artifactforge.coordinator import artifacts as schemas
from artifactforge.coordinator.contracts import (
    OUTPUT_STRATEGIST_CONTRACT,
    agent_contract,
)


OUTPUT_STRATEGIST_SYSTEM = """You are the Output Strategist - an expert at communication design.

Your job is to design the optimal structure for the audience and output type.

## Structure Guidelines by Output Type

### REPORT
- Executive summary
- Key findings
- Evidence sections
- Analysis/framework
- Risks
- Recommendation
- Next steps

### BLOG
- Thesis statement
- Narrative setup
- Argument progression
- Examples
- Counterarguments
- Memorable close

### SLIDES
- Hook/problem
- Insight progression
- Contrast cases
- Recommendation
- Call to action

### DECISION MEMO
- Situation
- Options
- Analysis
- Recommendation
- Risks/gaps
- Decision requested

## Visual Elements
When the user's goal mentions charts, graphs, tables, figures, visuals, or data visualization
(or when the content contains numeric data, comparisons, or frameworks that benefit from
visual presentation), you MUST populate visual_elements with concrete specs.

Each visual element should be a dict with:
- "title": descriptive title (e.g. "Demographic Breakdown")
- "visual_type": one of "table", "bar_chart", "pie_chart", "line_chart", "flowchart", "comparison_matrix", "swot_grid", "timeline", "heatmap"
- "section_anchor": which section header this belongs under
- "data_description": what data to show
- "purpose": why this visual helps the reader

ALWAYS include visual_elements for reports, whitepapers, and decision memos.
For blogs and slides, include them when data or comparisons are involved.

## What NOT to Do
- Do NOT write content
- Do NOT ignore output type requirements
- Do NOT bury key insights
- Do NOT return empty visual_elements when the content has data, comparisons, or frameworks

## Section Data Requirements (CRITICAL)
For EACH section in the structure, specify what data and analytical frameworks it needs to be substantive.
This prevents downstream agents from writing vague prose when specific data is available.

"section_data_requirements": {
  "Section Name": {
    "required_data": ["list of specific data points this section needs"],
    "required_frameworks": ["analytical frameworks to apply, e.g. 'competitive_matrix', 'risk_table', 'scenario_model'"],
    "specificity": "guidance on precision level, e.g. 'Use exact figures with sources, not ranges'"
  }
}

Examples of good required_data entries:
- "population count with year" (not "demographics")
- "competitor names and count by category" (not "competitive landscape")
- "startup cost line items with dollar ranges" (not "financial analysis")
- "API latency benchmarks from published tests" (not "performance data")
- "relevant paper titles and key results" (not "academic research")

Infer the right frameworks for the topic. Common patterns:
- Business decisions: scenario_model, competitive_matrix, risk_severity_table
- Technical comparisons: benchmark_table, feature_matrix, architecture_diagram
- Policy analysis: stakeholder_matrix, impact_assessment, precedent_table
- Research surveys: taxonomy, gap_analysis, timeline_of_developments

## Scope Guidance (CRITICAL)
When scope_guidance is present in the brief:
- If min_items/max_items specify a count, design that many content sections for the core material
  (e.g., if max_items=10 and the user asked for "10 ways", the structure MUST have ~10 distinct sections covering each way/strategy/item)
- If breadth_preference is "broad", favor more sections with lighter depth over fewer deep sections
- If breadth_preference is "deep", fewer sections with more analysis per section
- NEVER produce fewer content sections than min_items when it is set
- The user's quantity request is a hard requirement, not a suggestion

## Output Format
Return JSON with structure, section_purposes, narrative_flow, visual_elements, key_takeaways, audience_guidance, section_data_requirements.
"""


@agent_contract(OUTPUT_STRATEGIST_CONTRACT)
def run_output_strategist(
    execution_brief: dict[str, Any],
    analytical_backbone: dict[str, Any],
    repair_context: dict[str, Any] | None = None,
    learnings_context: dict[str, Any] | None = None,
) -> schemas.ContentBlueprint:
    """Run output strategist to design communication structure.

    Args:
        execution_brief: Output from Intent Architect
        analytical_backbone: Output from Analyst

    Returns:
        ContentBlueprint with structure
    """
    prompt = _build_strategy_prompt(
        execution_brief, analytical_backbone, repair_context, learnings_context
    )
    result = _call_llm(system=OUTPUT_STRATEGIST_SYSTEM, prompt=prompt)

    try:
        parsed = json.loads(extract_json(result))
        return schemas.ContentBlueprint(
            structure=parsed.get("structure", []),
            section_purposes=parsed.get("section_purposes", {}),
            narrative_flow=parsed.get("narrative_flow", ""),
            visual_elements=parsed.get("visual_elements", []),
            key_takeaways=parsed.get("key_takeaways", []),
            audience_guidance=parsed.get("audience_guidance", []),
            section_data_requirements=parsed.get("section_data_requirements"),
        )
    except (json.JSONDecodeError, KeyError):
        return _create_default_blueprint(execution_brief)


def _build_strategy_prompt(
    brief: dict,
    analysis: dict | None,
    repair_context: dict[str, Any] | None,
    learnings_context: dict[str, Any] | None = None,
) -> str:
    brief_json = json.dumps(
        {
            "output_type": brief.get("output_type", "report"),
            "audience": brief.get("audience", "general"),
            "tone": brief.get("tone", "professional"),
            "user_goal": brief.get("user_goal", ""),
            "scope_guidance": brief.get("scope_guidance"),
        },
        indent=2,
    )

    try:
        if analysis is None or not isinstance(analysis, dict):
            analysis_summary = json.dumps(
                {
                    "key_findings": [],
                    "risks": [],
                    "recommendation_logic": [],
                },
                indent=2,
            )
        else:
            scope = brief.get("scope_guidance") or {}
            max_items = scope.get("max_items") or 10
            finding_limit = max(5, max_items)
            risk_limit = max(3, max_items // 2)
            analysis_summary = json.dumps(
                {
                    "key_findings": (analysis.get("key_findings") or [])[:finding_limit],
                    "risks": (analysis.get("risks") or [])[:risk_limit],
                    "recommendation_logic": (
                        analysis.get("recommendation_logic") or []
                    )[:risk_limit],
                },
                indent=2,
            )
    except (TypeError, KeyError) as e:
        analysis_summary = json.dumps(
            {
                "key_findings": [],
                "risks": [],
                "recommendation_logic": [],
            },
            indent=2,
        )

    repair_text = ""
    if repair_context:
        repair_text = "\n## Repair Context\n" + json.dumps(repair_context, indent=2)

    from artifactforge.agents.learnings_utils import build_learnings_section

    learnings_text = build_learnings_section(learnings_context)

    return f"""## Brief
{brief_json}

## Analysis Summary
{analysis_summary}
{repair_text}
{learnings_text}

Design the optimal structure. Return JSON."""


def _create_default_blueprint(brief: dict) -> schemas.ContentBlueprint:
    output_type = brief.get("output_type", "report")
    default_structures = {
        "report": [
            "Introduction",
            "Findings",
            "Analysis",
            "Recommendation",
            "Conclusion",
        ],
        "blog": ["Hook", "Body", "Conclusion"],
        "slides": ["Title", "Problem", "Solution", "Next Steps"],
    }
    return schemas.ContentBlueprint(
        structure=default_structures.get(output_type, ["Section 1", "Section 2"]),
        section_purposes={},
        narrative_flow="Standard flow",
        visual_elements=[],
        key_takeaways=[],
        audience_guidance=[],
        section_data_requirements=None,
    )


def _call_llm(system: str, prompt: str) -> str:
    from artifactforge.agents.llm_gateway import call_llm_sync

    return call_llm_sync(
        system_prompt=system, user_prompt=prompt, agent_name="output_strategist"
    )


__all__ = ["run_output_strategist", "OUTPUT_STRATEGIST_CONTRACT"]

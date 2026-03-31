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

## What NOT to Do
- Do NOT write content
- Do NOT ignore output type requirements
- Do NOT bury key insights
- Do NOT skip visual elements when helpful

## Output Format
Return JSON with structure (section headers), section_purposes, narrative_flow, visual_elements, key_takeaways, audience_guidance.
"""


@agent_contract(OUTPUT_STRATEGIST_CONTRACT)
def run_output_strategist(
    execution_brief: dict[str, Any],
    analytical_backbone: dict[str, Any],
    repair_context: dict[str, Any] | None = None,
) -> schemas.ContentBlueprint:
    """Run output strategist to design communication structure.

    Args:
        execution_brief: Output from Intent Architect
        analytical_backbone: Output from Analyst

    Returns:
        ContentBlueprint with structure
    """
    prompt = _build_strategy_prompt(
        execution_brief, analytical_backbone, repair_context
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
        )
    except (json.JSONDecodeError, KeyError):
        return _create_default_blueprint(execution_brief)


def _build_strategy_prompt(
    brief: dict,
    analysis: dict | None,
    repair_context: dict[str, Any] | None,
) -> str:
    brief_json = json.dumps(
        {
            "output_type": brief.get("output_type", "report"),
            "audience": brief.get("audience", "general"),
            "tone": brief.get("tone", "professional"),
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
            analysis_summary = json.dumps(
                {
                    "key_findings": (analysis.get("key_findings") or [])[:5],
                    "risks": (analysis.get("risks") or [])[:3],
                    "recommendation_logic": (
                        analysis.get("recommendation_logic") or []
                    )[:3],
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

    return f"""## Brief
{brief_json}

## Analysis Summary
{analysis_summary}
{repair_text}

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
    )


def _call_llm(system: str, prompt: str) -> str:
    from artifactforge.agents.llm_gateway import call_llm_sync

    return call_llm_sync(
        system_prompt=system, user_prompt=prompt, agent_name="output_strategist"
    )


__all__ = ["run_output_strategist", "OUTPUT_STRATEGIST_CONTRACT"]

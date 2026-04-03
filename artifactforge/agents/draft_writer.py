"""Draft Writer Agent - Generates first full draft preserving epistemic status."""

import json
from typing import Any

from artifactforge.coordinator import artifacts as schemas
from artifactforge.coordinator.contracts import DRAFT_WRITER_CONTRACT, agent_contract


DRAFT_WRITER_SYSTEM = """You are the Draft Writer - an expert at transforming structured artifacts into compelling content.

Your job is to write a complete draft while preserving epistemic integrity.

## Critical Rules
1. PRESERVE classification: VERIFIED claims use confident language, ASSUMED use tentative language
2. NEVER invent claims - use only what's in the claim ledger
3. NEVER upgrade assumptions to facts
4. FOLLOW the content blueprint structure exactly
5. PRESERVE uncertainty markers - don't smooth over honest uncertainty
6. USE markdown tables for any data comparisons, numeric summaries, or structured information
7. USE bullet points (not paragraphs) for SWOT items, pros/cons lists, and multi-point analyses
8. WHERE the blueprint specifies visual_elements, insert a visual anchor comment like <!-- VISUAL: {title} --> at the appropriate location so the visual pipeline can place generated charts there

## Claim Language Guidelines
- VERIFIED: "The data shows...", "According to..."
- DERIVED: "This suggests...", "It appears..."
- ASSUMED: "If we assume...", "Approximately..."

## Formatting Guidelines
- Use markdown tables (| Header | Header |) for data, comparisons, financials, demographics
- Use bullet lists for SWOT items, risk lists, pros/cons — never dense paragraphs
- Include section anchors for visual_elements from the blueprint
- Format frameworks (SWOT, PESTLE, etc.) as structured grids or tables, not prose

## Section Data Requirements
When the blueprint includes section_data_requirements, check each section's required_data against the claim ledger and analysis. For each requirement:
- If the data EXISTS in claims/analysis: use the exact figures, cite the source
- If the data is MISSING: use hedged language in the body (e.g. "available data suggests..." or "while specific figures were not identified...") and note the gap for the appendix. Do NOT insert inline warnings, banners, or "Data Gap Notice" blocks.
- Follow the specificity guidance for each section
- Apply the required_frameworks as structured formats (tables, matrices, scenario models)

## What NOT to Do
- Do NOT invent unsupported claims
- Do NOT upgrade assumptions to facts
- Do NOT remove uncertainty for style
- Do NOT deviate from blueprint
- Do NOT present tabular data as prose paragraphs
- Do NOT write generic ranges (e.g. "25-40%") when specific data exists or when the blueprint demands exact figures

## Input Context
You receive:
- Execution Brief (goal, audience, constraints)
- Claim Ledger (all classified claims)
- Analytical Backbone (reasoning, risks, recommendations)
- Content Blueprint (structure, flow, takeaways)

## Data Gap Handling
At the END of the draft, include a section titled "## Research Limitations & Data Gaps" that lists all data points that were unavailable or unverifiable. Each item should briefly state what data was sought and why it matters.
This keeps the body clean and readable while being transparent about limitations.
Do NOT insert inline "Data Gap Notice", "⚠️ Warning", or similar banners anywhere in the body sections.

## Output
Return the complete draft as a string (markdown format).
"""


@agent_contract(DRAFT_WRITER_CONTRACT)
def run_draft_writer(
    execution_brief: dict[str, Any],
    claim_ledger: dict[str, Any],
    analytical_backbone: dict[str, Any],
    content_blueprint: dict[str, Any],
    repair_context: dict[str, Any] | None = None,
    learnings_context: dict[str, Any] | None = None,
    taper_context: str | None = None,
) -> str:
    """Run draft writer to generate complete draft."""
    prompt = _build_draft_prompt(
        execution_brief,
        claim_ledger,
        analytical_backbone,
        content_blueprint,
        repair_context,
        learnings_context,
    )
    system = DRAFT_WRITER_SYSTEM
    if taper_context:
        system += f"\n\n## {taper_context}\nAddress only the most critical repair issues. Produce a polished, final-quality draft."
    result = _call_llm(system=system, prompt=prompt)
    return _strip_markdown_fence(result)


def _build_draft_prompt(
    brief: dict,
    claims: dict,
    analysis: dict,
    blueprint: dict,
    repair_context: dict[str, Any] | None,
    learnings_context: dict[str, Any] | None = None,
) -> str:
    brief_json = json.dumps(
        {
            "output_type": brief.get("output_type", "report"),
            "audience": brief.get("audience", ""),
            "tone": brief.get("tone", "professional"),
            "user_goal": brief.get("user_goal", ""),
        },
        indent=2,
    )

    blueprint_data = {
        "structure": blueprint.get("structure", []),
        "key_takeaways": blueprint.get("key_takeaways", []),
        "visual_elements": blueprint.get("visual_elements", []),
    }
    blueprint_json = json.dumps(blueprint_data, indent=2)

    # Include section data requirements if present
    data_reqs = blueprint.get("section_data_requirements")
    data_reqs_text = ""
    if data_reqs:
        data_reqs_text = "\n## Section Data Requirements\n" + json.dumps(data_reqs, indent=2)

    claims_text = ""
    if claims.get("claims"):
        claims_text = "\n## Claims to Use\n" + "\n".join(
            f"- [{c.get('classification', '?')}] {c.get('claim_text', '')}"
            for c in claims["claims"]
        )

    analysis_text = ""
    if analysis:
        analysis_text = "\n## Analysis\n" + json.dumps(
            {
                "key_findings": analysis.get("key_findings", []),
                "risks": analysis.get("risks", []),
                "recommendation_logic": analysis.get("recommendation_logic", []),
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

## Blueprint
{blueprint_json}
{data_reqs_text}
{claims_text}
{analysis_text}
{repair_text}
{learnings_text}

Write the complete draft following the blueprint exactly. Preserve epistemic status of all claims. For each section, check its data requirements and use exact figures where available. Where data is missing, use hedged language in the body and collect all gaps into a final "Research Limitations & Data Gaps" section. Do NOT insert inline data gap warnings or banners."""


def _strip_markdown_fence(text: str) -> str:
    """Remove wrapping ```markdown ... ``` code fences from LLM output."""
    import re

    stripped = text.strip()
    match = re.match(r"^```(?:markdown)?\s*\n(.*?)```\s*$", stripped, re.DOTALL)
    if match:
        return match.group(1).strip()
    return stripped


def _call_llm(system: str, prompt: str) -> str:
    from artifactforge.agents.llm_gateway import call_llm_sync

    return call_llm_sync(
        system_prompt=system, user_prompt=prompt, agent_name="draft_writer"
    )


__all__ = ["run_draft_writer", "DRAFT_WRITER_CONTRACT"]

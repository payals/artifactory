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

## Claim Language Guidelines
- VERIFIED: "The data shows...", "According to..."
- DERIVED: "This suggests...", "It appears..."
- ASSUMED: "If we assume...", "Approximately..."

## What NOT to Do
- Do NOT invent unsupported claims
- Do NOT upgrade assumptions to facts
- Do NOT remove uncertainty for style
- Do NOT deviate from blueprint

## Input Context
You receive:
- Execution Brief (goal, audience, constraints)
- Claim Ledger (all classified claims)
- Analytical Backbone (reasoning, risks, recommendations)
- Content Blueprint (structure, flow, takeaways)

## Output
Return the complete draft as a string (markdown format).
"""


@agent_contract(DRAFT_WRITER_CONTRACT)
def run_draft_writer(
    execution_brief: dict[str, Any],
    claim_ledger: dict[str, Any],
    analytical_backbone: dict[str, Any],
    content_blueprint: dict[str, Any],
) -> str:
    """Run draft writer to generate complete draft.

    Args:
        execution_brief: Output from Intent Architect
        claim_ledger: Classified claims from Evidence Ledger
        analytical_backbone: Output from Analyst
        content_blueprint: Structure from Output Strategist

    Returns:
        Draft content as string
    """
    prompt = _build_draft_prompt(
        execution_brief, claim_ledger, analytical_backbone, content_blueprint
    )
    result = _call_llm(system=DRAFT_WRITER_SYSTEM, prompt=prompt)
    return result.strip()


def _build_draft_prompt(
    brief: dict,
    claims: dict,
    analysis: dict,
    blueprint: dict,
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

    blueprint_json = json.dumps(
        {
            "structure": blueprint.get("structure", []),
            "key_takeaways": blueprint.get("key_takeaways", []),
        },
        indent=2,
    )

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

    return f"""## Brief
{brief_json}

## Blueprint
{blueprint_json}
{claims_text}
{analysis_text}

Write the complete draft following the blueprint exactly. Preserve epistemic status of all claims."""


def _call_llm(system: str, prompt: str) -> str:
    from artifactforge.agents.llm_gateway import call_llm_sync

    return call_llm_sync(
        system_prompt=system, user_prompt=prompt, agent_name="draft_writer"
    )


__all__ = ["run_draft_writer", "DRAFT_WRITER_CONTRACT"]

"""Analyst Agent - Converts evidence into second-order thinking."""

import json
from typing import Any

from artifactforge.agents.llm_gateway import extract_json
from artifactforge.coordinator import artifacts as schemas
from artifactforge.coordinator.contracts import ANALYST_CONTRACT, agent_contract


ANALYST_SYSTEM = """You are the Analyst - an expert at turning evidence into actionable intelligence.

Your job is to produce second-order thinking, NOT just summarize.

## Required Thinking
1. PRIMARY DRIVERS: What drives the outcome?
2. IMPLICATIONS: Second-order effects and consequences
3. RISKS: What could go wrong?
4. SENSITIVITIES: How does result change with assumptions?
5. COUNTERARGUMENTS: What would experts object to?
6. RECOMMENDATION LOGIC: Chain of reasoning for decisions
7. OPEN UNKNOWNS: What remains unresolved?

## What NOT to Do
- Do NOT merely summarize facts
- Do NOT skip risks and counterarguments
- Do NOT avoid sensitivity analysis
- Do NOT omit recommendation logic when decision required

## Decision Analysis
If decision_required is true, your recommendation_logic must include:
- Options considered
- Tradeoffs
- Recommended path with reasoning
- Conditions that would change recommendation

## Output Format
Return JSON with key_findings, primary_drivers, implications, risks, sensitivities, counterarguments, recommendation_logic, open_unknowns.
"""


@agent_contract(ANALYST_CONTRACT)
def run_analyst(
    execution_brief: dict[str, Any],
    claim_ledger: dict[str, Any],
    repair_context: dict[str, Any] | None = None,
) -> schemas.AnalyticalBackbone:
    """Run analyst to generate second-order thinking.

    Args:
        execution_brief: Output from Intent Architect
        claim_ledger: Classified claims from Evidence Ledger

    Returns:
        AnalyticalBackbone with reasoning
    """
    prompt = _build_analyst_prompt(execution_brief, claim_ledger, repair_context)
    result = _call_llm(system=ANALYST_SYSTEM, prompt=prompt)

    try:
        parsed = json.loads(extract_json(result))
        return schemas.AnalyticalBackbone(
            key_findings=parsed.get("key_findings", []),
            primary_drivers=parsed.get("primary_drivers", []),
            implications=parsed.get("implications", []),
            risks=parsed.get("risks", []),
            sensitivities=parsed.get("sensitivities", []),
            counterarguments=parsed.get("counterarguments", []),
            recommendation_logic=parsed.get("recommendation_logic", []),
            open_unknowns=parsed.get("open_unknowns", []),
        )
    except (json.JSONDecodeError, KeyError):
        return _create_default_analysis(execution_brief)


def _build_analyst_prompt(
    brief: dict,
    claims: dict,
    repair_context: dict[str, Any] | None,
) -> str:
    claims_summary = ""
    if claims.get("claims"):
        claims_text = "\n".join(
            f"- [{c.get('classification', '?')}] {c.get('claim_text', '')}"
            for c in claims["claims"][:20]
        )
        claims_summary = f"\n## Claim Ledger\n{claims_text}"

    brief_json = json.dumps(
        {
            "user_goal": brief.get("user_goal", ""),
            "decision_required": brief.get("decision_required", False),
            "rigor_level": brief.get("rigor_level", "MEDIUM"),
        },
        indent=2,
    )

    repair_text = ""
    if repair_context:
        repair_text = "\n## Repair Context\n" + json.dumps(repair_context, indent=2)

    return f"""## Execution Brief
{brief_json}
{claims_summary}
{repair_text}

Generate second-order analysis. Return JSON."""


def _create_default_analysis(brief: dict) -> schemas.AnalyticalBackbone:
    return schemas.AnalyticalBackbone(
        key_findings=["Analysis pending"],
        primary_drivers=[],
        implications=[],
        risks=[],
        sensitivities=[],
        counterarguments=[],
        recommendation_logic=["Recommendation pending"]
        if brief.get("decision_required")
        else [],
        open_unknowns=["Analysis not completed"],
    )


def _call_llm(system: str, prompt: str) -> str:
    from artifactforge.agents.llm_gateway import call_llm_sync

    return call_llm_sync(system_prompt=system, user_prompt=prompt, agent_name="analyst")


__all__ = ["run_analyst", "ANALYST_CONTRACT"]

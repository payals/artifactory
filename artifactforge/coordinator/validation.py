"""Agent Contract Validation System - Validates agent outputs against contract criteria.

Uses LLM to validate qualitative criteria defined in contracts.
"""

import json
from typing import Any, Dict, List

from artifactforge.coordinator.contracts import AgentContract, get_agent_contract
from artifactforge.agents.llm_gateway import call_llm_sync


VALIDATION_SYSTEM = """You are an Agent Contract Validator - you check if an agent's output meets its contract criteria.

Each agent has a contract with pass_fail_criteria - qualitative requirements for the output.
Your job is to evaluate whether the output meets these criteria.

## Validation Approach
1. Read each criteria statement from the contract
2. Examine the agent's output artifact
3. Determine if the output satisfies each criteria
4. Return validation results for each criteria

## Output Format
Return JSON with:
- agent_name: The agent being validated
- artifact_type: Type of artifact produced
- criteria_results: List of objects for each criteria with:
  - criteria: The criteria text
  - satisfied: boolean
  - reasoning: Why satisfied or not
  - severity: "HIGH" or "MEDIUM" (HIGH if critical failure)
- overall_passed: boolean (all criteria satisfied)
- notes: Any additional notes
"""


def validate_agent_output(
    agent_name: str, artifact: Dict[str, Any], artifact_type: str
) -> Dict[str, Any]:
    """Validate an agent's output against its contract criteria."""
    contract = get_agent_contract(agent_name)
    if not contract:
        return {
            "agent_name": agent_name,
            "artifact_type": artifact_type,
            "criteria_results": [],
            "overall_passed": False,
            "notes": f"No contract found for agent '{agent_name}'",
        }

    # Build validation prompt
    prompt = f"""## Agent Contract
Agent: {agent_name}
Mission: {contract.mission}

## Pass/Fail Criteria
{json.dumps(contract.pass_fail_criteria, indent=2)}

## Agent Output Artifact
Artifact Type: {artifact_type}
Artifact Content: {json.dumps(artifact, indent=2)}

Validate each criteria against the artifact. Return JSON as specified."""

    result = call_llm_sync(
        system_prompt=VALIDATION_SYSTEM,
        user_prompt=prompt,
        agent_name="contract_validator",
    )

    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {
            "agent_name": agent_name,
            "artifact_type": artifact_type,
            "criteria_results": [],
            "overall_passed": False,
            "notes": "Validation failed - could not parse result",
        }


def validate_all_agents(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate all agent outputs in the state against their contracts."""
    validation_results = []

    # Map artifacts to agent names
    artifact_to_agent = {
        "execution_brief": "intent_architect",
        "research_map": "research_lead",
        "claim_ledger": "evidence_ledger",
        "analytical_backbone": "analyst",
        "content_blueprint": "output_strategist",
        "red_team_review": "adversarial_reviewer",
        "verification_report": "verifier",
        "release_decision": "final_arbiter",
        "visual_specs": "visual_designer",
        "visual_reviews": "visual_reviewer",
        "generated_visuals": "visual_generator",
    }

    for artifact_key, agent_name in artifact_to_agent.items():
        artifact = state.get(artifact_key)
        if artifact:
            result = validate_agent_output(agent_name, artifact, artifact_key)
            validation_results.append(result)

    return validation_results


__all__ = [
    "validate_agent_output",
    "validate_all_agents",
]

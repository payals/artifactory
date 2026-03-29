"""Agent Contract System - Defines agent responsibilities and constraints."""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from artifactforge.coordinator import artifacts as artifact_schemas


# Registry of all agents
AGENT_REGISTRY: dict[str, "AgentContract"] = {}


@dataclass
class AgentContract:
    """Contract defining agent behavior and constraints."""

    name: str
    mission: str
    inputs: list[str]  # Required input artifacts
    required_output_schema: type  # Schema class for output
    forbidden_behaviors: list[str]
    pass_fail_criteria: list[str]
    max_retries: int = 2

    # Runtime
    execute: Optional[Callable] = field(default=None, repr=False)


def agent_contract(contract: AgentContract):
    """Decorator to register an agent with its contract.

    Usage:
        @agent_contract(AgentContract(
            name="intent_architect",
            mission="...",
            inputs=["user_prompt"],
            required_output_schema=artifact_schemas.ExecutionBrief,
            forbidden_behaviors=["Do not research"],
            pass_fail_criteria=["Task clearly framed"]
        ))
        def run_intent_architect(...) -> artifact_schemas.ExecutionBrief:
            ...
    """
    AGENT_REGISTRY[contract.name] = contract

    def decorator(func: Callable) -> Callable:
        contract.execute = func
        return func

    return decorator


def get_agent_contract(name: str) -> Optional[AgentContract]:
    """Get agent contract by name."""
    return AGENT_REGISTRY.get(name)


def list_agents() -> list[str]:
    """List all registered agent names."""
    return list(AGENT_REGISTRY.keys())


# =============================================================================
# Predefined Contracts (for reference, implemented in agents/)
# =============================================================================

INTENT_ARCHITECT_CONTRACT = AgentContract(
    name="intent_architect",
    mission="Convert user request into precise execution brief with clear success criteria and inferred missing dimensions.",
    inputs=["user_prompt", "conversation_context"],
    required_output_schema=artifact_schemas.ExecutionBrief,
    forbidden_behaviors=[
        "Do not research",
        "Do not draft final prose",
        "Do not leave success criteria vague",
        "Do not assume output type without justification",
    ],
    pass_fail_criteria=[
        "Task is clearly framed",
        "Success criteria are actionable",
        "Likely missing dimensions are surfaced",
        "Output type is justified",
    ],
)

RESEARCH_LEAD_CONTRACT = AgentContract(
    name="research_lead",
    mission="Map information terrain and gather relevant material.",
    inputs=["execution_brief"],
    required_output_schema=artifact_schemas.ResearchMap,
    forbidden_behaviors=[
        "Do not analyze or draw conclusions",
        "Do not write content",
        "Do not limit to obvious sources",
        "Do not skip conflicting views",
    ],
    pass_fail_criteria=[
        "Source diversity achieved",
        "Key dimensions identified",
        "Data gaps surfaced",
        "Competing views noted",
    ],
)

EVIDENCE_LEDGER_CONTRACT = AgentContract(
    name="evidence_ledger",
    mission="Separate facts from inference from assumption with explicit epistemic classification.",
    inputs=["research_map"],
    required_output_schema=artifact_schemas.ClaimLedger,
    forbidden_behaviors=[
        "Do not merge assumptions into verified claims",
        "Do not create broad uncheckable claims",
        "Do not omit confidence or dependency structure",
        "Do not assign VERIFIED without source refs",
        "Do not leave claims unclassified",
    ],
    pass_fail_criteria=[
        "All meaningful claims are classified",
        "High-impact claims are traceable",
        "Assumptions are explicit",
        "Dependency structure is clear",
    ],
)

ANALYST_CONTRACT = AgentContract(
    name="analyst",
    mission="Convert evidence into actual thinking with second-order analysis.",
    inputs=["execution_brief", "claim_ledger"],
    required_output_schema=artifact_schemas.AnalyticalBackbone,
    forbidden_behaviors=[
        "Do not merely summarize",
        "Do not skip risks and counterarguments",
        "Do not avoid sensitivity analysis",
        "Do not omit recommendation logic when decision required",
    ],
    pass_fail_criteria=[
        "Second-order thinking present",
        "Risks and sensitivities identified",
        "Recommendation logic exists if needed",
        "Counterarguments addressed",
    ],
)

OUTPUT_STRATEGIST_CONTRACT = AgentContract(
    name="output_strategist",
    mission="Design optimal communication structure for the audience and output type.",
    inputs=["execution_brief", "analytical_backbone"],
    required_output_schema=artifact_schemas.ContentBlueprint,
    forbidden_behaviors=[
        "Do not write the content",
        "Do not ignore output type requirements",
        "Do not bury key insights",
        "Do not skip visual elements when helpful",
    ],
    pass_fail_criteria=[
        "Structure matches output type",
        "Narrative flow is clear",
        "Key takeaways are identifiable",
        "Visual strategy is appropriate",
    ],
)

DRAFT_WRITER_CONTRACT = AgentContract(
    name="draft_writer",
    mission="Generate first full draft preserving epistemic status of all claims.",
    inputs=[
        "execution_brief",
        "claim_ledger",
        "analytical_backbone",
        "content_blueprint",
    ],
    required_output_schema=str,  # Draft content
    forbidden_behaviors=[
        "Do not invent unsupported claims",
        "Do not upgrade assumptions to facts",
        "Do not remove uncertainty for style",
        "Do not deviate from blueprint",
    ],
    pass_fail_criteria=[
        "Blueprint followed",
        "Claim epistemic status preserved",
        "No new unsupported claims introduced",
        "Uncertainty appropriately conveyed",
    ],
)

ADVERSARIAL_REVIEWER_CONTRACT = AgentContract(
    name="adversarial_reviewer",
    mission="Try to break the draft by identifying weak points and fragile reasoning.",
    inputs=["draft_v1", "claim_ledger", "execution_brief"],
    required_output_schema=artifact_schemas.RedTeamReview,
    forbidden_behaviors=[
        "Do not give generic feedback",
        "Do not ignore fragile assumptions",
        "Do not avoid critical flaws",
        "Do not skip severity differentiation",
    ],
    pass_fail_criteria=[
        "Major flaws identified",
        "Severity properly differentiated",
        "Specific fixes suggested",
        "Weak assumptions challenged",
    ],
)

VERIFIER_CONTRACT = AgentContract(
    name="verifier",
    mission="Ensure support, traceability, and consistency for all claims.",
    inputs=["draft_v1", "claim_ledger"],
    required_output_schema=artifact_schemas.VerificationReport,
    forbidden_behaviors=[
        "Do not miss unsupported claims",
        "Do not ignore numerical inconsistencies",
        "Do not approve overconfident language",
        "Do not skip citation verification",
    ],
    pass_fail_criteria=[
        "All claims verified",
        "No contradictions remain",
        "Language appropriately cautious",
        "Numerical consistency confirmed",
    ],
)

POLISHER_CONTRACT = AgentContract(
    name="polisher",
    mission="Improve readability and presentation without changing substance.",
    inputs=["draft_v1", "output_type"],
    required_output_schema=str,  # Polished content
    forbidden_behaviors=[
        "Do not change meaning of claims",
        "Do not remove uncertainty markers",
        "Do not hide unresolved issues",
        "Do not alter conclusions",
    ],
    pass_fail_criteria=[
        "Readability improved",
        "Substance preserved",
        "Format matches medium",
        "Uncertainty markers retained",
    ],
)

FINAL_ARBITER_CONTRACT = AgentContract(
    name="final_arbiter",
    mission="Decide whether output is ready to ship as the final quality gate.",
    inputs=[
        "execution_brief",
        "draft_v1",
        "red_team_review",
        "verification_report",
        "all_artifacts",
    ],
    required_output_schema=artifact_schemas.ReleaseDecision,
    forbidden_behaviors=[
        "Do not approve with unresolved critical issues",
        "Do not ignore known gaps",
        "Do not treat polish as substitute for rigor",
        "Do not skip recommendation check when required",
    ],
    pass_fail_criteria=[
        "Core question answered",
        "Critical issues resolved",
        "Recommendation present if needed",
        "Known gaps disclosed",
    ],
)


__all__ = [
    "AgentContract",
    "agent_contract",
    "get_agent_contract",
    "list_agents",
    "AGENT_REGISTRY",
]

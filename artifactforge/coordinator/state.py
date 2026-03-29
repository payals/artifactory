"""LangGraph state definitions."""

from typing import Any, Literal, Optional

from typing_extensions import TypedDict

from artifactforge.coordinator import artifacts as mcrs_artifacts


class GraphState(TypedDict):
    """Main graph state - legacy simple pipeline."""

    # Identification
    artifact_id: Optional[str]
    artifact_type: str
    user_description: str

    # Schema
    schema: Optional[dict]

    # Research Phase
    research_output: Optional[dict]
    research_sources: Optional[list]

    # Generation Phase
    artifact_draft: Optional[str]
    generation_metadata: Optional[dict]

    # Review Phase
    review_results: Optional[list]

    # Verification
    verification_status: Literal["pending", "passed", "failed"]
    verification_errors: Optional[list]

    # User Interaction
    user_questions: Optional[list]
    user_answers: Optional[dict]

    # Errors
    errors: Optional[list]

    # Metadata
    num_retries: int


class MCRSState(TypedDict):
    """MCRS multi-agent pipeline state with full epistemic tracking."""

    # =========================================================================
    # Input
    # =========================================================================
    user_prompt: str
    conversation_context: Optional[list[dict]]
    output_constraints: Optional[dict]

    # =========================================================================
    # Phase 1: Intent
    # =========================================================================
    execution_brief: Optional[mcrs_artifacts.ExecutionBrief]

    # =========================================================================
    # Phase 2: Research
    # =========================================================================
    research_map: Optional[mcrs_artifacts.ResearchMap]

    # =========================================================================
    # Phase 3: Evidence (CORE - epistemic classification)
    # =========================================================================
    claim_ledger: Optional[mcrs_artifacts.ClaimLedger]

    # =========================================================================
    # Phase 4: Analysis
    # =========================================================================
    analytical_backbone: Optional[mcrs_artifacts.AnalyticalBackbone]

    # =========================================================================
    # Phase 5: Strategy
    # =========================================================================
    content_blueprint: Optional[mcrs_artifacts.ContentBlueprint]

    # =========================================================================
    # Phase 6: Draft
    # =========================================================================
    draft_v1: Optional[str]
    draft_version: int

    # =========================================================================
    # Phase 7: Review
    # =========================================================================
    red_team_review: Optional[mcrs_artifacts.RedTeamReview]

    # =========================================================================
    # Phase 8: Verification
    # =========================================================================
    verification_report: Optional[mcrs_artifacts.VerificationReport]

    # =========================================================================
    # Phase 9: Polish
    # =========================================================================
    polished_draft: Optional[str]

    # =========================================================================
    # Phase 10: Release
    # =========================================================================
    release_decision: Optional[mcrs_artifacts.ReleaseDecision]

    # =========================================================================
    # Revision Tracking (prevents infinite loops)
    # =========================================================================
    revision_history: list[dict]
    current_stage: str
    retry_count: int

    # =========================================================================
    # Errors & Metadata
    # =========================================================================
    errors: list[str]
    stage_timing: dict[str, float]  # stage -> elapsed seconds


# Backward compatibility
__all__ = ["GraphState", "MCRSState"]

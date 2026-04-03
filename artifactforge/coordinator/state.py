"""LangGraph state definitions."""

from typing import Any, Literal, Optional

from typing_extensions import TypedDict

from artifactforge.coordinator import artifacts as mcrs_artifacts
from artifactforge.coordinator.artifacts import (
    VisualSpec,
    VisualReview,
    VisualGeneration,
)


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
    intent_mode: Literal["auto", "interactive"]
    answers_collected: dict[str, str]

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
    # Revision Tracking (adaptive — quality-driven loop control)
    # =========================================================================
    revision_history: list[dict]
    revision_quality_history: list[dict]  # Quality snapshots per revision for adaptive control
    current_stage: str  # Set by @trace_node decorator; read by _repair_context_for_node

    # =========================================================================
    # Errors & Metadata
    # =========================================================================
    errors: list[str]
    stage_timing: dict[str, float]

    # =========================================================================
    # Observability & Metrics
    # =========================================================================
    tokens_used: dict[str, int]
    costs: dict[str, float]
    stage_metadata: dict[str, dict]
    trace_id: Optional[str]
    artifact_id: Optional[str]  # DB artifact row ID, set by persistence adapter
    learnings_context: Optional[dict[str, Any]]  # Injected from prior runs
    applied_learning_ids: list[str]  # IDs of learnings injected this run (for outcome tracking)
    repair_context: Optional[dict[str, Any]]

    # =========================================================================
    # Time Budget (optional — None means unlimited)
    # =========================================================================
    time_budget_seconds: Optional[int]
    pipeline_start_time: Optional[float]

    # =========================================================================
    # Resume support (ephemeral — never persisted to disk)
    # =========================================================================
    _resumed_nodes: Optional[set[str]]  # Output keys loaded from disk; consumed on skip

    # =========================================================================
    # Phase 11: Visual Design
    # =========================================================================
    visual_specs: list[VisualSpec]
    visual_reviews: list[VisualReview]
    generated_visuals: list[VisualGeneration]
    final_with_visuals: Optional[str]


# Backward compatibility
__all__ = ["GraphState", "MCRSState"]

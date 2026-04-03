"""MCRS Artifact Schemas - Structured data definitions for multi-agent pipeline."""

from typing import Literal, Optional, TypedDict


# =============================================================================
# Phase 1: Intent
# =============================================================================


class ExecutionBrief(TypedDict):
    """Output from Intent Architect - defines execution parameters."""

    user_goal: str
    output_type: str  # report, blog, slides, memo, decision_doc, technical_writeup
    audience: str
    tone: str  # formal, conversational, technical, persuasive
    must_answer_questions: list[str]
    constraints: list[str]
    success_criteria: list[str]
    likely_missing_dimensions: list[str]
    decision_required: bool
    rigor_level: Literal["LOW", "MEDIUM", "HIGH"]
    persuasion_level: Literal["LOW", "MEDIUM", "HIGH"]
    open_questions_to_resolve: list[str]
    scope_guidance: Optional[dict]  # {"min_items": N, "max_items": N, "breadth_preference": "broad"|"deep"|"balanced"}
    intent_mode: Literal["auto", "interactive"]
    answers_collected: dict[str, str]


# =============================================================================
# Phase 2: Research
# =============================================================================


class ResearchQuery(TypedDict):
    """A single typed research query within a research plan."""

    question: str  # What we need to find out
    search_query: str  # The actual search string to use
    category: str  # LLM-inferred: e.g. "demographic", "competitive", "technical", "regulatory", "academic", etc.
    priority: Literal["HIGH", "MEDIUM", "LOW"]
    why_needed: str  # How this connects to the user's goal


class ResearchPlan(TypedDict):
    """LLM-generated research plan — typed queries grouped by category."""

    categories: list[str]  # Unique category names inferred from the topic
    queries: list[ResearchQuery]
    research_depth: Literal["shallow", "medium", "deep"]
    domain_context: str  # Brief description of the domain for downstream agents


class ResearchSource(TypedDict):
    """Individual source in research map."""

    source_id: str
    title: str
    url: Optional[str]
    source_type: Literal[
        "official", "news", "research", "reference", "internal", "other"
    ]
    reliability: Literal["HIGH", "MEDIUM", "LOW"]
    notes: str
    publish_date: Optional[str]


class ResearchMap(TypedDict):
    """Output from Research Lead - gathered information terrain."""

    sources: list[ResearchSource]
    facts: list[str]  # Raw factual statements extracted
    key_dimensions: list[str]  # Critical aspects to cover
    competing_views: list[str]  # Conflicting perspectives
    data_gaps: list[str]  # Known missing information
    followup_questions: list[str]
    research_plan: Optional[ResearchPlan]  # The plan that drove the research


# =============================================================================
# Phase 3: Evidence (CORE)
# =============================================================================


class Claim(TypedDict):
    """Single claim with epistemic classification."""

    claim_id: str  # e.g., "C001"
    claim_text: str
    classification: Literal["VERIFIED", "DERIVED", "ASSUMED"]
    source_refs: list[str]  # source_ids
    confidence: float  # 0.0-1.0
    importance: Literal["HIGH", "MEDIUM", "LOW"]
    dependent_on: list[str]  # claim_ids this depends on
    notes: str  # Reasoning for classification


class ClaimLedger(TypedDict):
    """Output from Evidence Ledger - epistemically classified claims."""

    claims: list[Claim]
    summary: str  # High-level summary of epistemic status


# =============================================================================
# Phase 4: Analysis
# =============================================================================


class AnalyticalBackbone(TypedDict):
    """Output from Analyst - second-order reasoning."""

    key_findings: list[str]
    primary_drivers: list[str]  # What drives the outcome
    implications: list[str]  # Second-order effects
    risks: list[str]
    sensitivities: list[str]  # How result changes with assumptions
    counterarguments: list[str]
    recommendation_logic: list[str]  # Chain of reasoning for recommendation
    open_unknowns: list[str]  # Unresolved uncertainties


# =============================================================================
# Phase 5: Strategy
# =============================================================================


class SectionDataRequirement(TypedDict):
    """What data/frameworks a section needs to be substantive."""

    required_data: list[str]  # Specific data points needed (e.g. "population count", "API latency benchmarks")
    required_frameworks: list[str]  # Analytical frameworks to apply (e.g. "competitive_matrix", "risk_severity_table")
    specificity: str  # Guidance on precision level (e.g. "Use exact figures with sources, not ranges")


class ContentBlueprint(TypedDict):
    """Output from Output Strategist - communication structure."""

    structure: list[str]  # Section headers in order
    section_purposes: dict[str, str]  # section -> purpose
    narrative_flow: str  # How the reader journeys through content
    visual_elements: list[dict]  # Tables, charts, diagrams to include
    key_takeaways: list[str]  # 3-5 main points to remember
    audience_guidance: list[str]  # How to help audience understand
    section_data_requirements: Optional[dict[str, SectionDataRequirement]]  # section -> what data it needs


# =============================================================================
# Phase 7: Review
# =============================================================================


class RedTeamIssue(TypedDict):
    """Single issue from adversarial review."""

    issue_id: str  # e.g., "R001"
    severity: Literal["HIGH", "MEDIUM", "LOW"]
    section: str
    problem_type: Literal[
        "missing_dimension",
        "unsupported_claim",
        "shallow_analysis",
        "overconfidence",
        "weak_recommendation",
        "audience_mismatch",
        "poor_structure",
        "misleading_framing",
        "unaddressed_risk",
        "unexamined_assumption",
    ]
    repair_locus: Literal[
        "intent_architect",
        "research_lead",
        "evidence_ledger",
        "analyst",
        "output_strategist",
        "draft_writer",
        "polisher",
        "visual_designer",
        "visual_reviewer",
        "visual_generator",
    ]
    explanation: str
    suggested_fix: str


class RedTeamReview(TypedDict):
    """Output from Adversarial Reviewer - critique findings."""

    issues: list[RedTeamIssue]
    overall_assessment: str
    passed: bool


# =============================================================================
# Phase 8: Verification
# =============================================================================


class VerificationItem(TypedDict):
    """Single claim verification result."""

    claim_id: str
    status: Literal["SUPPORTED", "WEAK", "UNSUPPORTED", "INCONSISTENT"]
    repair_locus: Literal[
        "intent_architect",
        "research_lead",
        "evidence_ledger",
        "analyst",
        "output_strategist",
        "draft_writer",
        "polisher",
        "visual_designer",
        "visual_reviewer",
        "visual_generator",
    ]
    notes: str
    required_action: Optional[
        Literal[
            "add_source",
            "reclassify_claim",
            "downgrade_language",
            "remove_claim",
            "fix_number",
            "resolve_contradiction",
        ]
    ]


class VerificationReport(TypedDict):
    """Output from Verifier - claim support status."""

    items: list[VerificationItem]
    summary: str
    passed: bool


# =============================================================================
# Phase 10: Release
# =============================================================================


class ReleaseDecision(TypedDict):
    """Output from Final Arbiter - release readiness."""

    status: Literal["READY", "NOT_READY"]
    confidence: float  # 0.0-1.0
    remaining_risks: list[str]
    known_gaps: list[str]
    notes: str


# =============================================================================
# Phase 11: Visual Design
# =============================================================================


class VisualSpec(TypedDict):
    """Single visual specification from Visual Designer."""

    visual_id: str  # e.g., "V001"
    section_anchor: str  # Where to insert (section header)
    visual_type: Literal[
        # Simple (Mermaid)
        "flowchart",
        "sequence_diagram",
        "org_chart",
        "timeline",
        "gantt_chart",
        "concept_diagram",
        # Complex (Python)
        "bar_chart",
        "line_chart",
        "pie_chart",
        "scatter_plot",
        "heatmap",
        "statistical_chart",
    ]
    title: str
    description: str  # What this visual shows
    data_spec: dict  # Data needed or placeholder data
    complexity: Literal["SIMPLE", "COMPLEX"]  # SIMPLE = Mermaid, COMPLEX = Python
    mermaid_code: Optional[str]  # If SIMPLE
    placeholder_position: str  # Where in section to insert


class VisualReview(TypedDict):
    """Output from Visual Reviewer - validation of visual suggestions."""

    visual_id: str
    is_appropriate: bool
    clarity_score: float  # 0-1
    data_accuracy: float  # 0-1
    placement_correct: bool
    issues: list[str]
    suggestions: list[str]


class VisualGeneration(TypedDict):
    """Output from Visual Generator - generated visual assets."""

    visual_id: str
    visual_type: str
    generated_code: Optional[str]  # Python/matplotlib code or file path
    svg_output: Optional[str]  # For Mermaid SVGs
    image_path: Optional[str]  # Path to generated image
    generation_method: Literal["mermaid", "python"]
    notes: str


# =============================================================================
# Revision Tracking
# =============================================================================


class RevisionEntry(TypedDict):
    """Single revision in history."""

    version: int
    trigger: str  # What caused revision (review, verification, arbiter)
    issues_addressed: list[str]
    changes_made: str
    timestamp: str


# =============================================================================
# Schema Registry
# =============================================================================

ARTIFACT_SCHEMAS = {
    "execution_brief": ExecutionBrief,
    "research_map": ResearchMap,
    "claim_ledger": ClaimLedger,
    "analytical_backbone": AnalyticalBackbone,
    "content_blueprint": ContentBlueprint,
    "red_team_review": RedTeamReview,
    "verification_report": VerificationReport,
    "release_decision": ReleaseDecision,
    "visual_spec": VisualSpec,
    "visual_review": VisualReview,
    "visual_generation": VisualGeneration,
}


__all__ = [
    "ExecutionBrief",
    "ResearchQuery",
    "ResearchPlan",
    "ResearchSource",
    "ResearchMap",
    "SectionDataRequirement",
    "Claim",
    "ClaimLedger",
    "AnalyticalBackbone",
    "ContentBlueprint",
    "RedTeamIssue",
    "RedTeamReview",
    "VerificationItem",
    "VerificationReport",
    "ReleaseDecision",
    "RevisionEntry",
    "VisualSpec",
    "VisualReview",
    "VisualGeneration",
    "ARTIFACT_SCHEMAS",
]

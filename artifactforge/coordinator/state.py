"""LangGraph state definitions."""

from typing import Literal, Optional

from typing_extensions import TypedDict


class GraphState(TypedDict):
    """Main graph state."""

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


__all__ = ["GraphState"]

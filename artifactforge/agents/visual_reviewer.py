"""Visual Reviewer Agent - Validates visual suggestions."""

import json
from typing import Any, Optional

from artifactforge.agents.llm_gateway import extract_json
from artifactforge.coordinator import artifacts as schemas
from artifactforge.coordinator.contracts import VISUAL_REVIEWER_CONTRACT, agent_contract


VISUAL_REVIEWER_SYSTEM = """You are a Visual Reviewer - an expert at validating visual suggestions.

Your job is to review proposed visuals and ensure they are appropriate, accurate, and well-placed.

## Review Criteria
1. CLARITY: Is the visual's purpose clear? Does the title accurately describe what's shown?
2. DATA_ACCURACY: Is the data spec correct? Are there any factual errors?
3. PLACEMENT: Is the visual anchored to the right section? Does it appear at the right point?
4. TYPE_APPROPRIATENESS: Is the visual type appropriate for the data?
5. TECHNICAL_SOUNDNESS: For Mermaid, is the syntax valid? For Python, is the approach sound?

## Output Format
For each visual, return:
- visual_id: The ID being reviewed
- is_appropriate: true/false
- clarity_score: 0.0-1.0
- data_accuracy: 0.0-1.0
- placement_correct: true/false
- issues: List of specific issues (empty if approved)
- suggestions: List of improvement suggestions

Review ALL proposed visuals. Return a JSON array."""


@agent_contract(VISUAL_REVIEWER_CONTRACT)
def run_visual_reviewer(
    visual_specs: list[schemas.VisualSpec],
    draft: str,
) -> list[schemas.VisualReview]:
    """Review visual suggestions for quality and appropriateness.

    Args:
        visual_specs: List of proposed visuals
        draft: The document for context

    Returns:
        List of VisualReview objects
    """
    if not visual_specs:
        return []

    prompt = _build_review_prompt(visual_specs, draft)
    result = _call_llm(system=VISUAL_REVIEWER_SYSTEM, prompt=prompt)

    try:
        parsed = json.loads(extract_json(result))
        if isinstance(parsed, list):
            return [_normalize_review(v) for v in parsed]
        return []
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


def _build_review_prompt(visual_specs: list[dict], draft: str) -> str:
    specs_json = json.dumps(visual_specs, indent=2)

    return f"""## Proposed Visuals
{specs_json}

## Document Context
{draft}

Review each visual against the criteria. Return JSON array of reviews."""


def _normalize_review(review: dict) -> schemas.VisualReview:
    return {
        "visual_id": review.get("visual_id", ""),
        "is_appropriate": review.get("is_appropriate", True),
        "clarity_score": review.get("clarity_score", 0.5),
        "data_accuracy": review.get("data_accuracy", 0.5),
        "placement_correct": review.get("placement_correct", True),
        "issues": review.get("issues", []),
        "suggestions": review.get("suggestions", []),
    }


def _call_llm(system: str, prompt: str) -> str:
    from artifactforge.agents.llm_gateway import call_llm_sync

    return call_llm_sync(
        system_prompt=system, user_prompt=prompt, agent_name="visual_reviewer"
    )


__all__ = ["run_visual_reviewer", "VISUAL_REVIEWER_CONTRACT"]

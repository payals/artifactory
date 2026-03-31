"""Final Arbiter Agent - Decides whether output is ready to ship."""

import json
from typing import Any

from artifactforge.agents.llm_gateway import extract_json
from artifactforge.coordinator import artifacts as schemas
from artifactforge.coordinator.contracts import FINAL_ARBITER_CONTRACT, agent_contract
from artifactforge.coordinator.validation import validate_all_agents


FINAL_ARBITER_SYSTEM = """You are the Final Arbiter - the quality gate that decides if output is ready.

Your job is to be strict. Don't approve weak work.

## Release Criteria (ALL must be true)
1. User's core question is answered
2. Evidence and assumptions are separated
3. Critical unsupported claims are resolved or removed
4. Major risks/counterarguments are addressed
5. Recommendation present if task requires one
6. Known gaps are disclosed
7. Structure matches output type
8. Output is usable by intended audience
9. All agent contracts fulfilled (each agent's output meets its pass_fail_criteria)

## Decision Factors
- Review issues: Any HIGH severity unresolved?
- Verification: Any UNSUPPORTED claims remain?
- Completeness: All must-answer questions addressed?
- Quality: Would you ship this?
- Contract validation: Do all agents meet their contract criteria?

## Confidence Scale
- 0.9-1.0: Ready as-is
- 0.7-0.9: Minor issues, can ship
- 0.5-0.7: Significant issues, should revise
- <0.5: Not ready

## Output Format
Return JSON with:
- status: "READY" or "NOT_READY"
- confidence: 0.0-1.0
- remaining_risks: array
- known_gaps: array
- contract_validations: array of validation results for each agent
- notes: explanation
"""


@agent_contract(FINAL_ARBITER_CONTRACT)
def run_final_arbiter(
    execution_brief: dict[str, Any],
    draft: str,
    red_team_review: dict[str, Any],
    verification_report: dict[str, Any],
    all_artifacts: dict[str, Any],
) -> schemas.ReleaseDecision:
    """Run final arbiter to make release decision.

    Args:
        execution_brief: Original brief
        draft: Current draft
        red_team_review: Issues from adversarial reviewer
        verification_report: Verification findings
        all_artifacts: All artifacts from the pipeline for validation

    Returns:
        ReleaseDecision
    """
    # Run contract validation on all agents
    validation_results = validate_all_agents(all_artifacts)

    prompt = _build_arbiter_prompt(
        execution_brief, draft, red_team_review, verification_report, validation_results
    )
    result = _call_llm(system=FINAL_ARBITER_SYSTEM, prompt=prompt)

    try:
        parsed = json.loads(extract_json(result))
        return schemas.ReleaseDecision(
            status=parsed.get("status", "NOT_READY"),
            confidence=parsed.get("confidence", 0.0),
            remaining_risks=parsed.get("remaining_risks", []),
            known_gaps=parsed.get("known_gaps", []),
            notes=parsed.get("notes", ""),
        )
    except (json.JSONDecodeError, KeyError):
        return schemas.ReleaseDecision(
            status="NOT_READY",
            confidence=0.0,
            remaining_risks=["Decision not completed"],
            known_gaps=[],
            notes="Analysis failed",
        )


def _build_arbiter_prompt(
    brief: dict,
    draft: str,
    review: dict,
    verification: dict,
    validation_results: list,
) -> str:
    brief_summary = json.dumps(
        {
            "user_goal": brief.get("user_goal", ""),
            "must_answer": brief.get("must_answer_questions", []),
            "decision_required": brief.get("decision_required", False),
        },
        indent=2,
    )

    review_summary = "No issues"
    if review.get("issues"):
        review_summary = json.dumps(
            {
                "issues_count": len(review["issues"]),
                "high_severity": len(
                    [i for i in review["issues"] if i.get("severity") == "HIGH"]
                ),
                "passed": review.get("passed", False),
            },
            indent=2,
        )

    verification_summary = "Passed"
    if verification.get("items"):
        unsupported = [
            i for i in verification["items"] if i.get("status") == "UNSUPPORTED"
        ]
        verification_summary = json.dumps(
            {
                "total_checked": len(verification["items"]),
                "unsupported": len(unsupported),
                "passed": verification.get("passed", False),
            },
            indent=2,
        )

    validation_summary = "No validation results"
    if validation_results:
        validation_summary = json.dumps(validation_results, indent=2)

    return f"""## Brief
{brief_summary}

## Review Summary
{review_summary}

## Verification Summary
{verification_summary}

## Contract Validation Results
{validation_summary}

## Draft (excerpt)
{draft[:2000]}

Make release decision. Return JSON."""


def _call_llm(system: str, prompt: str) -> str:
    from artifactforge.agents.llm_gateway import call_llm_sync

    return call_llm_sync(
        system_prompt=system, user_prompt=prompt, agent_name="final_arbiter"
    )


__all__ = ["run_final_arbiter", "FINAL_ARBITER_CONTRACT"]

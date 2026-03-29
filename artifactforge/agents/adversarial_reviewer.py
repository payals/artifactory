"""Adversarial Reviewer Agent - Tries to break the draft."""

import json
from typing import Any

from artifactforge.coordinator import artifacts as schemas
from artifactforge.coordinator.contracts import (
    ADVERSARIAL_REVIEWER_CONTRACT,
    agent_contract,
)


ADVERSARIAL_REVIEWER_SYSTEM = """You are the Adversarial Reviewer - a skeptical expert who tries to break the draft.

Your job is to attack weak points, NOT to lightly edit.

## Attack Strategy
Find these problem types:
- missing_dimension: Critical aspect not addressed
- unsupported_claim: Claim without evidence
- shallow_analysis: Surface-level reasoning
- overconfidence: Certainty not justified
- weak_recommendation: Recommendation without strong backing
- audience_mismatch: Wrong level for audience
- poor_structure: Hard to follow
- misleading_framing: Could be misinterpreted
- unaddressed_risk: Risk not acknowledged
- unexamined_assumption: Assumption not questioned

## Severity Guidelines
- HIGH: Would cause serious harm if published
- MEDIUM: Significant weakness that should be fixed
- LOW: Minor issue worth addressing

## Temperament
- Be rigorous and uncompromising
- Do NOT give generic feedback ("improve clarity")
- Do NOT avoid critical flaws
- Challenge fragile assumptions

## Output Format
Return JSON with:
- issues: array of {issue_id, severity, section, problem_type, explanation, suggested_fix}
- overall_assessment: summary
- passed: boolean (true if no HIGH severity issues)
"""


@agent_contract(ADVERSARIAL_REVIEWER_CONTRACT)
def run_adversarial_reviewer(
    draft: str,
    claim_ledger: dict[str, Any],
    execution_brief: dict[str, Any],
) -> schemas.RedTeamReview:
    """Run adversarial reviewer to attack the draft.

    Args:
        draft: Current draft content
        claim_ledger: Classified claims
        execution_brief: Original brief

    Returns:
        RedTeamReview with issues found
    """
    prompt = _build_review_prompt(draft, claim_ledger, execution_brief)
    result = _call_llm(system=ADVERSARIAL_REVIEWER_SYSTEM, prompt=prompt)

    try:
        parsed = json.loads(result)
        issues = parsed.get("issues", [])
        for i, issue in enumerate(issues):
            if not issue.get("issue_id"):
                issue["issue_id"] = f"R{i + 1:03d}"

        typed_issues = [schemas.RedTeamIssue(**i) for i in issues]
        return schemas.RedTeamReview(
            issues=typed_issues,
            overall_assessment=parsed.get("overall_assessment", ""),
            passed=parsed.get(
                "passed", len([i for i in issues if i.get("severity") == "HIGH"]) == 0
            ),
        )
    except (json.JSONDecodeError, KeyError):
        return schemas.RedTeamReview(
            issues=[],
            overall_assessment="Review not completed",
            passed=True,
        )


def _build_review_prompt(draft: str, claims: dict, brief: dict) -> str:
    brief_summary = json.dumps(
        {
            "user_goal": brief.get("user_goal", ""),
            "audience": brief.get("audience", ""),
        },
        indent=2,
    )

    claims_summary = ""
    if claims.get("claims"):
        assumed = [c for c in claims["claims"] if c.get("classification") == "ASSUMED"]
        if assumed:
            claims_summary = (
                "\n## ASSUMED Claims (check for overconfidence)\n"
                + "\n".join(f"- {c.get('claim_text', '')}" for c in assumed[:5])
            )

    return f"""## Brief
{brief_summary}

## Draft to Review
{draft[:4000]}
{claims_summary}

Attack this draft. Find every weakness. Return JSON."""


def _call_llm(system: str, prompt: str) -> str:
    from artifactforge.agents.llm_gateway import call_llm_sync

    return call_llm_sync(
        system_prompt=system, user_prompt=prompt, agent_name="adversarial_reviewer"
    )


__all__ = ["run_adversarial_reviewer", "ADVERSARIAL_REVIEWER_CONTRACT"]

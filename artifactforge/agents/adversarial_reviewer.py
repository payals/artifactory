"""Adversarial Reviewer Agent - Tries to break the draft."""

import json
from typing import Any

from artifactforge.agents.llm_gateway import extract_json
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

## Repair Locus (CRITICAL)
For EACH issue, you MUST specify where to send it for repair:
- intent_architect: The whole task framing is wrong
- research_lead: Need more/better sources (e.g., missing competitor analysis)
- evidence_ledger: Facts exist but poorly separated from assumptions
- analyst: Reasoning is weak even with good evidence
- output_strategist: Structure wrong for audience
- draft_writer: Expression/substance needs work
- polisher: Just needs cleanup
- visual_designer: Visual specification is wrong or inappropriate
- visual_reviewer: Visual review missed issues
- visual_generator: Generated visual is incorrect

## Temperament
- Be rigorous and uncompromising
- Do NOT give generic feedback ("improve clarity")
- Do NOT avoid critical flaws
- Challenge fragile assumptions

## Output Format
Return JSON with:
- issues: array of {issue_id, severity, section, problem_type, repair_locus, explanation, suggested_fix}
- overall_assessment: summary
- passed: boolean (true if no HIGH severity issues)
"""

PROBLEM_TYPE_DEFAULT_LOCUS: dict[str, str] = {
    "missing_dimension": "research_lead",
    "unsupported_claim": "evidence_ledger",
    "shallow_analysis": "analyst",
    "overconfidence": "evidence_ledger",
    "weak_recommendation": "analyst",
    "audience_mismatch": "output_strategist",
    "poor_structure": "output_strategist",
    "misleading_framing": "intent_architect",
    "unaddressed_risk": "analyst",
    "unexamined_assumption": "evidence_ledger",
}


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
        parsed = json.loads(extract_json(result))
        issues = parsed.get("issues", [])
        valid_loci = {
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
        }
        for i, issue in enumerate(issues):
            if not issue.get("issue_id"):
                issue["issue_id"] = f"R{i + 1:03d}"
            if (
                not issue.get("repair_locus")
                or issue.get("repair_locus") not in valid_loci
            ):
                issue["repair_locus"] = PROBLEM_TYPE_DEFAULT_LOCUS.get(
                    issue.get("problem_type", ""), "draft_writer"
                )
            issue.setdefault("severity", "MEDIUM")
            issue.setdefault("section", "")
            issue.setdefault("problem_type", "shallow_analysis")
            issue.setdefault("explanation", "")
            issue.setdefault("suggested_fix", "")

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

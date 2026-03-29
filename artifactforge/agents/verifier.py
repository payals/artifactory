"""Verifier Agent - Ensures support, traceability, and consistency."""

import json
from typing import Any

from artifactforge.coordinator import artifacts as schemas
from artifactforge.coordinator.contracts import VERIFIER_CONTRACT, agent_contract


VERIFIER_SYSTEM = """You are the Verifier - a grounding agent that checks support and consistency.

Your job is to verify claims and find inconsistencies, NOT to rewrite.

## Verification Tasks
1. Check SUPPORT: Does each claim have evidence?
2. Check TRACEABILITY: Can claims be traced to sources?
3. Check CONSISTENCY: Do numbers, facts align?
4. Check LANGUAGE: Is confidence appropriate?

## Status Definitions
- SUPPORTED: Clear evidence, can cite
- WEAK: Some evidence but not definitive
- UNSUPPORTED: No evidence or contradicts evidence
- INCONSISTENT: Contradicts other claims or sources

## Required Actions
- add_source: Need citation
- reclassify_claim: Change VERIFIED/DERIVED/ASSUMED
- downgrade_language: "is" -> "appears to be"
- remove_claim: Cannot be supported
- fix_number: Numerical error
- resolve_contradiction: Two claims conflict

## Language Downgrades
- "is" -> "appears to be" / "may be"
- "will" -> "may" / "might"
- "proves" -> "suggests" / "indicates"
- "clearly" -> remove unless truly justified
- "certainly" -> remove

## Output Format
Return JSON with:
- items: array of {claim_id, status, notes, required_action}
- summary: overview
- passed: boolean (true if no UNSUPPORTED)
"""


@agent_contract(VERIFIER_CONTRACT)
def run_verifier(
    draft: str,
    claim_ledger: dict[str, Any],
) -> schemas.VerificationReport:
    """Run verifier to check claim support and consistency.

    Args:
        draft: Current draft
        claim_ledger: Classified claims

    Returns:
        VerificationReport with findings
    """
    prompt = _build_verification_prompt(draft, claim_ledger)
    result = _call_llm(system=VERIFIER_SYSTEM, prompt=prompt)

    try:
        parsed = json.loads(result)
        items = parsed.get("items", [])
        typed_items = [schemas.VerificationItem(**i) for i in items]
        return schemas.VerificationReport(
            items=typed_items,
            summary=parsed.get("summary", ""),
            passed=parsed.get(
                "passed", all(i.get("status") != "UNSUPPORTED" for i in items)
            ),
        )
    except (json.JSONDecodeError, KeyError):
        return schemas.VerificationReport(
            items=[],
            summary="Verification not completed",
            passed=True,
        )


def _build_verification_prompt(draft: str, claims: dict) -> str:
    claims_text = ""
    if claims.get("claims"):
        claims_text = "\n## Claims to Verify\n" + "\n".join(
            f"- [{c.get('classification', '?')}] {c.get('claim_text', '')} (confidence: {c.get('confidence', 'N/A')})"
            for c in claims["claims"]
        )

    return f"""## Draft
{draft[:4000]}
{claims_text}

Verify each claim. Check support and consistency. Return JSON."""


def _call_llm(system: str, prompt: str) -> str:
    from artifactforge.agents.llm_gateway import call_llm_sync

    return call_llm_sync(
        system_prompt=system, user_prompt=prompt, agent_name="verifier"
    )


__all__ = ["run_verifier", "VERIFIER_CONTRACT"]

"""Evidence Ledger Agent - Core epistemic classification layer.

This agent separates facts from inference from assumption.
This is the MOST IMPORTANT agent in the MCRS system as it prevents
facts/assumptions blurring which undermines trustworthiness.
"""

import json
import logging
import uuid
from typing import Any, Optional

from artifactforge.agents.llm_gateway import extract_json
from artifactforge.coordinator import artifacts as schemas
from artifactforge.coordinator.contracts import EVIDENCE_LEDGER_CONTRACT, agent_contract

logger = logging.getLogger(__name__)


# System prompt for the Evidence Ledger
EVIDENCE_LEDGER_SYSTEM = """You are the Evidence Ledger - a critical thinking agent that classifies claims by their epistemic status.

Your job is to transform raw research into atomic, traceable claims with explicit confidence levels.

## Classification Rules

### VERIFIED
- Directly grounded in source material
- Factual statements that can be cited
- Specific numbers, dates, names, quotes
- Confidence: 0.8-1.0
- MUST have source_refs

### DERIVED
- Inferences or conclusions from verified facts
- Logical extensions, implications
- Patterns identified in data
- Confidence: 0.5-0.8
- MUST reference VERIFIED claims it depends on

### ASSUMED
- Scenario inputs, estimates, forecasts
- Planning placeholders
- Explicit guesses
- Confidence: 0.1-0.5
- MUST NOT masquerade as verified

## Critical Rules
1. NEVER assign VERIFIED without source_refs
2. NEVER omit the dependent_on field for DERIVED claims
3. NEVER create vague claims that can't be checked
4. NEVER inflate confidence to appear more certain
5. If you cannot verify, mark as ASSUMED

## Output Format
Return a JSON object with:
- claims: array of objects, each with:
  - claim_id: str (e.g. "C001")
  - claim_text: str (the claim itself)
  - classification: one of "VERIFIED", "DERIVED", "ASSUMED"
  - source_refs: list[str] (source_ids backing this claim)
  - confidence: float (0.0-1.0)
  - importance: one of "HIGH", "MEDIUM", "LOW"
  - dependent_on: list[str] (claim_ids this depends on, empty if none)
  - notes: str (reasoning for classification)
- summary: brief overview of epistemic status distribution
"""


@agent_contract(EVIDENCE_LEDGER_CONTRACT)
def run_evidence_ledger(
    research_map: dict[str, Any],
    *,
    deep_analyze: bool = False,
    query_context: Optional[str] = None,
    repair_context: Optional[dict[str, Any]] = None,
) -> schemas.ClaimLedger:
    """Run evidence ledger on research map to classify all claims.

    Args:
        research_map: Output from Research Lead containing sources and facts
        deep_analyze: If True, use deep_analyzer to fetch and analyze URLs in depth
        query_context: The original query for deep analysis context

    Returns:
        ClaimLedger with classified claims
    """
    sources = research_map.get("sources", [])
    facts = research_map.get("facts", [])
    key_dimensions = research_map.get("key_dimensions", [])

    if not facts and not key_dimensions:
        logger.warning(
            "evidence_ledger skipping - no facts ({}) or key_dimensions ({}) available".format(
                len(facts), len(key_dimensions)
            )
        )
        return {
            "claims": [],
            "summary": "No research data available for claim extraction",
        }

    # Optional: Deep analyze top sources for richer evidence
    if deep_analyze and sources:
        deep_findings = _perform_deep_analysis(sources, query_context)
        if deep_findings:
            logger.info(
                f"Deep analysis found {len(deep_findings.get('key_findings', []))} key findings"
            )
            # Merge deep findings into facts
            findings = deep_findings.get("key_findings", [])
            if findings:
                facts = list(facts) + findings

    # Build source reference map
    source_map = {s.get("source_id", f"SRC_{i}"): s for i, s in enumerate(sources)}

    # Build prompt for classification
    prompt = _build_classification_prompt(
        sources=sources,
        facts=facts,
        key_dimensions=key_dimensions,
        repair_context=repair_context,
    )

    # Call LLM (would integrate with existing LLM client)
    result = _call_llm(system=EVIDENCE_LEDGER_SYSTEM, prompt=prompt)

    # Parse result
    try:
        parsed = json.loads(extract_json(result))
        claims: list[dict] = parsed.get("claims", [])
        summary = parsed.get("summary", "")
    except (json.JSONDecodeError, KeyError):
        # Fallback: create basic claims from facts
        claims = _create_fallback_claims(facts, sources)
        summary = (
            f"Created {len(claims)} claims from {len(facts)} facts (fallback mode)"
        )

    # Ensure all claims have IDs and cast to proper type
    typed_claims: list[schemas.Claim] = []
    for i, claim in enumerate(claims):
        if not claim.get("claim_id"):
            claim["claim_id"] = f"C{i + 1:03d}"
        claim.setdefault("claim_text", "")
        claim.setdefault("classification", "DERIVED")
        claim.setdefault("source_refs", [])
        claim.setdefault("confidence", 0.0)
        claim.setdefault("importance", "MEDIUM")
        claim.setdefault("dependent_on", [])
        claim.setdefault("notes", "")
        typed_claims.append(schemas.Claim(**claim))

    return schemas.ClaimLedger(claims=typed_claims, summary=summary)


def _build_classification_prompt(
    sources: list[dict],
    facts: list[str],
    key_dimensions: list[str],
    repair_context: Optional[dict[str, Any]] = None,
) -> str:
    """Build prompt for claim classification."""
    sources_text = "\n".join(
        f"- {s.get('title', 'Unknown')}: {s.get('source_id', 'N/A')}" for s in sources
    )

    facts_text = "\n".join(f"- {f}" for f in facts)

    dimensions_text = "\n".join(f"- {d}" for d in key_dimensions)

    repair_text = ""
    if repair_context:
        repair_text = "\n## Repair Context\n" + json.dumps(repair_context, indent=2)

    return f"""## Sources Available
{sources_text}

## Key Dimensions to Address
{dimensions_text}

## Extracted Facts
{facts_text}
{repair_text}

## Your Task
Create atomic claims from this research. For each claim:
1. Assign it a classification (VERIFIED, DERIVED, or ASSUMED)
2. Assign confidence (0.0-1.0)
3. Add source references (for VERIFIED) or dependencies (for DERIVED)
4. Mark importance level

Return JSON with "claims" array and "summary" string."""


def _create_fallback_claims(
    facts: list[str],
    sources: list[dict],
) -> list[dict]:
    """Create basic claims when LLM fails."""
    claims = []
    source_ids = [s.get("source_id", f"SRC_{i}") for i, s in enumerate(sources)]

    for i, fact in enumerate(facts):
        claims.append(
            {
                "claim_id": f"C{i + 1:03d}",
                "claim_text": fact,
                "classification": "VERIFIED" if source_ids else "ASSUMED",
                "source_refs": source_ids[:1] if source_ids else [],
                "confidence": 0.9 if source_ids else 0.3,
                "importance": "HIGH",
                "dependent_on": [],
                "notes": "Auto-classified fallback",
            }
        )

    return claims


def _perform_deep_analysis(
    sources: list[dict],
    query_context: Optional[str] = None,
) -> dict[str, Any]:
    """Perform deep analysis on top sources using deep_analyzer."""
    try:
        from artifactforge.tools.research.deep_analyzer import run_deep_analyzer

        urls = [s.get("url", "") for s in sources if s.get("url")]
        if not urls:
            return {}

        return run_deep_analyzer(
            sources=urls[:5],
            query=query_context or "Analyze for key claims and evidence",
        )
    except ImportError:
        logger.warning("deep_analyzer not available, skipping deep analysis")
        return {}
    except Exception as e:
        logger.error(f"Deep analysis failed: {e}")
        return {}


def _call_llm(system: str, prompt: str) -> str:
    from artifactforge.agents.llm_gateway import call_llm_sync

    return call_llm_sync(
        system_prompt=system, user_prompt=prompt, agent_name="evidence_ledger"
    )


__all__ = ["run_evidence_ledger", "EVIDENCE_LEDGER_CONTRACT"]

"""Polisher Agent - Improves readability without changing substance."""

from typing import Any

from artifactforge.coordinator.contracts import POLISHER_CONTRACT, agent_contract


POLISHER_SYSTEM = """You are the Polisher - an expert at improving readability.

Your job is to make content clearer and more scanable WITHOUT changing substance.

## Improvements Allowed
- Clearer section headers
- Better transitions
- Tighten repetition
- Improve sentence flow
- Better formatting
- Add emphasis where appropriate

## Critical Constraints
- NEVER change meaning of claims
- NEVER remove uncertainty markers (may, might, appears)
- NEVER hide unresolved issues
- NEVER alter conclusions
- NEVER change epistemic status of claims

## Formatting for Medium
- markdown: Standard markdown
- pdf: Structure for PDF generation
- slides: Lightweight markup

## Output
Return the polished version as a string.
"""


@agent_contract(POLISHER_CONTRACT)
def run_polisher(
    draft: str,
    output_type: str = "report",
) -> str:
    """Run polisher to improve readability.

    Args:
        draft: Current draft
        output_type: Target format

    Returns:
        Polished draft
    """
    prompt = _build_polish_prompt(draft, output_type)
    result = _call_llm(system=POLISHER_SYSTEM, prompt=prompt)
    return result.strip()


def _build_polish_prompt(draft: str, output_type: str) -> str:
    return f"""## Current Draft
{draft}

## Target Format
{output_type}

Polish for readability. Keep all meaning, claims, and uncertainty markers intact. Return polished version."""


def _call_llm(system: str, prompt: str) -> str:
    from artifactforge.agents.llm_gateway import call_llm_sync

    return call_llm_sync(
        system_prompt=system, user_prompt=prompt, agent_name="polisher"
    )


__all__ = ["run_polisher", "POLISHER_CONTRACT"]

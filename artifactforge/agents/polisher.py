"""Polisher Agent - Improves readability without changing substance."""

import json
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
- Consolidate data gap notices: if inline warnings like "Data Gap Notice", "⚠️", "data not found", or similar banners appear in the body, MOVE them to a "Research Limitations & Data Gaps" appendix at the end. Replace the inline notice with hedged natural language.

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
    repair_context: dict[str, Any] | None = None,
    learnings_context: dict[str, Any] | None = None,
) -> str:
    """Run polisher to improve readability.

    Args:
        draft: Current draft
        output_type: Target format

    Returns:
        Polished draft
    """
    prompt = _build_polish_prompt(draft, output_type, repair_context)
    result = _call_llm(system=POLISHER_SYSTEM, prompt=prompt)
    return _strip_markdown_fence(result)


def _build_polish_prompt(
    draft: str,
    output_type: str,
    repair_context: dict[str, Any] | None,
) -> str:
    repair_text = ""
    if repair_context:
        repair_text = "\n## Repair Context\n" + json.dumps(repair_context, indent=2)

    return f"""## Current Draft
{draft}

## Target Format
{output_type}
{repair_text}

Polish for readability. Keep all meaning, claims, and uncertainty markers intact. Return polished version."""


def _strip_markdown_fence(text: str) -> str:
    """Remove wrapping ```markdown ... ``` code fences from LLM output."""
    import re

    stripped = text.strip()
    match = re.match(r"^```(?:markdown)?\s*\n(.*?)```\s*$", stripped, re.DOTALL)
    if match:
        return match.group(1).strip()
    return stripped


def _call_llm(system: str, prompt: str) -> str:
    from artifactforge.agents.llm_gateway import call_llm_sync

    return call_llm_sync(
        system_prompt=system, user_prompt=prompt, agent_name="polisher"
    )


__all__ = ["run_polisher", "POLISHER_CONTRACT"]

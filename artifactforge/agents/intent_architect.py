"""Intent Architect Agent - Translates user requests to execution briefs.

This agent prevents answering the wrong question by inferring the actual goal
behind the user's literal prompt.
"""

import json
from typing import Any, Optional

from artifactforge.coordinator import artifacts as schemas
from artifactforge.coordinator.contracts import (
    INTENT_ARCHITECT_CONTRACT,
    agent_contract,
)


INTENT_ARCHITECT_SYSTEM = """You are the Intent Architect - an expert at understanding what users actually need.

Your job is to translate raw user requests into precise execution briefs.

## Common Mismatches to Detect
- "market opportunity" → might need go/no-go analysis
- "write a blog" → might need thought leadership for technical audience
- "make slides" → might need persuasion for non-experts
- "review this design" → might need failure modes and risk prioritization
- "compare X and Y" → might need decision framework, not just comparison

## Missing Dimensions to Infer
For market research → demographics, demand, competition, cost, regulation, risk, recommendation
For technical review → architecture, tradeoffs, bottlenecks, risks, rollout concerns
For slides → narrative arc, audience sophistication, aha moments, objections to address
For blog → audience, thesis, novelty, counterarguments, readability
For decision memo → options, pros/cons, risks, recommendation, timeline

## Output Requirements
Return a JSON object with:
- user_goal: What the user actually needs (not just what they asked for)
- output_type: The format that best serves the goal
- audience: Who will consume this
- tone: Appropriate tone (formal, conversational, technical, persuasive)
- must_answer_questions: Critical questions this must address
- constraints: Any stated constraints
- success_criteria: What "done" looks like
- likely_missing_dimensions: What they'd need but didn't mention
- decision_required: Whether a decision recommendation is needed
- rigor_level: LOW/MEDIUM/HIGH based on stakes
- persuasion_level: LOW/MEDIUM/HOW based on audience alignment
- open_questions: What needs research to resolve
"""


@agent_contract(INTENT_ARCHITECT_CONTRACT)
def run_intent_architect(
    user_prompt: str,
    conversation_context: Optional[list[dict]] = None,
    output_constraints: Optional[dict] = None,
) -> schemas.ExecutionBrief:
    """Analyze user intent and create execution brief.

    Args:
        user_prompt: Raw user request
        conversation_context: Prior conversation history
        output_constraints: Any stated constraints

    Returns:
        ExecutionBrief with all parameters defined
    """
    prompt = _build_intent_prompt(user_prompt, conversation_context, output_constraints)
    result = _call_llm(system=INTENT_ARCHITECT_SYSTEM, prompt=prompt)

    try:
        parsed = json.loads(result)
        # Validate required fields
        return _validate_and_defaults(parsed)
    except (json.JSONDecodeError, KeyError, TypeError):
        return _create_default_brief(user_prompt)


def _build_intent_prompt(
    user_prompt: str,
    conversation_context: Optional[list[dict]],
    output_constraints: Optional[dict],
) -> str:
    """Build prompt for intent analysis."""
    context_text = ""
    if conversation_context:
        context_text = "\n## Prior Conversation\n" + "\n".join(
            f"- {msg.get('role', 'unknown')}: {msg.get('content', '')[:200]}"
            for msg in conversation_context[-3:]
        )

    constraints_text = ""
    if output_constraints:
        constraints_text = "\n## Stated Constraints\n" + json.dumps(
            output_constraints, indent=2
        )

    return f"""## User Request
{user_prompt}
{context_text}
{constraints_text}

Analyze this request and create an execution brief in JSON format."""


def _validate_and_defaults(parsed: dict) -> schemas.ExecutionBrief:
    """Validate and apply defaults to parsed result."""
    return {
        "user_goal": parsed.get("user_goal", parsed.get("user_prompt", "")),
        "output_type": parsed.get("output_type", "report"),
        "audience": parsed.get("audience", "general"),
        "tone": parsed.get("tone", "professional"),
        "must_answer_questions": parsed.get("must_answer_questions", []),
        "constraints": parsed.get("constraints", []),
        "success_criteria": parsed.get("success_criteria", []),
        "likely_missing_dimensions": parsed.get("likely_missing_dimensions", []),
        "decision_required": parsed.get("decision_required", False),
        "rigor_level": parsed.get("rigor_level", "MEDIUM"),
        "persuasion_level": parsed.get("persuasion_level", "MEDIUM"),
        "open_questions_to_resolve": parsed.get("open_questions_to_resolve", []),
    }


def _create_default_brief(user_prompt: str) -> schemas.ExecutionBrief:
    """Create default brief when parsing fails."""
    return {
        "user_goal": user_prompt,
        "output_type": "report",
        "audience": "general",
        "tone": "professional",
        "must_answer_questions": [],
        "constraints": [],
        "success_criteria": ["Complete the request"],
        "likely_missing_dimensions": [],
        "decision_required": False,
        "rigor_level": "MEDIUM",
        "persuasion_level": "MEDIUM",
        "open_questions_to_resolve": [],
    }


def _call_llm(system: str, prompt: str) -> str:
    from artifactforge.agents.llm_gateway import call_llm_sync

    return call_llm_sync(
        system_prompt=system, user_prompt=prompt, agent_name="intent_architect"
    )


__all__ = ["run_intent_architect", "INTENT_ARCHITECT_CONTRACT"]

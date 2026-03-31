"""Intent Architect Agent - Translates user requests to execution briefs.

This agent prevents answering the wrong question by inferring the actual goal
behind the user's literal prompt.
"""

import json
from typing import Any, Optional

from pydantic import BaseModel

from artifactforge.agents.llm_gateway import extract_json
from artifactforge.coordinator import artifacts as schemas
from artifactforge.coordinator.contracts import (
    INTENT_ARCHITECT_CONTRACT,
    agent_contract,
)


class ClarificationQuestion(BaseModel):
    """A single clarification question with multiple choice options."""

    id: str
    question: str
    options: list[str]  # Last option must be "Other (specify)"


CLARIFICATION_QUESTION_SYSTEM = """You are an expert at asking clarifying questions to ensure an AI produces exactly what the user needs.

Your job is to analyze the user's request and generate 3-5 targeted questions that will help produce a better output.
Each question MUST have exactly 5 options - 4 specific choices + "Other (specify)" as the last option.

## Output Type Guidelines:

### SLIDES/PRESENTATION
- Number of slides
- Theme/style (corporate, creative, minimal, technical)
- Content structure (section order)
- Existing content to incorporate
- Target audience
- Presentation date/deadline
- Speaker notes needed?

### REPORT/DOCUMENT
- Primary goal (inform, persuade, document, decide)
- Target audience
- Length/depth (brief overview, detailed analysis, comprehensive)
- Existing data sources to use
- Specific sections required
- Deadline
- Tone (formal, conversational, technical)

### BLOG POST
- Primary goal (educate, persuade, entertain)
- Target audience expertise level
- Desired length
- SEO keywords to target
- Existing content to reference
- Tone (professional, casual, witty)

### RFP
- Project scope overview
- Budget range
- Timeline requirements
- Required vendor qualifications
- Evaluation criteria
- Submission deadline

### Other output types
Generate questions appropriate to the output type and user prompt.

## Output Format
Return a JSON array of questions, each with:
- id: unique identifier (q1, q2, q3, etc.)
- question: the question text
- options: array of 5 options (4 specific + "Other (specify)")

Example:
[
  {"id": "q1", "question": "What is the primary goal?", 
   "options": ["Inform/educate", "Persuade/convince", "Help make a decision", "Document current state", "Other (specify)"]},
  {"id": "q2", "question": "Who is the target audience?",
   "options": ["Executive leadership", "Technical team", "General public", "Industry experts", "Other (specify)"]}
]"""


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
- persuasion_level: LOW/MEDIUM/HIGH based on audience alignment
- open_questions_to_resolve: What needs research to resolve
"""


@agent_contract(INTENT_ARCHITECT_CONTRACT)
def run_intent_architect(
    user_prompt: str,
    conversation_context: Optional[list[dict]] = None,
    output_constraints: Optional[dict] = None,
    intent_mode: str = "auto",
    answers_collected: Optional[dict[str, str]] = None,
    repair_context: Optional[dict[str, Any]] = None,
) -> schemas.ExecutionBrief:
    """Analyze user intent and create execution brief.

    Args:
        user_prompt: Raw user request
        conversation_context: Prior conversation history
        output_constraints: Any stated constraints

    Returns:
        ExecutionBrief with all parameters defined
    """
    prompt = _build_intent_prompt(
        user_prompt,
        conversation_context,
        output_constraints,
        intent_mode,
        answers_collected,
        repair_context,
    )
    result = _call_llm(system=INTENT_ARCHITECT_SYSTEM, prompt=prompt)

    try:
        parsed = json.loads(extract_json(result))
        parsed.setdefault("intent_mode", intent_mode)
        parsed.setdefault("answers_collected", answers_collected or {})
        # Validate required fields
        return _validate_and_defaults(parsed)
    except (json.JSONDecodeError, KeyError, TypeError):
        return _create_default_brief(user_prompt, intent_mode, answers_collected)


def _build_intent_prompt(
    user_prompt: str,
    conversation_context: Optional[list[dict]],
    output_constraints: Optional[dict],
    intent_mode: str,
    answers_collected: Optional[dict[str, str]],
    repair_context: Optional[dict[str, Any]],
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

    clarification_text = "\n## Clarification Mode\n"
    clarification_text += (
        "User chose interactive clarification before pipeline execution."
        if intent_mode == "interactive"
        else "User chose automatic execution without clarification questions."
    )

    if answers_collected:
        clarification_text += "\n\n## Clarification Answers\n" + json.dumps(
            answers_collected, indent=2
        )

    repair_text = ""
    if repair_context:
        repair_text = "\n## Repair Context\n" + json.dumps(repair_context, indent=2)

    return f"""## User Request
{user_prompt}
{context_text}
{constraints_text}
{clarification_text}
{repair_text}

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
        "intent_mode": parsed.get("intent_mode", "auto"),
        "answers_collected": parsed.get("answers_collected", {}),
    }


def _create_default_brief(
    user_prompt: str,
    intent_mode: str = "auto",
    answers_collected: Optional[dict[str, str]] = None,
) -> schemas.ExecutionBrief:
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
        "intent_mode": intent_mode if intent_mode == "interactive" else "auto",
        "answers_collected": answers_collected or {},
    }


def _call_llm(system: str, prompt: str) -> str:
    from artifactforge.agents.llm_gateway import call_llm_sync

    return call_llm_sync(
        system_prompt=system, user_prompt=prompt, agent_name="intent_architect"
    )


def generate_clarification_questions(
    user_prompt: str, output_type: str
) -> list[ClarificationQuestion]:
    """Generate dynamic clarification questions based on prompt and output type."""
    prompt = f"""## User Request
{user_prompt}

## Output Type
{output_type}

Generate 3-5 clarification questions as a JSON array."""

    result = _call_llm(system=CLARIFICATION_QUESTION_SYSTEM, prompt=prompt)

    try:
        parsed = json.loads(extract_json(result))
        questions = []
        for item in parsed:
            questions.append(
                ClarificationQuestion(
                    id=item.get("id", f"q{len(questions) + 1}"),
                    question=item.get("question", ""),
                    options=item.get("options", []),
                )
            )
        return questions
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return []


__all__ = [
    "run_intent_architect",
    "INTENT_ARCHITECT_CONTRACT",
    "generate_clarification_questions",
    "ClarificationQuestion",
]

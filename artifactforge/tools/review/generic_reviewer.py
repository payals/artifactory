"""Generic reviewer tool - reviews artifact drafts for quality."""

import json
import os
from typing import Any, Dict, cast

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from artifactforge.config import get_settings

settings = get_settings()
OPENAI_API_KEY = settings.openai_api_key or os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")


class ReviewInput(BaseModel):
    artifact_type: str = Field(description="Type of artifact")
    draft: str = Field(description="Artifact draft to review")
    context: Dict[str, Any] = Field(description="Research context")
    artifact_schema: Dict[str, Any] = Field(
        default_factory=dict,
        alias="schema",
        description="Artifact schema",
    )


async def _review_with_llm(
    artifact_type: str,
    draft: str,
    context: Dict[str, Any],
    schema: Dict[str, Any],
) -> dict[str, Any]:
    """Review artifact using LLM."""
    if artifact_type == "simple_report":
        return _review_simple_report(draft, context, schema)

    if ANTHROPIC_API_KEY:
        return await _review_with_anthropic(artifact_type, draft, context, schema)
    elif OPENAI_API_KEY:
        return await _review_with_openai(artifact_type, draft, context, schema)
    else:
        return _mock_review(artifact_type)


async def _review_with_anthropic(
    artifact_type: str,
    draft: str,
    context: Dict[str, Any],
    schema: Dict[str, Any],
) -> dict[str, Any]:
    """Review using Anthropic API."""
    assert ANTHROPIC_API_KEY is not None

    prompt = f"""Review the following {artifact_type} draft:

Draft:
{draft[:4000]}

Context:
{json.dumps(context, indent=2)[:1000]}

Schema:
{json.dumps(schema, indent=2)[:1000]}

Evaluate:
1. completeness (0-1)
2. clarity (0-1)
3. accuracy (0-1)

Respond with JSON:
{{"passed": true/false, "issues": [], "suggestions": [], "scores": {{"completeness": 0.0, "clarity": 0.0, "accuracy": 0.0}}}}"""

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 2048,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        response.raise_for_status()
        data = response.json()

    text = data["content"][0]["text"]

    try:
        result = json.loads(text)
        return cast(dict[str, Any], result)
    except json.JSONDecodeError:
        return _parse_review_text(text)


async def _review_with_openai(
    artifact_type: str,
    draft: str,
    context: Dict[str, Any],
    schema: Dict[str, Any],
) -> dict[str, Any]:
    """Review using OpenAI API."""
    assert OPENAI_API_KEY is not None

    prompt = f"""Review the following {artifact_type} draft:

Draft:
{draft[:4000]}

Context:
{json.dumps(context, indent=2)[:1000]}

Schema:
{json.dumps(schema, indent=2)[:1000]}

Evaluate:
1. completeness (0-1)
2. clarity (0-1)
3. accuracy (0-1)

Respond with JSON:
{{"passed": true/false, "issues": [], "suggestions": [], "scores": {{"completeness": 0.0, "clarity": 0.0, "accuracy": 0.0}}}}"""

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 2048,
                "response_format": {"type": "json_object"},
            },
        )
        response.raise_for_status()
        data = response.json()

    text = data["choices"][0]["message"]["content"]

    try:
        result = json.loads(text)
        return cast(dict[str, Any], result)
    except json.JSONDecodeError:
        return _parse_review_text(text)


def _parse_review_text(text: str) -> dict[str, Any]:
    """Parse review text when JSON parsing fails."""
    lines = text.split("\n")
    issues = []
    suggestions = []
    scores = {"completeness": 0.5, "clarity": 0.5, "accuracy": 0.5}

    for line in lines:
        line = line.strip().lower()
        if "issue" in line or "problem" in line:
            issues.append(line)
        if "suggest" in line or "improve" in line:
            suggestions.append(line)

    passed = len(issues) < 3

    return {
        "passed": passed,
        "issues": issues,
        "suggestions": suggestions,
        "scores": scores,
    }


def _mock_review(artifact_type: str) -> dict[str, Any]:
    """Mock review when no API keys available."""
    return {
        "passed": True,
        "issues": [],
        "suggestions": ["Consider adding more details"],
        "scores": {"completeness": 0.6, "clarity": 0.7, "accuracy": 0.5},
    }


def _review_simple_report(
    draft: str, context: Dict[str, Any], schema: Dict[str, Any]
) -> dict[str, Any]:
    required_sections = [
        section.get("title", "") for section in schema.get("sections", [])
    ]
    issues = []
    suggestions = []

    for title in required_sections:
        if f"## {title}" not in draft:
            issues.append(f"Missing required section: {title}")

    word_count = len(draft.split())
    if word_count < 80:
        issues.append("Draft is too short to be reader-focused and specific.")
        suggestions.append("Add more evidence-backed detail for each required section.")

    if "- " not in draft:
        suggestions.append("Use concise bullet points to improve readability.")

    context_findings = [str(item) for item in context.get("key_findings", [])]
    if context_findings and not any(finding in draft for finding in context_findings):
        suggestions.append(
            "Reflect the strongest research findings directly in the draft."
        )

    report_kind = schema.get("report_kind", "general")
    decision_expected = report_kind in {"market_feasibility", "comparison"}
    decision_present = "## Recommendation" in draft
    if decision_expected and not decision_present:
        issues.append(
            "Decision-oriented reports must include a Recommendation section."
        )

    completeness = max(0.0, 1 - (len(issues) * 0.15))
    clarity = 0.85 if word_count >= 80 else 0.45
    accuracy = 0.7 if context else 0.5
    readability = 0.8 if "- " in draft else 0.55
    specificity = (
        0.8
        if context_findings and any(finding in draft for finding in context_findings)
        else 0.5
    )
    decision_usefulness = 0.85 if not decision_expected or decision_present else 0.35

    scores = {
        "completeness": round(completeness, 2),
        "clarity": round(clarity, 2),
        "accuracy": round(accuracy, 2),
        "readability": round(readability, 2),
        "specificity": round(specificity, 2),
    }

    if decision_expected:
        scores["decision_usefulness"] = round(decision_usefulness, 2)

    return {
        "passed": not issues,
        "issues": issues,
        "suggestions": suggestions,
        "scores": scores,
    }


def run_generic_reviewer(
    artifact_type: str,
    draft: str,
    context: Dict[str, Any],
    schema: Dict[str, Any],
) -> Dict[str, Any]:
    import asyncio

    return asyncio.run(_review_with_llm(artifact_type, draft, context, schema))


@tool(args_schema=ReviewInput)
def generic_reviewer(
    artifact_type: str,
    draft: str,
    context: Dict[str, Any],
    artifact_schema: Dict[str, Any],
) -> Dict[str, Any]:
    """Review artifact draft for quality.

    Uses LLM to evaluate completeness, clarity, and accuracy.
    """
    return run_generic_reviewer(
        artifact_type=artifact_type,
        draft=draft,
        context=context,
        schema=artifact_schema,
    )


__all__ = ["generic_reviewer", "run_generic_reviewer"]

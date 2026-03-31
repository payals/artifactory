"""Research Lead Agent - Maps information terrain and gathers relevant material."""

import json
import logging
from typing import Any, Optional

from artifactforge.agents.llm_gateway import extract_json
from artifactforge.coordinator import artifacts as schemas
from artifactforge.coordinator.contracts import RESEARCH_LEAD_CONTRACT, agent_contract
from artifactforge.tools.research.deep_analyzer import run_deep_analyzer
from artifactforge.tools.research.web_searcher import SearchError, run_web_searcher

logger = logging.getLogger(__name__)


RESEARCH_LEAD_SYSTEM = """You are the Research Lead - an expert at mapping information terrain.

Your job is to gather relevant material and identify what matters, NOT to analyze or draw conclusions.

## Gathering Guidelines
1. Identify diverse source types: official, news, research, reference
2. Extract raw factual statements from fetched content
3. Note key dimensions that must be covered
4. Surface competing/conflicting views
5. Identify data gaps honestly
6. List follow-up questions

## What NOT to Do
- Do NOT analyze or draw conclusions
- Do NOT write content
- Do NOT limit to obvious sources
- Do NOT skip conflicting views

## Source Reliability Guidelines
- HIGH: Official sources, peer-reviewed research, primary data
- MEDIUM: News articles, industry reports, expert opinions
- LOW: Blogs, forums, unverified claims

## Output Format
Return JSON with sources, facts, key_dimensions, competing_views, data_gaps, followup_questions.
"""


@agent_contract(RESEARCH_LEAD_CONTRACT)
def run_research_lead(
    execution_brief: dict[str, Any],
    existing_research: Optional[dict[str, Any]] = None,
    repair_context: Optional[dict[str, Any]] = None,
) -> schemas.ResearchMap:
    """Run research lead to gather information based on execution brief.

    Uses web_searcher for real-time research and deep_analyzer for source content.

    Args:
        execution_brief: Output from Intent Architect
        existing_research: Optional existing research to build upon

    Returns:
        ResearchMap with gathered sources and facts
    """
    queries = _generate_search_queries(execution_brief)

    all_sources = []
    all_results = []
    deep_analyses = []
    search_errors = []

    for query in queries:
        try:
            search_result = run_web_searcher(query=query, num_results=5)
            sources = search_result.get("sources", [])
            results = search_result.get("results", [])
            all_sources.extend(sources)
            all_results.extend(results)
            analysis_sources = [url for url in sources if url][:3]
            if analysis_sources:
                analysis = run_deep_analyzer(sources=analysis_sources, query=query)
                deep_analyses.append(
                    {
                        "query": query,
                        "sources": analysis_sources,
                        "summary": analysis.get("summary", ""),
                        "key_findings": analysis.get("key_findings", []),
                    }
                )
        except SearchError as e:
            search_errors.append(
                {"query": query, "message": str(e), "errors": getattr(e, "errors", [])}
            )
            logger.warning("research_search_failed query=%s errors=%s", query, e.errors)

    prompt = _build_research_prompt(
        execution_brief,
        all_sources,
        all_results,
        deep_analyses,
        search_errors,
        existing_research,
        repair_context,
    )
    result = _call_llm(system=RESEARCH_LEAD_SYSTEM, prompt=prompt)

    try:
        parsed = json.loads(extract_json(result))
        sources = parsed.get("sources", [])
        for i, s in enumerate(sources):
            if not s.get("source_id"):
                s["source_id"] = f"SRC_{i + 1:03d}"
        logger.info(
            f"research_lead parsed: {len(sources)} sources, {len(parsed.get('facts', []))} facts"
        )
        return schemas.ResearchMap(
            sources=sources,
            facts=parsed.get("facts", []),
            key_dimensions=parsed.get("key_dimensions", []),
            competing_views=parsed.get("competing_views", []),
            data_gaps=parsed.get("data_gaps", []),
            followup_questions=parsed.get("followup_questions", []),
        )
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(
            f"research_lead JSON parse failed: {e}, result length: {len(result)}"
        )
        return _create_empty_research_map()


def _generate_search_queries(brief: dict[str, Any]) -> list[str]:
    """Generate search queries from execution brief."""
    user_goal = brief.get("user_goal", "")
    output_type = brief.get("output_type", "report")
    must_answer = brief.get("must_answer_questions", [])

    queries = []

    if user_goal:
        queries.append(user_goal)

    for q in must_answer[:3]:
        queries.append(q)

    queries.extend(
        [
            f"{user_goal} latest trends 2026",
            f"{user_goal} key facts statistics",
        ]
    )

    return queries[:5]


def _build_research_prompt(
    brief: dict[str, Any],
    sources: list[str],
    results: list[dict],
    deep_analyses: list[dict[str, Any]],
    search_errors: list[dict[str, Any]],
    existing: Optional[dict[str, Any]],
    repair_context: Optional[dict[str, Any]],
) -> str:
    brief_json = json.dumps(
        {
            "user_goal": brief.get("user_goal", ""),
            "output_type": brief.get("output_type", ""),
            "must_answer": brief.get("must_answer_questions", []),
            "missing_dimensions": brief.get("likely_missing_dimensions", []),
            "open_questions": brief.get("open_questions_to_resolve", []),
        },
        indent=2,
    )

    sources_text = ""
    if sources:
        sources_text = "\n## Search Results Found\n"
        for r in results[:10]:
            title = r.get("title", "")
            url = r.get("url", "")
            snippet = r.get("snippet", "")[:500]
            sources_text += f"- **{title}**\n  {url}\n  {snippet[:200]}...\n"

    existing_text = ""
    if existing:
        existing_text = (
            f"\n## Existing Research to Build Upon\n{json.dumps(existing, indent=2)}"
        )

    repair_text = ""
    if repair_context:
        repair_text = f"\n## Repair Context\n{json.dumps(repair_context, indent=2)}"

    deep_analysis_text = ""
    if deep_analyses:
        deep_analysis_text = "\n## Deep Source Analysis\n"
        for analysis in deep_analyses:
            findings = analysis.get("key_findings", [])
            deep_analysis_text += (
                f"- Query: {analysis.get('query', '')}\n"
                f"  Summary: {analysis.get('summary', '')}\n"
                f"  Findings: {json.dumps(findings[:5])}\n"
            )

    search_error_text = ""
    if search_errors:
        search_error_text = "\n## Search Errors Encountered\n" + json.dumps(
            search_errors, indent=2
        )

    return f"""## Execution Brief
{brief_json}
{sources_text}
{deep_analysis_text}
{search_error_text}
{existing_text}
{repair_text}

Analyze these search results and create a research map with sources, facts, key dimensions, competing views, and data gaps. Return JSON with:
- "sources": list of {{
  "source_id": str (e.g. "S001"),
  "title": str,
  "url": str or null,
  "source_type": one of "official", "news", "research", "reference", "internal", "other",
  "reliability": one of "HIGH", "MEDIUM", "LOW",
  "notes": str (key findings and relevance summary),
  "publish_date": str or null (ISO date if known)
}}
- "facts": list of str (verified facts from sources)
- "key_dimensions": list of str (dimensions to analyze)
- "competing_views": list of str (different perspectives found)
- "data_gaps": list of str (missing information)
- "followup_questions": list of str (questions for deeper research)"""


def _create_empty_research_map() -> schemas.ResearchMap:
    return schemas.ResearchMap(
        sources=[],
        facts=[],
        key_dimensions=[],
        competing_views=[],
        data_gaps=["No research available"],
        followup_questions=[],
    )


def _call_llm(system: str, prompt: str) -> str:
    from artifactforge.agents.llm_gateway import call_llm_sync

    return call_llm_sync(
        system_prompt=system, user_prompt=prompt, agent_name="research_lead"
    )


__all__ = ["run_research_lead", "RESEARCH_LEAD_CONTRACT"]

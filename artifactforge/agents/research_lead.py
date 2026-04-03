"""Research Lead Agent - Maps information terrain via multi-pass typed research.

Phase 1: Generate a research plan with LLM-inferred categories and typed queries
Phase 2: Execute three passes — landscape scan, deep source analysis, gap-filling
Phase 3: Synthesize into a ResearchMap for downstream agents
"""

import json
import logging
from typing import Any, Optional

from artifactforge.agents.llm_gateway import extract_json
from artifactforge.coordinator import artifacts as schemas
from artifactforge.coordinator.contracts import RESEARCH_LEAD_CONTRACT, agent_contract
from artifactforge.tools.research.deep_analyzer import run_deep_analyzer
from artifactforge.tools.research.web_searcher import SearchError, run_web_searcher

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

RESEARCH_PLAN_SYSTEM = """You are a research strategist. Given a user goal and execution brief, you produce a structured research plan.

Your job is to figure out WHAT information is needed and WHERE to look — not to answer the questions yourself.

## How to think about categories
Infer categories from the topic. Do NOT use a fixed list. Examples:
- A market analysis might need: demographic, competitive, regulatory, financial, cultural
- An AI research survey might need: academic_landscape, open_problems, key_players, technical_foundations, recent_breakthroughs
- A policy brief might need: legal_framework, stakeholder_positions, precedents, economic_impact, implementation_barriers
- A technical writeup might need: architecture, benchmarks, alternatives, limitations, deployment_considerations

## Query design principles
1. Each query should target a SPECIFIC piece of information, not a broad topic
2. Include location/context qualifiers (e.g. "Chincoteague Island population census" not "population statistics")
3. For competitive/landscape queries, target directories, listings, and databases — not generic articles
4. For quantitative data, target government, industry, or academic sources
5. For regulatory info, target .gov sites and official documents
6. Generate 8-15 queries covering all categories

## Output
Return JSON:
{
  "categories": ["category1", "category2", ...],
  "queries": [
    {
      "question": "What is the population and median income?",
      "search_query": "Chincoteague Island VA population median income census ACS",
      "category": "demographic",
      "priority": "HIGH",
      "why_needed": "Core market sizing data"
    }
  ],
  "research_depth": "shallow" | "medium" | "deep",
  "domain_context": "Brief description of the domain"
}"""

RESEARCH_LEAD_SYSTEM = """You are the Research Lead - an expert at mapping information terrain.

Your job is to synthesize gathered research material into a structured research map. You receive search results and deep source analyses from multiple research passes.

## Synthesis Guidelines
1. Extract SPECIFIC facts with numbers, dates, names — not vague summaries
2. Classify source reliability honestly (HIGH only for official/primary sources)
3. Note key dimensions that the downstream analysis MUST cover
4. Surface competing/conflicting views — don't smooth over disagreements
5. Identify data gaps honestly — what we searched for but couldn't find
6. List follow-up questions that deeper research could answer

## What NOT to Do
- Do NOT analyze or draw conclusions — that's the Analyst's job
- Do NOT invent facts that weren't in the search results
- Do NOT rate all sources as HIGH reliability — be discriminating
- Do NOT skip conflicting or inconvenient findings

## Source Reliability Guidelines
- HIGH: Official government data, peer-reviewed research, primary databases, official directories
- MEDIUM: News articles, industry reports, expert opinions, well-sourced blogs
- LOW: Forums, unverified claims, outdated sources, opinion pieces without data

## Output Format
Return JSON with sources, facts, key_dimensions, competing_views, data_gaps, followup_questions."""


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


@agent_contract(RESEARCH_LEAD_CONTRACT)
def run_research_lead(
    execution_brief: dict[str, Any],
    existing_research: Optional[dict[str, Any]] = None,
    repair_context: Optional[dict[str, Any]] = None,
    learnings_context: Optional[dict[str, Any]] = None,
) -> schemas.ResearchMap:
    """Run research lead with multi-pass typed research.

    1. Generate a research plan (LLM-inferred categories and queries)
    2. Pass 1: Landscape scan — run all queries via web search
    3. Pass 2: Deep source analysis — fetch and analyze top URLs
    4. Pass 3: Gap-fill — generate targeted queries for unanswered questions
    5. Synthesize everything into a ResearchMap
    """
    # Step 1: Generate research plan
    research_plan = _generate_research_plan(execution_brief, existing_research, repair_context)
    logger.info(
        "research_plan: %d categories, %d queries, depth=%s",
        len(research_plan.get("categories", [])),
        len(research_plan.get("queries", [])),
        research_plan.get("research_depth", "medium"),
    )

    # Step 2: Pass 1 — Landscape scan
    all_results, all_sources, search_errors = _pass_landscape_scan(research_plan)
    logger.info(
        "pass1_landscape: %d results, %d sources, %d errors",
        len(all_results), len(all_sources), len(search_errors),
    )

    # Step 3: Pass 2 — Deep source analysis on top URLs
    deep_analyses = _pass_deep_analysis(all_sources, research_plan)
    logger.info("pass2_deep: %d analyses", len(deep_analyses))

    # Step 4: Pass 3 — Gap-fill for unanswered questions
    gap_results, gap_sources, gap_errors = _pass_gap_fill(
        research_plan, all_results, deep_analyses, execution_brief
    )
    all_results.extend(gap_results)
    all_sources.extend(gap_sources)
    search_errors.extend(gap_errors)
    logger.info("pass3_gaps: %d additional results", len(gap_results))

    # Deep-analyze gap-fill sources too
    if gap_sources:
        gap_deep = _pass_deep_analysis(gap_sources, research_plan)
        deep_analyses.extend(gap_deep)

    # Step 5: Synthesize into ResearchMap
    prompt = _build_synthesis_prompt(
        execution_brief, all_results, deep_analyses, search_errors,
        existing_research, repair_context, learnings_context, research_plan,
    )
    result = _call_llm(system=RESEARCH_LEAD_SYSTEM, prompt=prompt)

    try:
        parsed = json.loads(extract_json(result))
        sources = parsed.get("sources", [])
        for i, s in enumerate(sources):
            if not s.get("source_id"):
                s["source_id"] = f"SRC_{i + 1:03d}"
        logger.info(
            "research_lead parsed: %d sources, %d facts",
            len(sources), len(parsed.get("facts", [])),
        )
        return schemas.ResearchMap(
            sources=sources,
            facts=parsed.get("facts", []),
            key_dimensions=parsed.get("key_dimensions", []),
            competing_views=parsed.get("competing_views", []),
            data_gaps=parsed.get("data_gaps", []),
            followup_questions=parsed.get("followup_questions", []),
            research_plan=research_plan,
        )
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("research_lead JSON parse failed: %s, len=%d", e, len(result))
        return _create_empty_research_map(research_plan)


# ---------------------------------------------------------------------------
# Step 1: Research plan generation
# ---------------------------------------------------------------------------


def _generate_research_plan(
    brief: dict[str, Any],
    existing_research: Optional[dict[str, Any]],
    repair_context: Optional[dict[str, Any]],
) -> schemas.ResearchPlan:
    """Ask the LLM to produce a typed research plan based on the execution brief."""
    brief_json = json.dumps(
        {
            "user_goal": brief.get("user_goal", ""),
            "output_type": brief.get("output_type", "report"),
            "audience": brief.get("audience", ""),
            "must_answer_questions": brief.get("must_answer_questions", []),
            "likely_missing_dimensions": brief.get("likely_missing_dimensions", []),
            "open_questions_to_resolve": brief.get("open_questions_to_resolve", []),
            "rigor_level": brief.get("rigor_level", "MEDIUM"),
            "decision_required": brief.get("decision_required", False),
        },
        indent=2,
    )

    existing_text = ""
    if existing_research:
        gaps = existing_research.get("data_gaps", [])
        if gaps:
            existing_text = f"\n## Known data gaps from prior research\n" + "\n".join(f"- {g}" for g in gaps)

    repair_text = ""
    if repair_context:
        repair_text = f"\n## Repair context\n{json.dumps(repair_context, indent=2)}"

    prompt = f"""## Execution Brief
{brief_json}
{existing_text}
{repair_text}

Generate a research plan. Infer the right categories for THIS specific topic — do not use generic categories. Each query should target a specific piece of information. Generate 8-15 queries."""

    result = _call_llm(system=RESEARCH_PLAN_SYSTEM, prompt=prompt)

    try:
        parsed = json.loads(extract_json(result))
        plan = schemas.ResearchPlan(
            categories=parsed.get("categories", ["general"]),
            queries=[
                schemas.ResearchQuery(
                    question=q.get("question", ""),
                    search_query=q.get("search_query", q.get("question", "")),
                    category=q.get("category", "general"),
                    priority=q.get("priority", "MEDIUM"),
                    why_needed=q.get("why_needed", ""),
                )
                for q in parsed.get("queries", [])
            ],
            research_depth=parsed.get("research_depth", "medium"),
            domain_context=parsed.get("domain_context", ""),
        )
        return plan
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("research_plan parse failed: %s", e)
        # Fallback: generate basic queries from the brief
        user_goal = brief.get("user_goal", "")
        return schemas.ResearchPlan(
            categories=["general"],
            queries=[
                schemas.ResearchQuery(
                    question=user_goal,
                    search_query=user_goal,
                    category="general",
                    priority="HIGH",
                    why_needed="Primary user goal",
                ),
                schemas.ResearchQuery(
                    question=f"Key facts about {user_goal}",
                    search_query=f"{user_goal} key facts statistics data",
                    category="general",
                    priority="MEDIUM",
                    why_needed="Supporting data",
                ),
            ],
            research_depth="medium",
            domain_context=user_goal,
        )


# ---------------------------------------------------------------------------
# Step 2: Pass 1 — Landscape scan
# ---------------------------------------------------------------------------


def _pass_landscape_scan(
    plan: schemas.ResearchPlan,
) -> tuple[list[dict], list[str], list[dict]]:
    """Execute all research plan queries via web search.

    Returns (results, source_urls, errors).
    """
    all_results: list[dict] = []
    all_sources: list[str] = []
    search_errors: list[dict] = []

    # Sort by priority: HIGH first
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    sorted_queries = sorted(
        plan.get("queries", []),
        key=lambda q: priority_order.get(q.get("priority", "MEDIUM"), 1),
    )

    for query in sorted_queries:
        search_text = query.get("search_query", query.get("question", ""))
        if not search_text:
            continue
        try:
            search_result = run_web_searcher(query=search_text)
            sources = search_result.get("sources", [])
            results = search_result.get("results", [])
            # Tag results with their category for later synthesis
            for r in results:
                r["_category"] = query.get("category", "general")
                r["_question"] = query.get("question", "")
            all_results.extend(results)
            all_sources.extend(sources)
        except SearchError as e:
            search_errors.append({
                "query": search_text,
                "category": query.get("category", "general"),
                "message": str(e),
                "errors": getattr(e, "errors", []),
            })
            logger.warning("search_failed query=%s category=%s", search_text, query.get("category"))

    # Deduplicate sources
    all_sources = list(dict.fromkeys(all_sources))
    return all_results, all_sources, search_errors


# ---------------------------------------------------------------------------
# Step 3: Pass 2 — Deep source analysis
# ---------------------------------------------------------------------------


def _pass_deep_analysis(
    source_urls: list[str],
    plan: schemas.ResearchPlan,
) -> list[dict[str, Any]]:
    """Fetch and deeply analyze the top URLs from the landscape scan."""
    depth = plan.get("research_depth", "medium")
    max_sources = {"shallow": 3, "medium": 8, "deep": 15}.get(depth, 8)

    urls_to_analyze = [url for url in source_urls if url][:max_sources]
    if not urls_to_analyze:
        return []

    deep_analyses = []
    domain_context = plan.get("domain_context", "")

    # Analyze in batches of 5 to avoid overwhelming the deep analyzer
    for batch_start in range(0, len(urls_to_analyze), 5):
        batch = urls_to_analyze[batch_start:batch_start + 5]
        try:
            analysis = run_deep_analyzer(
                sources=batch,
                query=domain_context,
            )
            deep_analyses.append({
                "sources": batch,
                "summary": analysis.get("summary", ""),
                "key_findings": analysis.get("key_findings", []),
            })
        except Exception as e:
            logger.warning("deep_analysis_failed batch=%s error=%s", batch, e)

    return deep_analyses


# ---------------------------------------------------------------------------
# Step 4: Pass 3 — Gap-fill
# ---------------------------------------------------------------------------


def _pass_gap_fill(
    plan: schemas.ResearchPlan,
    existing_results: list[dict],
    deep_analyses: list[dict[str, Any]],
    brief: dict[str, Any],
) -> tuple[list[dict], list[str], list[dict]]:
    """Identify unanswered questions and run targeted follow-up searches."""
    # Collect what we found so far
    found_snippets = " ".join(
        r.get("snippet", "") + " " + r.get("title", "")
        for r in existing_results[:20]
    )
    found_findings = " ".join(
        " ".join(a.get("key_findings", []))
        for a in deep_analyses
    )
    found_text = (found_snippets + " " + found_findings)[:3000]

    # Ask LLM what questions remain unanswered
    original_questions = [q.get("question", "") for q in plan.get("queries", [])]
    gap_prompt = f"""## Original research questions
{json.dumps(original_questions, indent=2)}

## What we found so far (summary)
{found_text}

## Task
Which of the original questions are NOT adequately answered by what we found? For each unanswered question, generate a more specific search query that might find the answer. Focus on the HIGH priority gaps.

Return JSON:
{{
  "unanswered": [
    {{
      "original_question": "...",
      "gap": "What specifically is missing",
      "refined_query": "A more specific search query to fill this gap"
    }}
  ]
}}"""

    gap_system = "You are a research gap analyst. Identify what information is still missing and suggest targeted searches to fill the gaps. Be specific — don't suggest broad searches."

    gap_result = _call_llm(system=gap_system, prompt=gap_prompt)

    all_results: list[dict] = []
    all_sources: list[str] = []
    search_errors: list[dict] = []

    try:
        parsed = json.loads(extract_json(gap_result))
        unanswered = parsed.get("unanswered", [])

        # Limit gap-fill to top 5 queries to stay within budget
        for gap in unanswered[:5]:
            query = gap.get("refined_query", "")
            if not query:
                continue
            try:
                search_result = run_web_searcher(query=query)
                sources = search_result.get("sources", [])
                results = search_result.get("results", [])
                for r in results:
                    r["_category"] = "gap_fill"
                    r["_question"] = gap.get("original_question", "")
                all_results.extend(results)
                all_sources.extend(sources)
            except SearchError as e:
                search_errors.append({
                    "query": query,
                    "category": "gap_fill",
                    "message": str(e),
                })

    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("gap_fill parse failed: %s", e)

    all_sources = list(dict.fromkeys(all_sources))
    return all_results, all_sources, search_errors


# ---------------------------------------------------------------------------
# Step 5: Synthesis prompt
# ---------------------------------------------------------------------------


def _build_synthesis_prompt(
    brief: dict[str, Any],
    results: list[dict],
    deep_analyses: list[dict[str, Any]],
    search_errors: list[dict[str, Any]],
    existing: Optional[dict[str, Any]],
    repair_context: Optional[dict[str, Any]],
    learnings_context: Optional[dict[str, Any]],
    research_plan: schemas.ResearchPlan,
) -> str:
    from artifactforge.agents.learnings_utils import build_learnings_section

    brief_json = json.dumps(
        {
            "user_goal": brief.get("user_goal", ""),
            "output_type": brief.get("output_type", ""),
            "must_answer": brief.get("must_answer_questions", []),
            "missing_dimensions": brief.get("likely_missing_dimensions", []),
        },
        indent=2,
    )

    # Group results by category for better synthesis
    results_by_category: dict[str, list[dict]] = {}
    for r in results:
        cat = r.get("_category", "general")
        results_by_category.setdefault(cat, []).append(r)

    results_text = ""
    for cat, cat_results in results_by_category.items():
        results_text += f"\n### Category: {cat}\n"
        for r in cat_results[:8]:
            title = r.get("title", "")
            url = r.get("url", "")
            snippet = r.get("snippet", "")[:500]
            question = r.get("_question", "")
            results_text += f"- **{title}**\n  {url}\n  Question: {question}\n  {snippet}\n"

    deep_text = ""
    if deep_analyses:
        deep_text = "\n## Deep Source Analysis\n"
        for analysis in deep_analyses:
            findings = analysis.get("key_findings", [])
            deep_text += (
                f"- Sources: {', '.join(analysis.get('sources', []))}\n"
                f"  Summary: {analysis.get('summary', '')}\n"
                f"  Findings: {json.dumps(findings[:8])}\n\n"
            )

    plan_text = f"\n## Research Plan (what we searched for)\n"
    for q in research_plan.get("queries", []):
        plan_text += f"- [{q.get('priority', '?')}] [{q.get('category', '?')}] {q.get('question', '')}\n"

    error_text = ""
    if search_errors:
        error_text = "\n## Searches that failed\n" + json.dumps(search_errors[:5], indent=2)

    existing_text = ""
    if existing:
        existing_text = f"\n## Existing research to build upon\n{json.dumps(existing, indent=2)}"

    repair_text = ""
    if repair_context:
        repair_text = f"\n## Repair context\n{json.dumps(repair_context, indent=2)}"

    learnings_text = build_learnings_section(learnings_context)

    return f"""## Execution Brief
{brief_json}
{plan_text}

## Search Results (grouped by category)
{results_text}
{deep_text}
{error_text}
{existing_text}
{repair_text}
{learnings_text}

Synthesize ALL the above into a research map. Extract SPECIFIC facts with exact numbers, dates, and names — not vague summaries. Return JSON with:
- "sources": list of {{"source_id": str, "title": str, "url": str|null, "source_type": "official"|"news"|"research"|"reference"|"internal"|"other", "reliability": "HIGH"|"MEDIUM"|"LOW", "notes": str, "publish_date": str|null}}
- "facts": list of str (specific factual statements with numbers/data)
- "key_dimensions": list of str (critical aspects the analysis must cover)
- "competing_views": list of str (conflicting perspectives found)
- "data_gaps": list of str (what we searched for but couldn't find)
- "followup_questions": list of str (questions for even deeper research)"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_empty_research_map(
    plan: Optional[schemas.ResearchPlan] = None,
) -> schemas.ResearchMap:
    return schemas.ResearchMap(
        sources=[],
        facts=[],
        key_dimensions=[],
        competing_views=[],
        data_gaps=["No research available"],
        followup_questions=[],
        research_plan=plan,
    )


def _call_llm(system: str, prompt: str) -> str:
    from artifactforge.agents.llm_gateway import call_llm_sync

    return call_llm_sync(
        system_prompt=system, user_prompt=prompt, agent_name="research_lead"
    )


__all__ = ["run_research_lead", "RESEARCH_LEAD_CONTRACT"]

"""LangGraph nodes - tool-powered implementations."""

import logging
from typing import Any

from artifactforge.coordinator.state import GraphState
from artifactforge.schemas.simple_report import build_simple_report_schema
from artifactforge.tools.research.web_searcher import SearchError, run_web_searcher
from artifactforge.tools.research.deep_analyzer import run_deep_analyzer
from artifactforge.tools.research.research_router import research_router
from artifactforge.tools.generic_generator import run_generic_generator
from artifactforge.tools.review.generic_reviewer import run_generic_reviewer

logger = logging.getLogger(__name__)


def router_node(state: GraphState) -> dict[str, Any]:
    """Route to appropriate workflow based on artifact type."""
    artifact_type = state.get("artifact_type", "simple_report")
    user_description = state.get("user_description", "")

    if artifact_type == "simple_report":
        return {"schema": build_simple_report_schema(user_description)}

    return {
        "schema": {"type": artifact_type},
    }


def research_node(state: GraphState) -> dict[str, Any]:
    """Research phase - uses ResearchRouter for intelligent strategy selection."""
    user_description = state.get("user_description", "")
    artifact_type = state.get("artifact_type", "simple_report")

    strategy = research_router.route(artifact_type, user_description)
    num_results = strategy.get_num_results()

    all_sources = []
    all_results = []

    for query in strategy.search_queries:
        try:
            search_result = run_web_searcher(query=query, num_results=num_results)
            sources = search_result.get("sources", [])
            results = search_result.get("results", [])
            all_sources.extend(sources)
            all_results.extend(results)
        except SearchError as e:
            logger.warning(f"Search failed for query '{query}': {e}")

    if all_sources:
        analysis_result = run_deep_analyzer(
            sources=all_sources[:10], query=user_description
        )
    else:
        analysis_result = {
            "key_findings": [],
            "summary": "No sources found",
        }

    return {
        "research_output": analysis_result,
        "research_sources": list(set(all_sources)),
    }


def generate_node(state: GraphState) -> dict[str, Any]:
    """Generation phase - calls GenericGenerator tool."""
    user_description = state.get("user_description", "")
    artifact_type = state.get("artifact_type", "simple_report")
    schema = state.get("schema") or {}
    research_output = state.get("research_output") or {}

    result = run_generic_generator(
        artifact_type=artifact_type,
        schema=schema,
        context=research_output,
        user_description=user_description,
    )

    return {
        "artifact_draft": result.get("draft", ""),
        "generation_metadata": result.get("metadata", {}),
    }


def review_node(state: GraphState) -> dict[str, Any]:
    """Review phase - calls GenericReviewer tool."""
    artifact_type = state.get("artifact_type", "simple_report")
    artifact_draft = state.get("artifact_draft") or ""
    research_output = state.get("research_output") or {}
    schema = state.get("schema") or {}

    result = run_generic_reviewer(
        artifact_type=artifact_type,
        draft=artifact_draft,
        context=research_output,
        schema=schema,
    )

    review_results = [
        {
            "passed": result.get("passed", False),
            "issues": result.get("issues", []),
            "suggestions": result.get("suggestions", []),
            "scores": result.get("scores", {}),
        }
    ]

    return {"review_results": review_results}


def verify_node(state: GraphState) -> dict[str, Any]:
    """Verification phase - checks review results."""
    review_results = state.get("review_results") or []
    all_passed = all(r.get("passed", False) for r in review_results)

    return {
        "verification_status": "passed" if all_passed else "failed",
    }


def ask_user_node(state: GraphState) -> dict[str, Any]:
    """Ask user questions - stub."""
    return {
        "user_questions": [],
    }


def error_node(state: GraphState) -> dict[str, Any]:
    """Handle errors - stub."""
    errors = list(state.get("errors") or [])
    errors.append("stub error")
    return {"errors": errors}


__all__ = [
    "router_node",
    "research_node",
    "generate_node",
    "review_node",
    "verify_node",
    "ask_user_node",
    "error_node",
]

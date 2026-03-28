"""LangGraph nodes - tool-powered implementations."""

from typing import Any

from artifactforge.coordinator.state import GraphState
from artifactforge.tools.research.web_searcher import web_searcher
from artifactforge.tools.research.deep_analyzer import deep_analyzer
from artifactforge.tools.generic_generator import generic_generator
from artifactforge.tools.review.generic_reviewer import generic_reviewer


def router_node(state: GraphState) -> dict[str, Any]:
    """Route to appropriate workflow based on artifact type."""
    artifact_type = state.get("artifact_type", "simple_report")
    return {
        "schema": {"type": artifact_type},
    }


def research_node(state: GraphState) -> dict[str, Any]:
    """Research phase - calls WebSearcher and DeepAnalyzer tools."""
    user_description = state.get("user_description", "")
    artifact_type = state.get("artifact_type", "simple_report")
    search_query = f"{artifact_type} {user_description}"

    search_result = web_searcher(query=search_query, num_results=5)
    sources = search_result.get("sources", [])

    if sources:
        analysis_result = deep_analyzer(sources=sources, query=search_query)
    else:
        analysis_result = {
            "analysis": {"key_findings": [], "summary": "No sources found"}
        }

    return {
        "research_output": analysis_result.get("analysis", {}),
        "research_sources": sources,
    }


def generate_node(state: GraphState) -> dict[str, Any]:
    """Generation phase - calls GenericGenerator tool."""
    user_description = state.get("user_description", "")
    artifact_type = state.get("artifact_type", "simple_report")
    schema = state.get("schema") or {}
    research_output = state.get("research_output") or {}

    result = generic_generator(
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

    result = generic_reviewer(
        artifact_type=artifact_type,
        draft=artifact_draft,
        context=research_output,
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

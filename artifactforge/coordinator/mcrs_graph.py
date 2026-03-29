"""MCRS LangGraph - 10-agent multi-agent content reasoning pipeline."""

from typing import Any, Literal, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from artifactforge.coordinator.state import MCRSState


MAX_REVISIONS = 3
MAX_RETRIES = 2


def create_mcrs_app(checkpointer: Optional[Any] = None) -> StateGraph:
    """Create the MCRS LangGraph application with 10 agents."""
    graph = StateGraph(MCRSState)

    graph.add_node("intent_architect", intent_architect_node)
    graph.add_node("research_lead", research_lead_node)
    graph.add_node("evidence_ledger", evidence_ledger_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("output_strategist", output_strategist_node)
    graph.add_node("draft_writer", draft_writer_node)
    graph.add_node("adversarial_reviewer", adversarial_reviewer_node)
    graph.add_node("verifier", verifier_node)
    graph.add_node("polisher", polisher_node)
    graph.add_node("final_arbiter", final_arbiter_node)

    graph.set_entry_point("intent_architect")

    graph.add_edge("intent_architect", "research_lead")
    graph.add_edge("research_lead", "evidence_ledger")
    graph.add_edge("evidence_ledger", "analyst")
    graph.add_edge("analyst", "output_strategist")
    graph.add_edge("output_strategist", "draft_writer")
    graph.add_edge("draft_writer", "adversarial_reviewer")

    graph.add_conditional_edges(
        "adversarial_reviewer",
        route_after_review,
        {
            "revise": "draft_writer",
            "verify": "verifier",
        },
    )

    graph.add_edge("verifier", "final_arbiter")

    graph.add_conditional_edges(
        "final_arbiter",
        route_after_arbiter,
        {
            "polish": "polisher",
            "revise_research": "research_lead",
            "revise_draft": "draft_writer",
            "end": END,
        },
    )

    graph.add_edge("polisher", END)

    compile_kwargs: dict[str, Any] = {}
    if checkpointer:
        compile_kwargs["checkpointer"] = checkpointer
    else:
        compile_kwargs["checkpointer"] = MemorySaver()

    return graph.compile(**compile_kwargs)


def intent_architect_node(state: MCRSState) -> dict[str, Any]:
    from artifactforge.agents import run_intent_architect

    result = run_intent_architect(
        user_prompt=state["user_prompt"],
        conversation_context=state.get("conversation_context"),
        output_constraints=state.get("output_constraints"),
    )
    return {"execution_brief": result, "current_stage": "intent_architect"}


def research_lead_node(state: MCRSState) -> dict[str, Any]:
    from artifactforge.agents import run_research_lead

    result = run_research_lead(
        execution_brief=state["execution_brief"],
    )
    return {"research_map": result, "current_stage": "research_lead"}


def evidence_ledger_node(state: MCRSState) -> dict[str, Any]:
    from artifactforge.agents import run_evidence_ledger

    result = run_evidence_ledger(
        research_map=state["research_map"],
    )
    return {"claim_ledger": result, "current_stage": "evidence_ledger"}


def analyst_node(state: MCRSState) -> dict[str, Any]:
    from artifactforge.agents import run_analyst

    result = run_analyst(
        execution_brief=state["execution_brief"],
        claim_ledger=state["claim_ledger"],
    )
    return {"analytical_backbone": result, "current_stage": "analyst"}


def output_strategist_node(state: MCRSState) -> dict[str, Any]:
    from artifactforge.agents import run_output_strategist

    result = run_output_strategist(
        execution_brief=state["execution_brief"],
        analytical_backbone=state["analytical_backbone"],
    )
    return {"content_blueprint": result, "current_stage": "output_strategist"}


def draft_writer_node(state: MCRSState) -> dict[str, Any]:
    from artifactforge.agents import run_draft_writer

    revision_count = len(state.get("revision_history", []))
    result = run_draft_writer(
        execution_brief=state["execution_brief"],
        claim_ledger=state["claim_ledger"],
        analytical_backbone=state["analytical_backbone"],
        content_blueprint=state["content_blueprint"],
    )
    return {
        "draft_v1": result,
        "draft_version": state.get("draft_version", 1),
        "revision_history": state.get("revision_history", [])
        + [
            {
                "version": revision_count + 1,
                "trigger": "draft",
                "changes_made": "Initial draft",
            }
        ],
        "current_stage": "draft_writer",
    }


def adversarial_reviewer_node(state: MCRSState) -> dict[str, Any]:
    from artifactforge.agents import run_adversarial_reviewer

    result = run_adversarial_reviewer(
        draft=state["draft_v1"] or "",
        claim_ledger=state["claim_ledger"],
        execution_brief=state["execution_brief"],
    )
    return {"red_team_review": result, "current_stage": "adversarial_reviewer"}


def verifier_node(state: MCRSState) -> dict[str, Any]:
    from artifactforge.agents import run_verifier

    result = run_verifier(
        draft=state["draft_v1"] or "",
        claim_ledger=state["claim_ledger"],
    )
    return {"verification_report": result, "current_stage": "verifier"}


def polisher_node(state: MCRSState) -> dict[str, Any]:
    from artifactforge.agents import run_polisher

    output_type = state.get("execution_brief", {}).get("output_type", "report")
    result = run_polisher(
        draft=state["draft_v1"] or "",
        output_type=output_type,
    )
    return {"polished_draft": result, "current_stage": "polisher"}


def final_arbiter_node(state: MCRSState) -> dict[str, Any]:
    from artifactforge.agents import run_final_arbiter

    result = run_final_arbiter(
        execution_brief=state["execution_brief"],
        draft=state["draft_v1"] or "",
        red_team_review=state["red_team_review"],
        verification_report=state["verification_report"],
    )
    return {"release_decision": result, "current_stage": "final_arbiter"}


def route_after_review(state: MCRSState) -> Literal["revise", "verify"]:
    review = state.get("red_team_review", {})
    issues = review.get("issues", [])
    high_severity = [i for i in issues if i.get("severity") == "HIGH"]
    revision_count = len(state.get("revision_history", []))

    if high_severity and revision_count < MAX_REVISIONS:
        return "revise"
    return "verify"


def route_after_arbiter(
    state: MCRSState,
) -> Literal["polish", "revise_research", "revise_draft", "end"]:
    decision = state.get("release_decision", {})
    status = decision.get("status", "NOT_READY")
    revision_count = len(state.get("revision_history", []))

    if status == "READY":
        return "polish"

    if revision_count >= MAX_REVISIONS:
        return "end"

    review = state.get("red_team_review", {})
    verification = state.get("verification_report", {})

    review_issues = [i for i in review.get("issues", []) if i.get("severity") == "HIGH"]
    unsupported = [
        i for i in verification.get("items", []) if i.get("status") == "UNSUPPORTED"
    ]

    if review_issues and not unsupported:
        return "revise_draft"

    return "revise_research"


mcrs_app = create_mcrs_app()

__all__ = ["create_mcrs_app", "mcrs_app", "MAX_REVISIONS", "MAX_RETRIES"]

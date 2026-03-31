"""MCRS LangGraph - 13-node multi-agent content reasoning pipeline."""

from pathlib import Path
from typing import Any, Literal, Optional, cast

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from artifactforge.coordinator.state import MCRSState
from artifactforge.observability.events import get_event_emitter
from artifactforge.observability.middleware import trace_node


MAX_REVISIONS = 3
RepairLocus = Literal[
    "intent_architect",
    "research_lead",
    "evidence_ledger",
    "analyst",
    "output_strategist",
    "draft_writer",
    "polisher",
    "visual_designer",
]


def _execution_brief(state: MCRSState) -> dict[str, Any]:
    return cast(dict[str, Any], state.get("execution_brief") or {})


def _review_issues(state: MCRSState) -> list[dict[str, Any]]:
    review = cast(dict[str, Any], state.get("red_team_review") or {})
    return cast(list[dict[str, Any]], review.get("issues") or [])


def _verification_items(state: MCRSState) -> list[dict[str, Any]]:
    verification = cast(dict[str, Any], state.get("verification_report") or {})
    return cast(list[dict[str, Any]], verification.get("items") or [])


def _emit_route_decision(
    state: MCRSState, from_node: str, to_node: str, reason: str
) -> None:
    trace_id = state.get("trace_id")
    if trace_id:
        get_event_emitter().emit_route(trace_id, from_node, to_node, reason)


def _repair_context_for_node(
    state: MCRSState, target_node: RepairLocus
) -> Optional[dict[str, Any]]:
    source_node = state.get("current_stage")
    if source_node not in {"adversarial_reviewer", "final_arbiter"}:
        return None

    review_issues = _review_issues(state)
    verification_items = _verification_items(state)
    decision = cast(dict[str, Any], state.get("release_decision") or {})

    if source_node == "adversarial_reviewer":
        relevant_review_issues = [
            issue for issue in review_issues if issue.get("severity") == "HIGH"
        ]
        if not relevant_review_issues or target_node != "draft_writer":
            return None
        return {
            "source_node": source_node,
            "target_node": target_node,
            "reason": "high_severity_review_issues",
            "review_issues": relevant_review_issues,
            "verification_items": [],
            "release_decision": None,
            "revision_count": len(state.get("revision_history", [])),
        }

    relevant_review_issues = [
        issue
        for issue in review_issues
        if issue.get("severity") == "HIGH" and issue.get("repair_locus") == target_node
    ]
    relevant_verification_items = [
        item
        for item in verification_items
        if item.get("status") == "UNSUPPORTED"
        and item.get("repair_locus") == target_node
    ]

    if not relevant_review_issues and not relevant_verification_items:
        return None

    return {
        "source_node": source_node,
        "target_node": target_node,
        "reason": "arbiter_repair_reroute",
        "review_issues": relevant_review_issues,
        "verification_items": relevant_verification_items,
        "release_decision": decision or None,
        "revision_count": len(state.get("revision_history", [])),
    }


def create_mcrs_app(checkpointer: Optional[Any] = None) -> Any:
    """Create the MCRS LangGraph application with 13 agents (10 core + 3 visual)."""
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
    graph.add_node("visual_designer", visual_designer_node)
    graph.add_node("visual_reviewer", visual_reviewer_node)
    graph.add_node("visual_generator", visual_generator_node)

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
            "intent_architect": "intent_architect",
            "research_lead": "research_lead",
            "evidence_ledger": "evidence_ledger",
            "analyst": "analyst",
            "output_strategist": "output_strategist",
            "draft_writer": "draft_writer",
            "polisher": "polisher",
            "visual_designer": "visual_designer",
            "end": END,
        },
    )

    graph.add_conditional_edges(
        "polisher",
        route_after_polisher,
        {
            "adversarial_reviewer": "adversarial_reviewer",
            "visual_designer": "visual_designer",
            "end": END,
        },
    )
    graph.add_edge("visual_designer", "visual_reviewer")
    graph.add_edge("visual_reviewer", "visual_generator")
    graph.add_edge("visual_generator", END)

    compile_kwargs: dict[str, Any] = {}
    if checkpointer:
        compile_kwargs["checkpointer"] = checkpointer
    else:
        compile_kwargs["checkpointer"] = MemorySaver()

    return graph.compile(**compile_kwargs)


@trace_node("intent_architect")
def intent_architect_node(state: MCRSState) -> dict[str, Any]:
    from artifactforge.agents import run_intent_architect

    repair_context = _repair_context_for_node(state, "intent_architect")
    result = run_intent_architect(
        user_prompt=state["user_prompt"],
        conversation_context=state.get("conversation_context"),
        output_constraints=state.get("output_constraints"),
        intent_mode=state.get("intent_mode", "auto"),
        answers_collected=state.get("answers_collected"),
        repair_context=repair_context,
        learnings_context=state.get("learnings_context"),
    )
    return {
        "execution_brief": result,
        "intent_mode": state.get("intent_mode", "auto"),
        "answers_collected": state.get("answers_collected", {}),
        "repair_context": repair_context,
    }


@trace_node("research_lead")
def research_lead_node(state: MCRSState) -> dict[str, Any]:
    from artifactforge.agents import run_research_lead

    repair_context = _repair_context_for_node(state, "research_lead")
    result = run_research_lead(
        execution_brief=state["execution_brief"],
        existing_research=state.get("research_map"),
        repair_context=repair_context,
        learnings_context=state.get("learnings_context"),
    )
    return {"research_map": result, "repair_context": repair_context}


@trace_node("evidence_ledger")
def evidence_ledger_node(state: MCRSState) -> dict[str, Any]:
    from artifactforge.agents import run_evidence_ledger

    repair_context = _repair_context_for_node(state, "evidence_ledger")
    result = run_evidence_ledger(
        research_map=state["research_map"],
        repair_context=repair_context,
        learnings_context=state.get("learnings_context"),
    )
    return {"claim_ledger": result, "repair_context": repair_context}


@trace_node("analyst")
def analyst_node(state: MCRSState) -> dict[str, Any]:
    from artifactforge.agents import run_analyst

    repair_context = _repair_context_for_node(state, "analyst")
    result = run_analyst(
        execution_brief=state["execution_brief"],
        claim_ledger=state["claim_ledger"],
        repair_context=repair_context,
        learnings_context=state.get("learnings_context"),
    )
    return {"analytical_backbone": result, "repair_context": repair_context}


@trace_node("output_strategist")
def output_strategist_node(state: MCRSState) -> dict[str, Any]:
    from artifactforge.agents import run_output_strategist

    repair_context = _repair_context_for_node(state, "output_strategist")
    result = run_output_strategist(
        execution_brief=state["execution_brief"],
        analytical_backbone=state["analytical_backbone"],
        repair_context=repair_context,
        learnings_context=state.get("learnings_context"),
    )
    return {"content_blueprint": result, "repair_context": repair_context}


@trace_node("draft_writer")
def draft_writer_node(state: MCRSState) -> dict[str, Any]:
    from artifactforge.agents import run_draft_writer

    revision_count = len(state.get("revision_history", []))
    repair_context = _repair_context_for_node(state, "draft_writer")
    result = run_draft_writer(
        execution_brief=state["execution_brief"],
        claim_ledger=state["claim_ledger"],
        analytical_backbone=state["analytical_backbone"],
        content_blueprint=state["content_blueprint"],
        repair_context=repair_context,
        learnings_context=state.get("learnings_context"),
    )
    from datetime import datetime

    revision_trigger = (
        repair_context.get("reason", "draft") if repair_context else "draft"
    )
    revision_changes = (
        f"Rerun from {repair_context.get('source_node', 'unknown')}"
        if repair_context
        else "Initial draft"
    )
    issues_addressed = (
        [issue.get("issue_id", "") for issue in repair_context.get("review_issues", [])]
        if repair_context
        else []
    )
    return {
        "draft_v1": result,
        "repair_context": repair_context,
        "revision_history": state.get("revision_history", [])
        + [
            {
                "version": revision_count + 1,
                "trigger": revision_trigger,
                "changes_made": revision_changes,
                "issues_addressed": issues_addressed,
                "timestamp": datetime.utcnow().isoformat(),
            }
        ],
    }


@trace_node("adversarial_reviewer")
def adversarial_reviewer_node(state: MCRSState) -> dict[str, Any]:
    from artifactforge.agents import run_adversarial_reviewer

    result = run_adversarial_reviewer(
        draft=state["draft_v1"] or "",
        claim_ledger=state["claim_ledger"],
        execution_brief=state["execution_brief"],
        learnings_context=state.get("learnings_context"),
    )
    return {"red_team_review": result, "repair_context": None}


@trace_node("verifier")
def verifier_node(state: MCRSState) -> dict[str, Any]:
    from artifactforge.agents import run_verifier

    result = run_verifier(
        draft=state["draft_v1"] or "",
        claim_ledger=state["claim_ledger"],
        learnings_context=state.get("learnings_context"),
    )
    return {"verification_report": result, "repair_context": None}


@trace_node("polisher")
def polisher_node(state: MCRSState) -> dict[str, Any]:
    from datetime import datetime

    from artifactforge.agents import run_polisher

    output_type = _execution_brief(state).get("output_type", "report")
    repair_context = _repair_context_for_node(state, "polisher")
    result = run_polisher(
        draft=state["draft_v1"] or "",
        output_type=output_type,
        repair_context=repair_context,
        learnings_context=state.get("learnings_context"),
    )
    updates: dict[str, Any] = {"polished_draft": result, "repair_context": repair_context}
    if repair_context:
        revision_count = len(state.get("revision_history", []))
        updates["draft_v1"] = result
        updates["revision_history"] = state.get("revision_history", []) + [
            {
                "version": revision_count + 1,
                "trigger": "polisher_repair",
                "changes_made": f"Polish repair from {repair_context.get('source_node', 'unknown')}",
                "issues_addressed": [
                    issue.get("issue_id", "")
                    for issue in repair_context.get("review_issues", [])
                ],
                "timestamp": datetime.utcnow().isoformat(),
            }
        ]
    return updates


@trace_node("final_arbiter")
def final_arbiter_node(state: MCRSState) -> dict[str, Any]:
    from artifactforge.agents import run_final_arbiter

    all_artifacts = {
        "execution_brief": state.get("execution_brief"),
        "research_map": state.get("research_map"),
        "claim_ledger": state.get("claim_ledger"),
        "analytical_backbone": state.get("analytical_backbone"),
        "content_blueprint": state.get("content_blueprint"),
        "red_team_review": state.get("red_team_review"),
        "verification_report": state.get("verification_report"),
    }

    result = run_final_arbiter(
        execution_brief=state["execution_brief"],
        draft=state["draft_v1"] or "",
        red_team_review=state["red_team_review"],
        verification_report=state["verification_report"],
        all_artifacts=all_artifacts,
        learnings_context=state.get("learnings_context"),
    )
    return {"release_decision": result, "repair_context": None}


@trace_node("visual_designer")
def visual_designer_node(state: MCRSState) -> dict[str, Any]:
    from artifactforge.agents import run_visual_designer

    polished = state.get("polished_draft") or state.get("draft_v1") or ""
    blueprint = state.get("content_blueprint")
    output_type = _execution_brief(state).get("output_type", "report")

    result = run_visual_designer(
        draft=polished,
        content_blueprint=blueprint,
        output_type=output_type,
    )
    return {"visual_specs": result or []}


@trace_node("visual_reviewer")
def visual_reviewer_node(state: MCRSState) -> dict[str, Any]:
    from artifactforge.agents import run_visual_reviewer

    specs = state.get("visual_specs", [])
    polished = state.get("polished_draft") or state.get("draft_v1") or ""

    result = run_visual_reviewer(visual_specs=specs, draft=polished)
    return {"visual_reviews": result or []}


def _embed_visuals_in_content(
    content: str, generated_visuals: list, specs: list
) -> str:
    """Insert visual image references into markdown content.

    Matches generated visuals to either:
    1. <!-- VISUAL: title --> comment anchors (replaced with image)
    2. Section headers matching section_anchor (image inserted after header)

    Args:
        content: The polished draft content
        generated_visuals: Generated visuals with image_path
        specs: Original visual specs with title and section_anchor

    Returns:
        Content with image references embedded
    """
    if not generated_visuals:
        return content

    import re as _re

    spec_map = {s.get("visual_id"): s for s in specs}

    # Build lookup from visual title/section_anchor to image markdown
    visual_images: list[tuple[str, str, str]] = []  # (title, section_anchor, md)
    for vis in generated_visuals:
        image_path = vis.get("image_path")
        if not image_path:
            continue
        # Use absolute path so PDF renderers (weasyprint, pandoc) can find the file
        abs_path = str(Path(image_path).resolve())
        spec = spec_map.get(vis.get("visual_id"), {})
        title = spec.get("title", vis.get("visual_id", "Visual"))
        anchor = spec.get("section_anchor", "")
        img_md = f"\n![{title}]({abs_path})\n"
        visual_images.append((title, anchor, img_md))

    if not visual_images:
        return content

    lines = content.split("\n")
    output_lines = []
    used_ids: set[int] = set()

    for line in lines:
        stripped = line.strip()

        # Check if this line is a <!-- VISUAL: ... --> comment
        comment_match = _re.match(r"^<!--\s*VISUAL:\s*(.+?)\s*-->$", stripped)
        if comment_match:
            comment_title = comment_match.group(1).lower()
            # Find best matching visual by title similarity
            best_idx = None
            best_score = 0
            for idx, (title, _anchor, _img_md) in enumerate(visual_images):
                if idx in used_ids:
                    continue
                # Check if titles share significant words
                title_words = set(title.lower().split())
                comment_words = set(comment_title.split())
                overlap = len(title_words & comment_words)
                if overlap > best_score:
                    best_score = overlap
                    best_idx = idx
            if best_idx is not None and best_score >= 1:
                used_ids.add(best_idx)
                output_lines.append(visual_images[best_idx][2])
                continue
            # No match — drop the comment anchor
            continue

        output_lines.append(line)

        # Also try section_anchor matching for visuals not yet placed
        header_match = _re.match(r"^#{1,6}\s+(.*)$", stripped)
        if header_match:
            header_text = header_match.group(1).strip()
            for idx, (title, anchor, img_md) in enumerate(visual_images):
                if idx in used_ids:
                    continue
                if anchor and (
                    header_text.lower() == anchor.lower()
                    or anchor.lower() in header_text.lower()
                ):
                    used_ids.add(idx)
                    output_lines.append(img_md)

    return "\n".join(output_lines)


@trace_node("visual_generator")
def visual_generator_node(state: MCRSState) -> dict[str, Any]:
    from artifactforge.agents import run_visual_generator

    # Clean stale visuals from previous runs
    visuals_dir = Path("outputs/visuals")
    if visuals_dir.exists():
        for old_file in visuals_dir.glob("visual_V*"):
            old_file.unlink()

    specs = state.get("visual_specs", [])
    reviews = state.get("visual_reviews", [])

    result = run_visual_generator(visual_specs=specs, approved_reviews=reviews)
    polished = state.get("polished_draft") or state.get("draft_v1") or ""

    final_with_visuals = _embed_visuals_in_content(polished, result or [], specs)

    return {
        "generated_visuals": result or [],
        "final_with_visuals": final_with_visuals,
    }


def route_after_review(state: MCRSState) -> Literal["revise", "verify"]:
    issues = _review_issues(state)
    high_severity = [i for i in issues if i.get("severity") == "HIGH"]
    revision_count = len(state.get("revision_history", []))

    if high_severity and revision_count < MAX_REVISIONS:
        _emit_route_decision(
            state,
            "adversarial_reviewer",
            "draft_writer",
            f"{len(high_severity)} HIGH severity review issue(s)",
        )
        return "revise"

    _emit_route_decision(
        state,
        "adversarial_reviewer",
        "verifier",
        "No blocking HIGH severity review issues",
    )
    return "verify"


def route_after_polisher(
    state: MCRSState,
) -> Literal["adversarial_reviewer", "visual_designer", "end"]:
    """Route polisher output based on whether it was invoked as repair."""
    repair_context = state.get("repair_context")
    if repair_context:
        _emit_route_decision(
            state,
            "polisher",
            "adversarial_reviewer",
            "Polisher ran as repair; re-verifying polished content",
        )
        return "adversarial_reviewer"

    blueprint = cast(dict[str, Any], state.get("content_blueprint") or {})
    visual_elements = blueprint.get("visual_elements", [])
    if visual_elements:
        _emit_route_decision(
            state,
            "polisher",
            "visual_designer",
            "Normal polisher flow; visual elements requested",
        )
        return "visual_designer"

    _emit_route_decision(
        state,
        "polisher",
        "end",
        "Normal polisher flow; no visual elements requested",
    )
    return "end"


def route_after_arbiter(
    state: MCRSState,
) -> Literal[
    "intent_architect",
    "research_lead",
    "evidence_ledger",
    "analyst",
    "output_strategist",
    "draft_writer",
    "polisher",
    "visual_designer",
    "end",
]:
    decision = cast(dict[str, Any], state.get("release_decision") or {})
    status = decision.get("status", "NOT_READY")
    revision_count = len(state.get("revision_history", []))

    if status == "READY":
        _emit_route_decision(
            state,
            "final_arbiter",
            "polisher",
            "Release marked READY; proceeding to polish",
        )
        return "polisher"

    if revision_count >= MAX_REVISIONS:
        _emit_route_decision(
            state,
            "final_arbiter",
            "polisher",
            f"Revision limit reached ({revision_count}/{MAX_REVISIONS}); proceeding to polish",
        )
        return "polisher"

    all_issues = []

    for issue in _review_issues(state):
        if issue.get("severity") == "HIGH":
            all_issues.append(issue)

    for item in _verification_items(state):
        if item.get("status") == "UNSUPPORTED":
            all_issues.append(item)

    if not all_issues:
        _emit_route_decision(
            state,
            "final_arbiter",
            "polisher",
            "No unresolved HIGH or UNSUPPORTED issues remain; proceeding to polish",
        )
        return "polisher"

    priority_order = [
        "intent_architect",
        "research_lead",
        "evidence_ledger",
        "analyst",
        "output_strategist",
        "draft_writer",
        "polisher",
        "visual_designer",
    ]

    for locus in priority_order:
        for issue in all_issues:
            repair_locus = issue.get("repair_locus", "")
            if repair_locus == locus:
                target = cast(RepairLocus, locus)
                _emit_route_decision(
                    state,
                    "final_arbiter",
                    target,
                    f"Rerouting to repair locus '{target}'",
                )
                return target

    _emit_route_decision(
        state,
        "final_arbiter",
        "draft_writer",
        "Falling back to draft_writer for unresolved issues",
    )
    return "draft_writer"


mcrs_app = create_mcrs_app()

__all__ = ["create_mcrs_app", "mcrs_app", "MAX_REVISIONS"]

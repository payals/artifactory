from typing import cast

from artifactforge.coordinator.mcrs_graph import (
    route_after_arbiter,
    route_after_polisher,
    route_after_review,
)
from artifactforge.coordinator.state import MCRSState
from artifactforge.observability.events import EventType


def test_route_after_review_emits_route_event(fresh_emitter) -> None:
    decision = route_after_review(
        cast(
            MCRSState,
            {
                "trace_id": "trace-review",
                "red_team_review": {
                    "issues": [{"severity": "HIGH", "repair_locus": "draft_writer"}]
                },
                "revision_history": [],
            },
        )
    )

    assert decision == "revise"
    route_events = fresh_emitter.get_events(
        trace_id="trace-review", event_type=EventType.ROUTE
    )
    assert len(route_events) == 1
    assert route_events[0].node_name == "adversarial_reviewer"
    assert route_events[0].route_target == "draft_writer"


def test_route_after_arbiter_emits_repair_locus_route(fresh_emitter) -> None:
    decision = route_after_arbiter(
        cast(
            MCRSState,
            {
                "trace_id": "trace-arbiter",
                "release_decision": {"status": "NOT_READY"},
                "revision_history": [],
                "red_team_review": {"issues": []},
                "verification_report": {
                    "items": [
                        {"status": "UNSUPPORTED", "repair_locus": "research_lead"}
                    ]
                },
            },
        )
    )

    assert decision == "research_lead"
    route_events = fresh_emitter.get_events(
        trace_id="trace-arbiter", event_type=EventType.ROUTE
    )
    assert len(route_events) == 1
    assert route_events[0].node_name == "final_arbiter"
    assert route_events[0].route_target == "research_lead"


def test_route_after_arbiter_ready_routes_to_polisher(fresh_emitter) -> None:
    """READY always routes to polisher first; visual check happens after polish."""
    decision = route_after_arbiter(
        cast(
            MCRSState,
            {
                "trace_id": "trace-ready-vis",
                "release_decision": {"status": "READY"},
                "revision_history": [],
                "red_team_review": {"issues": []},
                "verification_report": {"items": []},
                "content_blueprint": {
                    "visual_elements": [{"type": "chart", "description": "bar chart"}]
                },
            },
        )
    )

    assert decision == "polisher"
    route_events = fresh_emitter.get_events(
        trace_id="trace-ready-vis", event_type=EventType.ROUTE
    )
    assert len(route_events) == 1
    assert route_events[0].node_name == "final_arbiter"
    assert route_events[0].route_target == "polisher"


def test_route_after_polisher_repair(fresh_emitter) -> None:
    decision = route_after_polisher(
        cast(
            MCRSState,
            {
                "trace_id": "trace-polish-repair",
                "repair_context": {
                    "source_node": "final_arbiter",
                    "target_node": "polisher",
                    "review_issues": [{"issue_id": "R001"}],
                },
            },
        )
    )

    assert decision == "adversarial_reviewer"
    route_events = fresh_emitter.get_events(
        trace_id="trace-polish-repair", event_type=EventType.ROUTE
    )
    assert len(route_events) == 1
    assert route_events[0].node_name == "polisher"
    assert route_events[0].route_target == "adversarial_reviewer"


def test_route_after_polisher_normal_with_visuals(fresh_emitter) -> None:
    decision = route_after_polisher(
        cast(
            MCRSState,
            {
                "trace_id": "trace-polish-normal",
                "repair_context": None,
                "content_blueprint": {
                    "visual_elements": [{"type": "chart"}]
                },
            },
        )
    )

    assert decision == "visual_designer"
    route_events = fresh_emitter.get_events(
        trace_id="trace-polish-normal", event_type=EventType.ROUTE
    )
    assert len(route_events) == 1
    assert route_events[0].node_name == "polisher"
    assert route_events[0].route_target == "visual_designer"


def test_route_after_polisher_normal_no_visuals(fresh_emitter) -> None:
    decision = route_after_polisher(
        cast(
            MCRSState,
            {
                "trace_id": "trace-polish-novis",
                "repair_context": None,
                "content_blueprint": {"visual_elements": []},
            },
        )
    )

    assert decision == "end"
    route_events = fresh_emitter.get_events(
        trace_id="trace-polish-novis", event_type=EventType.ROUTE
    )
    assert len(route_events) == 1
    assert route_events[0].node_name == "polisher"
    assert route_events[0].route_target == "end"

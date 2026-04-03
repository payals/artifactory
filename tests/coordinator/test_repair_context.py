from typing import cast

from artifactforge.coordinator.mcrs_graph import draft_writer_node, research_lead_node
from artifactforge.coordinator.state import MCRSState


def test_research_lead_node_passes_existing_research_and_repair_context(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "artifactforge.agents.run_research_lead",
        lambda execution_brief, existing_research=None, repair_context=None, learnings_context=None: (
            captured.update(
                {
                    "execution_brief": execution_brief,
                    "existing_research": existing_research,
                    "repair_context": repair_context,
                }
            )
            or {"sources": []}
        ),
    )

    result = research_lead_node(
        cast(
            MCRSState,
            {
                "current_stage": "final_arbiter",
                "execution_brief": {"user_goal": "Need research"},
                "research_map": {"facts": ["existing"]},
                "red_team_review": {"issues": []},
                "verification_report": {
                    "items": [
                        {"status": "UNSUPPORTED", "repair_locus": "research_lead"}
                    ]
                },
                "release_decision": {"status": "NOT_READY"},
                "revision_history": [],
            },
        )
    )

    assert captured["existing_research"] == {"facts": ["existing"]}
    assert captured["repair_context"] == {
        "source_node": "final_arbiter",
        "target_node": "research_lead",
        "reason": "arbiter_repair_reroute",
        "review_issues": [],
        "verification_items": [
            {"status": "UNSUPPORTED", "repair_locus": "research_lead"}
        ],
        "release_decision": {"status": "NOT_READY"},
        "revision_count": 0,
    }
    assert result["repair_context"]["target_node"] == "research_lead"


def test_draft_writer_node_records_review_repair_trigger(monkeypatch) -> None:
    monkeypatch.setattr(
        "artifactforge.agents.run_draft_writer",
        lambda execution_brief, claim_ledger, analytical_backbone, content_blueprint, repair_context=None, learnings_context=None, taper_context=None: (
            "draft"
        ),
    )

    result = draft_writer_node(
        cast(
            MCRSState,
            {
                "current_stage": "adversarial_reviewer",
                "execution_brief": {"user_goal": "Need draft"},
                "claim_ledger": {"claims": []},
                "analytical_backbone": {"key_findings": []},
                "content_blueprint": {"structure": []},
                "red_team_review": {
                    "issues": [
                        {
                            "severity": "HIGH",
                            "repair_locus": "draft_writer",
                            "issue": "Missing support",
                        }
                    ]
                },
                "revision_history": [],
            },
        )
    )

    assert result["repair_context"]["source_node"] == "adversarial_reviewer"
    assert result["revision_history"][0]["trigger"] == "high_severity_review_issues"

"""Tests for the Agent Contract Validation System.

Imports are deferred inside test functions to avoid a circular import chain:
validation.py -> llm_gateway -> agents/__init__ -> final_arbiter -> validation.py
"""

import json

import pytest

from artifactforge.coordinator.contracts import AGENT_REGISTRY, AgentContract


@pytest.fixture(autouse=True)
def _restore_registry():
    """Save and restore AGENT_REGISTRY to prevent cross-test pollution."""
    original = dict(AGENT_REGISTRY)
    yield
    AGENT_REGISTRY.clear()
    AGENT_REGISTRY.update(original)


def _register_test_contract() -> AgentContract:
    """Register a dummy contract for testing."""
    contract = AgentContract(
        name="test_validator_agent",
        mission="Test mission for validation",
        inputs=["input_a"],
        required_output_schema=dict,
        forbidden_behaviors=["Do not crash"],
        pass_fail_criteria=["Output must have key_field", "Output must be non-empty"],
    )
    AGENT_REGISTRY[contract.name] = contract
    return contract


# ---------------------------------------------------------------------------
# validate_agent_output
# ---------------------------------------------------------------------------


def test_validate_agent_output_unknown_agent(monkeypatch) -> None:
    monkeypatch.setattr(
        "artifactforge.agents.llm_gateway.call_llm_sync",
        lambda **kw: "{}",
    )
    from artifactforge.coordinator.validation import validate_agent_output

    result = validate_agent_output("no_such_agent_xyz", {"x": 1}, "test")

    assert result["overall_passed"] is False
    assert "No contract found" in result["notes"]


def test_validate_agent_output_valid_llm_response(monkeypatch) -> None:
    _register_test_contract()

    llm_response = json.dumps(
        {
            "agent_name": "test_validator_agent",
            "artifact_type": "test_output",
            "criteria_results": [
                {
                    "criteria": "Output must have key_field",
                    "satisfied": True,
                    "reasoning": "key_field present",
                    "severity": "HIGH",
                }
            ],
            "overall_passed": True,
            "notes": "All good",
        }
    )
    monkeypatch.setattr(
        "artifactforge.coordinator.validation.call_llm_sync",
        lambda **kw: llm_response,
    )
    from artifactforge.coordinator.validation import validate_agent_output

    result = validate_agent_output(
        "test_validator_agent", {"key_field": "value"}, "test_output"
    )

    assert result["overall_passed"] is True
    assert len(result["criteria_results"]) == 1


def test_validate_agent_output_invalid_json_from_llm(monkeypatch) -> None:
    _register_test_contract()

    monkeypatch.setattr(
        "artifactforge.coordinator.validation.call_llm_sync",
        lambda **kw: "not valid json {{{",
    )
    from artifactforge.coordinator.validation import validate_agent_output

    result = validate_agent_output(
        "test_validator_agent", {"key_field": "value"}, "test_output"
    )

    assert result["overall_passed"] is False
    assert "could not parse" in result["notes"]


def test_validate_agent_output_passes_correct_prompt(monkeypatch) -> None:
    contract = _register_test_contract()
    captured: dict = {}

    def fake_llm(**kwargs):
        captured.update(kwargs)
        return json.dumps({"overall_passed": True, "criteria_results": []})

    monkeypatch.setattr(
        "artifactforge.coordinator.validation.call_llm_sync", fake_llm
    )
    from artifactforge.coordinator.validation import validate_agent_output

    validate_agent_output(
        "test_validator_agent", {"data": "test_value"}, "test_output"
    )

    prompt = captured.get("user_prompt", "")
    assert contract.mission in prompt
    assert "test_value" in prompt
    assert "Output must have key_field" in prompt


# ---------------------------------------------------------------------------
# validate_all_agents
# ---------------------------------------------------------------------------


def test_validate_all_agents_processes_present_artifacts(monkeypatch) -> None:
    for name in ("intent_architect", "research_lead"):
        AGENT_REGISTRY[name] = AgentContract(
            name=name,
            mission=f"Mission for {name}",
            inputs=[],
            required_output_schema=dict,
            forbidden_behaviors=[],
            pass_fail_criteria=["criteria"],
        )

    call_count = {"n": 0}
    agent_names = ["intent_architect", "research_lead"]

    def fake_llm(**kw):
        idx = min(call_count["n"], len(agent_names) - 1)
        name = agent_names[idx]
        call_count["n"] += 1
        return json.dumps(
            {
                "agent_name": name,
                "artifact_type": "test",
                "criteria_results": [],
                "overall_passed": True,
                "notes": "",
            }
        )

    monkeypatch.setattr(
        "artifactforge.coordinator.validation.call_llm_sync", fake_llm
    )
    from artifactforge.coordinator.validation import validate_all_agents

    state = {
        "execution_brief": {"user_goal": "test"},
        "research_map": {"sources": []},
    }

    results = validate_all_agents(state)
    validated_agents = [r["agent_name"] for r in results]

    assert "intent_architect" in validated_agents
    assert "research_lead" in validated_agents
    assert len(results) == 2


def test_validate_all_agents_skips_none_artifacts(monkeypatch) -> None:
    AGENT_REGISTRY["intent_architect"] = AgentContract(
        name="intent_architect",
        mission="m",
        inputs=[],
        required_output_schema=dict,
        forbidden_behaviors=[],
        pass_fail_criteria=[],
    )

    monkeypatch.setattr(
        "artifactforge.coordinator.validation.call_llm_sync",
        lambda **kw: json.dumps({"overall_passed": True, "criteria_results": []}),
    )
    from artifactforge.coordinator.validation import validate_all_agents

    state = {"execution_brief": None}
    results = validate_all_agents(state)
    assert len(results) == 0


def test_validate_all_agents_empty_state(monkeypatch) -> None:
    monkeypatch.setattr(
        "artifactforge.coordinator.validation.call_llm_sync",
        lambda **kw: "{}",
    )
    from artifactforge.coordinator.validation import validate_all_agents

    results = validate_all_agents({})
    assert results == []

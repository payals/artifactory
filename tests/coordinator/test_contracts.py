"""Tests for the Agent Contract System — registration, retrieval, and predefined contracts."""

import pytest

from artifactforge.coordinator.contracts import (
    AGENT_REGISTRY,
    AgentContract,
    agent_contract,
    get_agent_contract,
    list_agents,
)


@pytest.fixture(autouse=True)
def _restore_registry():
    """Save and restore AGENT_REGISTRY to prevent cross-test pollution."""
    original = dict(AGENT_REGISTRY)
    yield
    AGENT_REGISTRY.clear()
    AGENT_REGISTRY.update(original)


# ---------------------------------------------------------------------------
# Decorator & registry
# ---------------------------------------------------------------------------


def test_agent_contract_decorator_registers_agent() -> None:
    contract = AgentContract(
        name="test_agent",
        mission="Test mission",
        inputs=["a"],
        required_output_schema=dict,
        forbidden_behaviors=["none"],
        pass_fail_criteria=["always pass"],
    )

    @agent_contract(contract)
    def dummy_fn():
        return "ok"

    assert "test_agent" in AGENT_REGISTRY
    assert AGENT_REGISTRY["test_agent"] is contract


def test_agent_contract_decorator_sets_execute() -> None:
    contract = AgentContract(
        name="exec_test",
        mission="m",
        inputs=[],
        required_output_schema=dict,
        forbidden_behaviors=[],
        pass_fail_criteria=[],
    )

    @agent_contract(contract)
    def my_func():
        return 42

    assert contract.execute is my_func


def test_get_agent_contract_existing() -> None:
    contract = AgentContract(
        name="lookup_test",
        mission="m",
        inputs=[],
        required_output_schema=dict,
        forbidden_behaviors=[],
        pass_fail_criteria=[],
    )
    AGENT_REGISTRY["lookup_test"] = contract

    result = get_agent_contract("lookup_test")
    assert result is contract


def test_get_agent_contract_nonexistent() -> None:
    assert get_agent_contract("no_such_agent_xyz") is None


def test_list_agents_returns_registered_names() -> None:
    AGENT_REGISTRY["alpha"] = AgentContract(
        name="alpha",
        mission="m",
        inputs=[],
        required_output_schema=dict,
        forbidden_behaviors=[],
        pass_fail_criteria=[],
    )
    AGENT_REGISTRY["beta"] = AgentContract(
        name="beta",
        mission="m",
        inputs=[],
        required_output_schema=dict,
        forbidden_behaviors=[],
        pass_fail_criteria=[],
    )

    names = list_agents()
    assert "alpha" in names
    assert "beta" in names


# ---------------------------------------------------------------------------
# Predefined contracts
# ---------------------------------------------------------------------------

_ALL_PREDEFINED_CONTRACTS = [
    "INTENT_ARCHITECT_CONTRACT",
    "RESEARCH_LEAD_CONTRACT",
    "EVIDENCE_LEDGER_CONTRACT",
    "ANALYST_CONTRACT",
    "OUTPUT_STRATEGIST_CONTRACT",
    "DRAFT_WRITER_CONTRACT",
    "ADVERSARIAL_REVIEWER_CONTRACT",
    "VERIFIER_CONTRACT",
    "POLISHER_CONTRACT",
    "FINAL_ARBITER_CONTRACT",
    "VISUAL_DESIGNER_CONTRACT",
    "VISUAL_REVIEWER_CONTRACT",
    "VISUAL_GENERATOR_CONTRACT",
]


def test_predefined_contracts_have_required_fields() -> None:
    import artifactforge.coordinator.contracts as mod

    for attr_name in _ALL_PREDEFINED_CONTRACTS:
        c = getattr(mod, attr_name)
        assert isinstance(c, AgentContract), f"{attr_name} is not AgentContract"
        assert c.name, f"{attr_name}.name is empty"
        assert c.mission, f"{attr_name}.mission is empty"
        assert isinstance(c.inputs, list), f"{attr_name}.inputs not a list"
        assert c.required_output_schema is not None, (
            f"{attr_name}.required_output_schema is None"
        )
        assert len(c.forbidden_behaviors) > 0, (
            f"{attr_name}.forbidden_behaviors is empty"
        )
        assert len(c.pass_fail_criteria) > 0, (
            f"{attr_name}.pass_fail_criteria is empty"
        )


def test_predefined_contract_names_are_unique() -> None:
    import artifactforge.coordinator.contracts as mod

    names = [getattr(mod, attr).name for attr in _ALL_PREDEFINED_CONTRACTS]
    assert len(names) == len(set(names)), f"Duplicate names: {names}"


def test_all_agents_register_when_imported() -> None:
    """Importing all agent modules should populate the registry with all 13 agents."""
    import importlib

    # Agent modules register via @agent_contract decorators at import time.
    # Since imports are cached, we need to reload the __init__ that triggers them.
    import artifactforge.agents as agents_pkg

    importlib.reload(agents_pkg)

    expected = {
        "intent_architect",
        "research_lead",
        "evidence_ledger",
        "analyst",
        "output_strategist",
        "draft_writer",
        "adversarial_reviewer",
        "verifier",
        "polisher",
        "final_arbiter",
        "visual_designer",
        "visual_reviewer",
        "visual_generator",
    }
    registered = set(AGENT_REGISTRY.keys())
    missing = expected - registered
    assert not missing, f"Agents not registered: {missing}"

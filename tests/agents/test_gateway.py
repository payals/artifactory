"""Tests for LLM Gateway model routing."""

import pytest
from artifactforge.agents.llm_gateway import (
    MODEL_REGISTRY,
    AGENT_TO_MODEL,
    resolve_model,
    model_candidates_for_agent,
    get_agent_temperature,
)


class TestModelRegistry:
    def test_registry_has_required_models(self):
        assert "default" in MODEL_REGISTRY
        assert "reasoning" in MODEL_REGISTRY
        assert "deep_reasoning" in MODEL_REGISTRY
        assert "coding" in MODEL_REGISTRY
        assert "review" in MODEL_REGISTRY
        assert "fallback_1" in MODEL_REGISTRY
        assert "fallback_2" in MODEL_REGISTRY

    def test_registry_values_are_openrouter_model_ids(self):
        for key, model_id in MODEL_REGISTRY.items():
            assert "/" in model_id, f"{key} should have a namespace like z-ai/ or qwen/"


class TestAgentRouting:
    def test_intent_architect_routes_to_reasoning(self):
        assert AGENT_TO_MODEL["intent_architect"] == "reasoning"

    def test_research_lead_routes_to_reasoning(self):
        assert AGENT_TO_MODEL["research_lead"] == "reasoning"

    def test_analyst_routes_to_deep_reasoning(self):
        assert AGENT_TO_MODEL["analyst"] == "deep_reasoning"

    def test_coding_writer_routes_to_coding(self):
        assert AGENT_TO_MODEL["coding_writer"] == "coding"

    def test_adversarial_reviewer_routes_to_review(self):
        assert AGENT_TO_MODEL["adversarial_reviewer"] == "review"

    def test_verifier_routes_to_verification(self):
        assert AGENT_TO_MODEL["verifier"] == "verification"


class TestResolveModel:
    def test_resolve_known_agent(self):
        model = resolve_model("analyst")
        assert model == MODEL_REGISTRY["deep_reasoning"]

    def test_resolve_unknown_agent_uses_default(self):
        model = resolve_model("unknown_agent_xyz")
        assert model == MODEL_REGISTRY["default"]

    def test_resolve_coding_writer(self):
        model = resolve_model("coding_writer")
        assert model == MODEL_REGISTRY["coding"]


class TestModelCandidates:
    def test_candidates_includes_primary_and_fallbacks(self):
        candidates = model_candidates_for_agent("analyst")
        assert len(candidates) >= 2
        assert candidates[0] == MODEL_REGISTRY["deep_reasoning"]

    def test_candidates_are_deduplicated(self):
        candidates = model_candidates_for_agent("analyst")
        unique_candidates = list(dict.fromkeys(candidates))
        assert candidates == unique_candidates

    def test_unknown_agent_uses_default_model(self):
        candidates = model_candidates_for_agent("unknown_agent")
        assert candidates[0] == MODEL_REGISTRY["default"]


class TestAgentTemperatures:
    def test_known_agents_have_temperatures(self):
        assert get_agent_temperature("intent_architect") == 0.1
        assert get_agent_temperature("research_lead") == 0.2
        assert get_agent_temperature("verifier") == 0.0

    def test_unknown_agent_uses_default(self):
        assert get_agent_temperature("unknown_agent") == 0.7

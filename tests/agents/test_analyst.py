import pytest
from artifactforge.agents.analyst import (
    run_analyst,
    _build_analyst_prompt,
    _create_default_analysis,
)


class TestBuildAnalystPrompt:
    def test_prompt_includes_brief_fields(self):
        brief = {
            "user_goal": "Analyze market trends",
            "decision_required": True,
            "rigor_level": "HIGH",
        }
        claims = {}
        prompt = _build_analyst_prompt(brief, claims, None)
        assert "Analyze market trends" in prompt
        assert "decision_required" in prompt
        assert "HIGH" in prompt

    def test_prompt_includes_claims_summary(self):
        brief = {"user_goal": "Goal", "decision_required": False}
        claims = {
            "claims": [
                {"classification": "VERIFIED", "claim_text": "Fact 1"},
                {"classification": "ASSUMED", "claim_text": "Assumption 1"},
            ]
        }
        prompt = _build_analyst_prompt(brief, claims, None)
        assert "Claim Ledger" in prompt
        assert "Fact 1" in prompt

    def test_prompt_includes_repair_context(self):
        brief = {"user_goal": "Goal"}
        claims = {}
        repair = {"source_node": "final_arbiter", "reason": "revision_needed"}
        prompt = _build_analyst_prompt(brief, claims, repair)
        assert "Repair Context" in prompt
        assert "final_arbiter" in prompt

    def test_prompt_handles_empty_claims(self):
        brief = {"user_goal": "Goal"}
        claims = {"claims": []}
        prompt = _build_analyst_prompt(brief, claims, None)
        assert "Claim Ledger" not in prompt


class TestCreateDefaultAnalysis:
    def test_default_analysis_structure(self):
        brief = {"decision_required": False}
        result = _create_default_analysis(brief)
        assert result["key_findings"] == ["Analysis pending"]
        assert result["open_unknowns"] == ["Analysis not completed"]
        assert result["recommendation_logic"] == []

    def test_default_analysis_includes_recommendation_when_decision_required(self):
        brief = {"decision_required": True}
        result = _create_default_analysis(brief)
        assert result["recommendation_logic"] == ["Recommendation pending"]


class TestRunAnalyst:
    def test_successful_analysis(self, monkeypatch):
        mock_response = """{
            "key_findings": ["Finding 1"],
            "primary_drivers": ["Driver 1"],
            "implications": ["Implication 1"],
            "risks": ["Risk 1"],
            "sensitivities": ["Sensitivity 1"],
            "counterarguments": ["Counter 1"],
            "recommendation_logic": ["Logic 1"],
            "open_unknowns": ["Unknown 1"]
        }"""
        monkeypatch.setattr(
            "artifactforge.agents.analyst._call_llm",
            lambda system, prompt: mock_response,
        )
        result = run_analyst(
            execution_brief={"user_goal": "Goal", "decision_required": True},
            claim_ledger={"claims": []},
        )
        assert result["key_findings"] == ["Finding 1"]
        assert result["risks"] == ["Risk 1"]
        assert result["counterarguments"] == ["Counter 1"]

    def test_llm_failure_returns_fallback(self, monkeypatch):
        monkeypatch.setattr(
            "artifactforge.agents.analyst._call_llm",
            lambda system, prompt: "invalid json",
        )
        result = run_analyst(
            execution_brief={"user_goal": "Goal", "decision_required": False},
            claim_ledger={"claims": []},
        )
        assert result["key_findings"] == ["Analysis pending"]
        assert result["open_unknowns"] == ["Analysis not completed"]

    def test_analysis_with_repair_context(self, monkeypatch):
        captured = []
        monkeypatch.setattr(
            "artifactforge.agents.analyst._call_llm",
            lambda system, prompt: captured.append(prompt) or "{}",
        )
        run_analyst(
            execution_brief={"user_goal": "Goal"},
            claim_ledger={"claims": []},
            repair_context={"source_node": "verifier"},
        )
        assert "Repair Context" in captured[0]
        assert "verifier" in captured[0]

    def test_contract_is_registered(self):
        from artifactforge.coordinator.contracts import ANALYST_CONTRACT, AGENT_REGISTRY

        assert "analyst" in AGENT_REGISTRY
        assert ANALYST_CONTRACT.name == "analyst"

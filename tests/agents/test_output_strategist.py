from artifactforge.agents.output_strategist import (
    run_output_strategist,
    _build_strategy_prompt,
    _create_default_blueprint,
)


class TestBuildStrategyPrompt:
    def test_prompt_includes_brief_fields(self):
        brief = {"output_type": "report", "audience": "executives", "tone": "formal"}
        prompt = _build_strategy_prompt(brief, None, None)
        assert "report" in prompt
        assert "executives" in prompt

    def test_prompt_includes_analysis_summary(self):
        brief = {"output_type": "blog"}
        analysis = {
            "key_findings": ["Finding 1", "Finding 2"],
            "risks": ["Risk 1"],
            "recommendation_logic": ["Logic 1"],
        }
        prompt = _build_strategy_prompt(brief, analysis, None)
        assert "Finding 1" in prompt
        assert "Risk 1" in prompt

    def test_prompt_handles_none_analysis(self):
        brief = {"output_type": "report"}
        prompt = _build_strategy_prompt(brief, None, None)
        assert "key_findings" in prompt

    def test_prompt_handles_invalid_analysis(self):
        brief = {"output_type": "report"}
        prompt = _build_strategy_prompt(brief, analysis=None, repair_context=None)
        assert "key_findings" in prompt

    def test_prompt_includes_repair_context(self):
        brief = {"output_type": "report"}
        repair = {"source_node": "analyst"}
        prompt = _build_strategy_prompt(brief, None, repair)
        assert "Repair Context" in prompt


class TestCreateDefaultBlueprint:
    def test_report_structure(self):
        brief = {"output_type": "report"}
        bp = _create_default_blueprint(brief)
        assert "Introduction" in bp["structure"]
        assert "Findings" in bp["structure"]
        assert "Recommendation" in bp["structure"]

    def test_blog_structure(self):
        brief = {"output_type": "blog"}
        bp = _create_default_blueprint(brief)
        assert "Hook" in bp["structure"]
        assert "Body" in bp["structure"]

    def test_slides_structure(self):
        brief = {"output_type": "slides"}
        bp = _create_default_blueprint(brief)
        assert "Title" in bp["structure"]
        assert "Problem" in bp["structure"]

    def test_unknown_type_fallback(self):
        brief = {"output_type": "unknown_type"}
        bp = _create_default_blueprint(brief)
        assert bp["structure"] == ["Section 1", "Section 2"]


class TestRunOutputStrategist:
    def test_successful_strategy(self, monkeypatch):
        mock_response = """{
            "structure": ["Intro", "Body", "Conclusion"],
            "section_purposes": {"Intro": "Set context"},
            "narrative_flow": "Linear progression",
            "visual_elements": [{"type": "table"}],
            "key_takeaways": ["Key point 1"],
            "audience_guidance": ["Read carefully"]
        }"""
        monkeypatch.setattr(
            "artifactforge.agents.output_strategist._call_llm",
            lambda system, prompt: mock_response,
        )
        result = run_output_strategist(
            execution_brief={"output_type": "report"},
            analytical_backbone={"key_findings": [], "risks": []},
        )
        assert result["structure"] == ["Intro", "Body", "Conclusion"]
        assert result["key_takeaways"] == ["Key point 1"]

    def test_llm_failure_returns_fallback(self, monkeypatch):
        monkeypatch.setattr(
            "artifactforge.agents.output_strategist._call_llm",
            lambda system, prompt: "not json",
        )
        result = run_output_strategist(
            execution_brief={"output_type": "report"},
            analytical_backbone={},
        )
        assert "Introduction" in result["structure"]

    def test_contract_is_registered(self):
        from artifactforge.coordinator.contracts import (
            OUTPUT_STRATEGIST_CONTRACT,
            AGENT_REGISTRY,
        )

        assert "output_strategist" in AGENT_REGISTRY
        assert OUTPUT_STRATEGIST_CONTRACT.name == "output_strategist"

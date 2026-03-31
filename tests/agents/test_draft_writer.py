from artifactforge.agents.draft_writer import (
    run_draft_writer,
    _build_draft_prompt,
)


class TestBuildDraftPrompt:
    def test_prompt_includes_brief_fields(self):
        brief = {
            "output_type": "report",
            "audience": "Executives",
            "tone": "professional",
            "user_goal": "Analyze market",
        }
        claims = {"claims": []}
        analysis = {}
        blueprint = {"structure": ["Intro", "Body"], "key_takeaways": ["Takeaway 1"]}
        prompt = _build_draft_prompt(brief, claims, analysis, blueprint, None)
        assert "report" in prompt
        assert "Executives" in prompt
        assert "Analyze market" in prompt

    def test_prompt_includes_blueprint(self):
        brief = {"output_type": "blog"}
        claims = {"claims": []}
        analysis = {}
        blueprint = {"structure": ["Hook", "Body", "Conclusion"], "key_takeaways": []}
        prompt = _build_draft_prompt(brief, claims, analysis, blueprint, None)
        assert "Hook" in prompt
        assert "Body" in prompt

    def test_prompt_includes_claims(self):
        brief = {"output_type": "report"}
        claims = {
            "claims": [
                {"classification": "VERIFIED", "claim_text": "Verified fact"},
                {"classification": "ASSUMED", "claim_text": "Assumed point"},
            ]
        }
        analysis = {}
        blueprint = {"structure": [], "key_takeaways": []}
        prompt = _build_draft_prompt(brief, claims, analysis, blueprint, None)
        assert "Claims to Use" in prompt
        assert "Verified fact" in prompt

    def test_prompt_includes_analysis(self):
        brief = {"output_type": "report"}
        claims = {"claims": []}
        analysis = {
            "key_findings": ["Finding 1"],
            "risks": ["Risk 1"],
            "recommendation_logic": ["Logic 1"],
        }
        blueprint = {"structure": [], "key_takeaways": []}
        prompt = _build_draft_prompt(brief, claims, analysis, blueprint, None)
        assert "Finding 1" in prompt
        assert "Risk 1" in prompt

    def test_prompt_includes_repair_context(self):
        brief = {"output_type": "report"}
        claims = {"claims": []}
        analysis = {}
        blueprint = {"structure": [], "key_takeaways": []}
        repair = {"source_node": "adversarial_reviewer"}
        prompt = _build_draft_prompt(brief, claims, analysis, blueprint, repair)
        assert "Repair Context" in prompt


class TestRunDraftWriter:
    def test_successful_draft_generation(self, monkeypatch):
        monkeypatch.setattr(
            "artifactforge.agents.draft_writer._call_llm",
            lambda system, prompt: "# Draft Title\n\nDraft body content.",
        )
        result = run_draft_writer(
            execution_brief={"output_type": "report", "audience": "General"},
            claim_ledger={"claims": []},
            analytical_backbone={"key_findings": [], "risks": []},
            content_blueprint={"structure": ["Intro"], "key_takeaways": []},
        )
        assert result == "# Draft Title\n\nDraft body content."

    def test_draft_strips_whitespace(self, monkeypatch):
        monkeypatch.setattr(
            "artifactforge.agents.draft_writer._call_llm",
            lambda system, prompt: "  \n  Draft content  \n  ",
        )
        result = run_draft_writer(
            execution_brief={},
            claim_ledger={"claims": []},
            analytical_backbone={},
            content_blueprint={},
        )
        assert result == "Draft content"

    def test_draft_with_repair_context(self, monkeypatch):
        captured = []
        monkeypatch.setattr(
            "artifactforge.agents.draft_writer._call_llm",
            lambda system, prompt: captured.append(prompt) or "Draft",
        )
        run_draft_writer(
            execution_brief={},
            claim_ledger={"claims": []},
            analytical_backbone={},
            content_blueprint={},
            repair_context={"issues": ["Fix this"]},
        )
        assert "Repair Context" in captured[0]

    def test_contract_is_registered(self):
        from artifactforge.coordinator.contracts import (
            DRAFT_WRITER_CONTRACT,
            AGENT_REGISTRY,
        )

        assert "draft_writer" in AGENT_REGISTRY
        assert DRAFT_WRITER_CONTRACT.name == "draft_writer"

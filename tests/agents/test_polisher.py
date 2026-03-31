from artifactforge.agents.polisher import (
    run_polisher,
    _build_polish_prompt,
)


class TestBuildPolishPrompt:
    def test_prompt_includes_draft(self):
        prompt = _build_polish_prompt("Draft content", "report", None)
        assert "Draft content" in prompt

    def test_prompt_includes_target_format(self):
        prompt = _build_polish_prompt("Draft", "slides", None)
        assert "slides" in prompt

    def test_prompt_includes_repair_context(self):
        repair = {"source_node": "verifier"}
        prompt = _build_polish_prompt("Draft", "report", repair)
        assert "Repair Context" in prompt
        assert "verifier" in prompt


class TestRunPolisher:
    def test_successful_polish(self, monkeypatch):
        monkeypatch.setattr(
            "artifactforge.agents.polisher._call_llm",
            lambda system, prompt: "Polished version with better flow.",
        )
        result = run_polisher(draft="Rough draft", output_type="report")
        assert result == "Polished version with better flow."

    def test_polish_strips_surrounding_whitespace(self, monkeypatch):
        monkeypatch.setattr(
            "artifactforge.agents.polisher._call_llm",
            lambda system, prompt: "  \n  Polished  \n  ",
        )
        result = run_polisher(draft="Draft", output_type="report")
        assert result == "Polished"

    def test_polish_with_repair_context(self, monkeypatch):
        captured = []
        monkeypatch.setattr(
            "artifactforge.agents.polisher._call_llm",
            lambda system, prompt: captured.append(prompt) or "Polished",
        )
        run_polisher(
            draft="Draft",
            output_type="blog",
            repair_context={"issues": ["Fix tone"]},
        )
        assert "Repair Context" in captured[0]

    def test_contract_is_registered(self):
        from artifactforge.coordinator.contracts import (
            POLISHER_CONTRACT,
            AGENT_REGISTRY,
        )

        assert "polisher" in AGENT_REGISTRY
        assert POLISHER_CONTRACT.name == "polisher"

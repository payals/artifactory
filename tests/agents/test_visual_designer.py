from artifactforge.agents.visual_designer import (
    run_visual_designer,
    _build_visual_prompt,
    _normalize_spec,
)


class TestBuildVisualPrompt:
    def test_prompt_includes_draft(self):
        prompt = _build_visual_prompt("Draft content", None, "report")
        assert "Draft content" in prompt

    def test_prompt_includes_output_type(self):
        prompt = _build_visual_prompt("Draft", None, "slides")
        assert "slides" in prompt

    def test_prompt_includes_blueprint_structure(self):
        blueprint = {"structure": ["Intro", "Analysis", "Conclusion"]}
        prompt = _build_visual_prompt("Draft", blueprint, "report")
        assert "Content Structure" in prompt
        assert "Intro" in prompt

    def test_prompt_handles_empty_blueprint(self):
        blueprint = {"structure": []}
        prompt = _build_visual_prompt("Draft", blueprint, "report")
        assert "Content Structure" in prompt


class TestNormalizeSpec:
    def test_simple_visual_gets_simple_complexity(self):
        spec = {
            "visual_type": "flowchart",
            "title": "Process Flow",
            "section_anchor": "Intro",
            "description": "Shows the process",
            "data_spec": {},
            "mermaid_code": "graph TD; A-->B;",
        }
        result = _normalize_spec(spec, 0)
        assert result["complexity"] == "SIMPLE"
        assert result["mermaid_code"] == "graph TD; A-->B;"

    def test_complex_visual_gets_complex_complexity(self):
        spec = {
            "visual_type": "bar_chart",
            "title": "Sales Chart",
            "section_anchor": "Data",
            "description": "Sales data",
            "data_spec": {"data": {"values": [1, 2, 3]}},
        }
        result = _normalize_spec(spec, 0)
        assert result["complexity"] == "COMPLEX"
        assert result["mermaid_code"] is None

    def test_all_simple_types(self):
        simple_types = [
            "flowchart",
            "sequence_diagram",
            "org_chart",
            "timeline",
            "gantt_chart",
            "concept_diagram",
        ]
        for vtype in simple_types:
            spec = {
                "visual_type": vtype,
                "title": "Test",
                "section_anchor": "S",
                "description": "D",
                "data_spec": {},
            }
            result = _normalize_spec(spec, 0)
            assert result["complexity"] == "SIMPLE", f"Failed for {vtype}"

    def test_generates_visual_id_when_missing(self):
        spec = {"visual_type": "bar_chart"}
        result = _normalize_spec(spec, 2)
        assert result["visual_id"] == "V003"

    def test_preserves_existing_id(self):
        spec = {"visual_id": "V042", "visual_type": "bar_chart"}
        result = _normalize_spec(spec, 0)
        assert result["visual_id"] == "V042"


class TestRunVisualDesigner:
    def test_returns_visual_specs(self, monkeypatch):
        mock_response = """[
            {
                "visual_id": "V001",
                "section_anchor": "Introduction",
                "visual_type": "flowchart",
                "title": "Process Flow",
                "description": "Shows the workflow",
                "data_spec": {},
                "mermaid_code": "graph TD; A-->B;",
                "placeholder_position": "after_first_paragraph"
            }
        ]"""
        monkeypatch.setattr(
            "artifactforge.agents.visual_designer._call_llm",
            lambda system, prompt: mock_response,
        )
        result = run_visual_designer(draft="Draft with process description")
        assert len(result) == 1
        assert result[0]["visual_id"] == "V001"
        assert result[0]["complexity"] == "SIMPLE"

    def test_returns_empty_list_on_llm_failure(self, monkeypatch):
        monkeypatch.setattr(
            "artifactforge.agents.visual_designer._call_llm",
            lambda system, prompt: "not json",
        )
        result = run_visual_designer(draft="Draft")
        assert result == []

    def test_returns_empty_list_on_non_array_response(self, monkeypatch):
        monkeypatch.setattr(
            "artifactforge.agents.visual_designer._call_llm",
            lambda system, prompt: '{"key": "value"}',
        )
        result = run_visual_designer(draft="Draft")
        assert result == []

    def test_passes_blueprint_to_prompt(self, monkeypatch):
        captured = []
        monkeypatch.setattr(
            "artifactforge.agents.visual_designer._call_llm",
            lambda system, prompt: captured.append(prompt) or "[]",
        )
        blueprint = {"structure": ["Section A", "Section B"]}
        run_visual_designer(draft="Draft", content_blueprint=blueprint)
        assert "Section A" in captured[0]

    def test_contract_is_registered(self):
        from artifactforge.coordinator.contracts import (
            VISUAL_DESIGNER_CONTRACT,
            AGENT_REGISTRY,
        )

        assert "visual_designer" in AGENT_REGISTRY
        assert VISUAL_DESIGNER_CONTRACT.name == "visual_designer"

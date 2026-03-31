from artifactforge.agents.visual_reviewer import (
    run_visual_reviewer,
    _build_review_prompt,
    _normalize_review,
)


class TestBuildReviewPrompt:
    def test_prompt_includes_visual_specs(self):
        specs = [
            {
                "visual_id": "V001",
                "visual_type": "flowchart",
                "title": "Process Flow",
            }
        ]
        prompt = _build_review_prompt(specs, "Draft")
        assert "V001" in prompt
        assert "flowchart" in prompt

    def test_prompt_includes_draft_context(self):
        specs = [{"visual_id": "V001"}]
        prompt = _build_review_prompt(specs, "Document with section Analysis")
        assert "Document with section Analysis" in prompt


class TestNormalizeReview:
    def test_defaults_for_missing_fields(self):
        review = {}
        result = _normalize_review(review)
        assert result["visual_id"] == ""
        assert result["is_appropriate"] is True
        assert result["clarity_score"] == 0.5
        assert result["data_accuracy"] == 0.5
        assert result["placement_correct"] is True
        assert result["issues"] == []
        assert result["suggestions"] == []

    def test_preserves_provided_values(self):
        review = {
            "visual_id": "V001",
            "is_appropriate": False,
            "clarity_score": 0.3,
            "data_accuracy": 0.7,
            "placement_correct": False,
            "issues": ["Wrong placement"],
            "suggestions": ["Move to intro"],
        }
        result = _normalize_review(review)
        assert result["visual_id"] == "V001"
        assert result["is_appropriate"] is False
        assert result["clarity_score"] == 0.3
        assert result["data_accuracy"] == 0.7
        assert result["placement_correct"] is False
        assert result["issues"] == ["Wrong placement"]
        assert result["suggestions"] == ["Move to intro"]


class TestRunVisualReviewer:
    def test_returns_empty_for_empty_specs(self):
        result = run_visual_reviewer(visual_specs=[], draft="Draft")
        assert result == []

    def test_returns_reviews(self, monkeypatch):
        mock_response = """[
            {
                "visual_id": "V001",
                "is_appropriate": true,
                "clarity_score": 0.9,
                "data_accuracy": 0.8,
                "placement_correct": true,
                "issues": [],
                "suggestions": ["Consider adding labels"]
            }
        ]"""
        monkeypatch.setattr(
            "artifactforge.agents.visual_reviewer._call_llm",
            lambda system, prompt: mock_response,
        )
        specs = [
            {
                "visual_id": "V001",
                "visual_type": "flowchart",
                "title": "Process",
                "section_anchor": "Intro",
                "description": "Shows process",
                "data_spec": {},
                "complexity": "SIMPLE",
                "mermaid_code": "graph TD; A-->B;",
                "placeholder_position": "after_first_paragraph",
            }
        ]
        result = run_visual_reviewer(visual_specs=specs, draft="Draft")
        assert len(result) == 1
        assert result[0]["visual_id"] == "V001"
        assert result[0]["is_appropriate"] is True
        assert result[0]["clarity_score"] == 0.9

    def test_returns_empty_on_llm_failure(self, monkeypatch):
        monkeypatch.setattr(
            "artifactforge.agents.visual_reviewer._call_llm",
            lambda system, prompt: "not json",
        )
        specs = [{"visual_id": "V001"}]
        result = run_visual_reviewer(visual_specs=specs, draft="Draft")
        assert result == []

    def test_returns_empty_on_non_array_response(self, monkeypatch):
        monkeypatch.setattr(
            "artifactforge.agents.visual_reviewer._call_llm",
            lambda system, prompt: '{"key": "value"}',
        )
        specs = [{"visual_id": "V001"}]
        result = run_visual_reviewer(visual_specs=specs, draft="Draft")
        assert result == []

    def test_contract_is_registered(self):
        from artifactforge.coordinator.contracts import (
            VISUAL_REVIEWER_CONTRACT,
            AGENT_REGISTRY,
        )

        assert "visual_reviewer" in AGENT_REGISTRY
        assert VISUAL_REVIEWER_CONTRACT.name == "visual_reviewer"

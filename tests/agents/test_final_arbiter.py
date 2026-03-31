from artifactforge.agents.final_arbiter import (
    run_final_arbiter,
    _build_arbiter_prompt,
)


class TestBuildArbiterPrompt:
    def test_prompt_includes_brief_summary(self):
        brief = {
            "user_goal": "Ship product",
            "must_answer_questions": ["What is the cost?"],
            "decision_required": True,
        }
        prompt = _build_arbiter_prompt(brief, "", {}, {}, [])
        assert "Ship product" in prompt
        assert "What is the cost?" in prompt

    def test_prompt_includes_review_summary_with_issues(self):
        review = {
            "issues": [
                {"severity": "HIGH"},
                {"severity": "MEDIUM"},
            ],
            "passed": False,
        }
        prompt = _build_arbiter_prompt({}, "", review, {}, [])
        assert "issues_count" in prompt
        assert "high_severity" in prompt

    def test_prompt_includes_no_issues_when_review_clean(self):
        review = {"issues": [], "passed": True}
        prompt = _build_arbiter_prompt({}, "", review, {}, [])
        assert "No issues" in prompt

    def test_prompt_includes_verification_summary(self):
        verification = {
            "items": [
                {"status": "SUPPORTED"},
                {"status": "UNSUPPORTED"},
            ],
            "passed": False,
        }
        prompt = _build_arbiter_prompt({}, "", {}, verification, [])
        assert "unsupported" in prompt
        assert "total_checked" in prompt

    def test_prompt_includes_validation_results(self):
        validations = [
            {"agent": "analyst", "passed": True},
            {"agent": "draft_writer", "passed": False},
        ]
        prompt = _build_arbiter_prompt({}, "", {}, {}, validations)
        assert "analyst" in prompt
        assert "draft_writer" in prompt

    def test_draft_is_included(self):
        prompt = _build_arbiter_prompt({}, "Draft excerpt", {}, {}, [])
        assert "Draft excerpt" in prompt


class TestRunFinalArbiter:
    def test_ready_decision(self, monkeypatch):
        mock_response = """{
            "status": "READY",
            "confidence": 0.95,
            "remaining_risks": [],
            "known_gaps": [],
            "notes": "All criteria met"
        }"""
        monkeypatch.setattr(
            "artifactforge.agents.final_arbiter._call_llm",
            lambda system, prompt: mock_response,
        )
        monkeypatch.setattr(
            "artifactforge.agents.final_arbiter.validate_all_agents",
            lambda artifacts: [],
        )
        result = run_final_arbiter(
            execution_brief={"user_goal": "Goal"},
            draft="Clean draft",
            red_team_review={"issues": [], "passed": True},
            verification_report={"items": [], "passed": True},
            all_artifacts={},
        )
        assert result["status"] == "READY"
        assert result["confidence"] == 0.95

    def test_not_ready_decision(self, monkeypatch):
        mock_response = """{
            "status": "NOT_READY",
            "confidence": 0.4,
            "remaining_risks": ["Unresolved HIGH issue"],
            "known_gaps": ["Missing recommendation"],
            "notes": "Critical issues remain"
        }"""
        monkeypatch.setattr(
            "artifactforge.agents.final_arbiter._call_llm",
            lambda system, prompt: mock_response,
        )
        monkeypatch.setattr(
            "artifactforge.agents.final_arbiter.validate_all_agents",
            lambda artifacts: [],
        )
        result = run_final_arbiter(
            execution_brief={"user_goal": "Goal"},
            draft="Draft",
            red_team_review={"issues": [{"severity": "HIGH"}], "passed": False},
            verification_report={"items": [], "passed": True},
            all_artifacts={},
        )
        assert result["status"] == "NOT_READY"
        assert "Unresolved HIGH issue" in result["remaining_risks"]

    def test_llm_failure_returns_fallback(self, monkeypatch):
        monkeypatch.setattr(
            "artifactforge.agents.final_arbiter._call_llm",
            lambda system, prompt: "not json",
        )
        monkeypatch.setattr(
            "artifactforge.agents.final_arbiter.validate_all_agents",
            lambda artifacts: [],
        )
        result = run_final_arbiter(
            execution_brief={},
            draft="",
            red_team_review={},
            verification_report={},
            all_artifacts={},
        )
        assert result["status"] == "NOT_READY"
        assert result["confidence"] == 0.0

    def test_contract_is_registered(self):
        from artifactforge.coordinator.contracts import (
            FINAL_ARBITER_CONTRACT,
            AGENT_REGISTRY,
        )

        assert "final_arbiter" in AGENT_REGISTRY
        assert FINAL_ARBITER_CONTRACT.name == "final_arbiter"

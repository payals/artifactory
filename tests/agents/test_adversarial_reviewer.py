"""Tests for Adversarial Reviewer Agent."""

import pytest
from artifactforge.agents.adversarial_reviewer import (
    run_adversarial_reviewer,
    _build_review_prompt,
    ADVERSARIAL_REVIEWER_SYSTEM,
)


class TestBuildReviewPrompt:
    def test_prompt_includes_brief_summary(self):
        brief = {"user_goal": "Test goal", "audience": "Executives"}
        draft = "Some draft content"
        claims = {}

        prompt = _build_review_prompt(draft, claims, brief)

        assert "Test goal" in prompt
        assert "Executives" in prompt

    def test_prompt_includes_draft_excerpt(self):
        brief = {"user_goal": "Goal", "audience": "Audience"}
        draft = "Draft excerpt here"
        claims = {}

        prompt = _build_review_prompt(draft, claims, brief)

        assert "Draft excerpt here" in prompt

    def test_prompt_includes_assumed_claims(self):
        brief = {"user_goal": "Goal", "audience": "Audience"}
        draft = "Draft"
        claims = {
            "claims": [
                {"classification": "ASSUMED", "claim_text": "This is an assumption"},
                {"classification": "VERIFIED", "claim_text": "This is verified"},
            ]
        }

        prompt = _build_review_prompt(draft, claims, brief)

        assert "ASSUMED Claims" in prompt
        assert "This is an assumption" in prompt

    def test_prompt_handles_empty_claims(self):
        brief = {"user_goal": "Goal", "audience": "Audience"}
        draft = "Draft"
        claims = {"claims": []}

        prompt = _build_review_prompt(draft, claims, brief)

        assert "ASSUMED Claims" not in prompt

    def test_prompt_handles_missing_claims_key(self):
        brief = {"user_goal": "Goal", "audience": "Audience"}
        draft = "Draft"
        claims = {}

        prompt = _build_review_prompt(draft, claims, brief)

        assert "ASSUMED Claims" not in prompt


class TestRunAdversarialReviewer:
    def test_successful_review_with_issues(self, monkeypatch):
        mock_response = """{
            "issues": [
                {
                    "issue_id": "R001",
                    "severity": "HIGH",
                    "section": "Introduction",
                    "problem_type": "unsupported_claim",
                    "repair_locus": "draft_writer",
                    "explanation": "Claim lacks evidence",
                    "suggested_fix": "Add supporting data"
                }
            ],
            "overall_assessment": "Draft has significant issues",
            "passed": false
        }"""
        monkeypatch.setattr(
            "artifactforge.agents.adversarial_reviewer._call_llm",
            lambda system, prompt: mock_response,
        )

        result = run_adversarial_reviewer(
            draft="Test draft",
            claim_ledger={"claims": []},
            execution_brief={"user_goal": "Goal", "audience": "Audience"},
        )

        assert len(result["issues"]) == 1
        assert result["issues"][0]["severity"] == "HIGH"
        assert result["passed"] is False
        assert result["overall_assessment"] == "Draft has significant issues"

    def test_successful_review_passes(self, monkeypatch):
        mock_response = """{
            "issues": [
                {
                    "issue_id": "R001",
                    "severity": "LOW",
                    "section": "Body",
                    "problem_type": "poor_structure",
                    "repair_locus": "polisher",
                    "explanation": "Minor formatting issue",
                    "suggested_fix": "Fix formatting"
                }
            ],
            "overall_assessment": "Mostly solid",
            "passed": true
        }"""
        monkeypatch.setattr(
            "artifactforge.agents.adversarial_reviewer._call_llm",
            lambda system, prompt: mock_response,
        )

        result = run_adversarial_reviewer(
            draft="Test draft",
            claim_ledger={"claims": []},
            execution_brief={"user_goal": "Goal", "audience": "Audience"},
        )

        assert result["passed"] is True
        assert len(result["issues"]) == 1

    def test_auto_generates_issue_id_when_missing(self, monkeypatch):
        mock_response = """{
            "issues": [
                {
                    "severity": "MEDIUM",
                    "section": "Body",
                    "problem_type": "shallow_analysis",
                    "repair_locus": "analyst",
                    "explanation": "Analysis is surface-level",
                    "suggested_fix": "Deepen analysis"
                }
            ],
            "overall_assessment": "Needs work",
            "passed": true
        }"""
        monkeypatch.setattr(
            "artifactforge.agents.adversarial_reviewer._call_llm",
            lambda system, prompt: mock_response,
        )

        result = run_adversarial_reviewer(
            draft="Test draft",
            claim_ledger={"claims": []},
            execution_brief={"user_goal": "Goal", "audience": "Audience"},
        )

        assert result["issues"][0]["issue_id"] == "R001"

    def test_defaults_invalid_repair_locus(self, monkeypatch):
        mock_response = """{
            "issues": [
                {
                    "issue_id": "R001",
                    "severity": "HIGH",
                    "section": "Body",
                    "problem_type": "missing_dimension",
                    "repair_locus": "invalid_locus",
                    "explanation": "Missing dimension",
                    "suggested_fix": "Add it"
                }
            ],
            "overall_assessment": "Issues found",
            "passed": false
        }"""
        monkeypatch.setattr(
            "artifactforge.agents.adversarial_reviewer._call_llm",
            lambda system, prompt: mock_response,
        )

        result = run_adversarial_reviewer(
            draft="Test draft",
            claim_ledger={"claims": []},
            execution_brief={"user_goal": "Goal", "audience": "Audience"},
        )

        assert result["issues"][0]["repair_locus"] == "research_lead"

    def test_defaults_missing_repair_locus(self, monkeypatch):
        mock_response = """{
            "issues": [
                {
                    "issue_id": "R001",
                    "severity": "MEDIUM",
                    "section": "Body",
                    "problem_type": "overconfidence",
                    "explanation": "Too confident",
                    "suggested_fix": "Tone down"
                }
            ],
            "overall_assessment": "Issues",
            "passed": true
        }"""
        monkeypatch.setattr(
            "artifactforge.agents.adversarial_reviewer._call_llm",
            lambda system, prompt: mock_response,
        )

        result = run_adversarial_reviewer(
            draft="Test draft",
            claim_ledger={"claims": []},
            execution_brief={"user_goal": "Goal", "audience": "Audience"},
        )

        assert result["issues"][0]["repair_locus"] == "evidence_ledger"

    def test_defaults_to_draft_writer_when_problem_type_also_missing(self, monkeypatch):
        mock_response = """{
            "issues": [
                {
                    "issue_id": "R001",
                    "severity": "MEDIUM",
                    "section": "Body",
                    "explanation": "Something wrong",
                    "suggested_fix": "Fix it"
                }
            ],
            "overall_assessment": "Issues",
            "passed": true
        }"""
        monkeypatch.setattr(
            "artifactforge.agents.adversarial_reviewer._call_llm",
            lambda system, prompt: mock_response,
        )

        result = run_adversarial_reviewer(
            draft="Test draft",
            claim_ledger={"claims": []},
            execution_brief={"user_goal": "Goal", "audience": "Audience"},
        )

        assert result["issues"][0]["repair_locus"] == "draft_writer"

    def test_defaults_to_draft_writer_when_problem_type_is_unknown(self, monkeypatch):
        mock_response = """{
            "issues": [
                {
                    "issue_id": "R001",
                    "severity": "MEDIUM",
                    "section": "Body",
                    "problem_type": "totally_made_up",
                    "repair_locus": "also_made_up",
                    "explanation": "Something",
                    "suggested_fix": "Something"
                }
            ],
            "overall_assessment": "Issues",
            "passed": true
        }"""
        monkeypatch.setattr(
            "artifactforge.agents.adversarial_reviewer._call_llm",
            lambda system, prompt: mock_response,
        )

        result = run_adversarial_reviewer(
            draft="Test draft",
            claim_ledger={"claims": []},
            execution_brief={"user_goal": "Goal", "audience": "Audience"},
        )

        assert result["issues"][0]["repair_locus"] == "draft_writer"

    @pytest.mark.parametrize("problem_type, expected_locus", [
        ("missing_dimension", "research_lead"),
        ("unsupported_claim", "evidence_ledger"),
        ("shallow_analysis", "analyst"),
        ("overconfidence", "evidence_ledger"),
        ("weak_recommendation", "analyst"),
        ("audience_mismatch", "output_strategist"),
        ("poor_structure", "output_strategist"),
        ("misleading_framing", "intent_architect"),
        ("unaddressed_risk", "analyst"),
        ("unexamined_assumption", "evidence_ledger"),
    ])
    def test_problem_type_to_locus_mapping(self, monkeypatch, problem_type, expected_locus):
        mock_response = f"""{{
            "issues": [
                {{
                    "issue_id": "R001",
                    "severity": "MEDIUM",
                    "section": "Body",
                    "problem_type": "{problem_type}",
                    "repair_locus": "invalid_locus",
                    "explanation": "Test",
                    "suggested_fix": "Test"
                }}
            ],
            "overall_assessment": "Test",
            "passed": true
        }}"""
        monkeypatch.setattr(
            "artifactforge.agents.adversarial_reviewer._call_llm",
            lambda system, prompt: mock_response,
        )

        result = run_adversarial_reviewer(
            draft="Test draft",
            claim_ledger={"claims": []},
            execution_brief={"user_goal": "Goal", "audience": "Audience"},
        )

        assert result["issues"][0]["repair_locus"] == expected_locus

    def test_llm_failure_returns_fallback(self, monkeypatch):
        monkeypatch.setattr(
            "artifactforge.agents.adversarial_reviewer._call_llm",
            lambda system, prompt: "not valid json",
        )

        result = run_adversarial_reviewer(
            draft="Test draft",
            claim_ledger={"claims": []},
            execution_brief={"user_goal": "Goal", "audience": "Audience"},
        )

        assert result["issues"] == []
        assert result["overall_assessment"] == "Review not completed"
        assert result["passed"] is True

    def test_passed_computed_from_issues_when_missing(self, monkeypatch):
        mock_response = """{
            "issues": [
                {
                    "issue_id": "R001",
                    "severity": "HIGH",
                    "section": "Body",
                    "problem_type": "unsupported_claim",
                    "repair_locus": "draft_writer",
                    "explanation": "No evidence",
                    "suggested_fix": "Add evidence"
                }
            ],
            "overall_assessment": "Bad"
        }"""
        monkeypatch.setattr(
            "artifactforge.agents.adversarial_reviewer._call_llm",
            lambda system, prompt: mock_response,
        )

        result = run_adversarial_reviewer(
            draft="Test draft",
            claim_ledger={"claims": []},
            execution_brief={"user_goal": "Goal", "audience": "Audience"},
        )

        # No "passed" in response, but has HIGH severity issue
        assert result["passed"] is False

    def test_contract_is_registered(self):
        from artifactforge.coordinator.contracts import (
            ADVERSARIAL_REVIEWER_CONTRACT,
            AGENT_REGISTRY,
        )

        assert "adversarial_reviewer" in AGENT_REGISTRY
        assert ADVERSARIAL_REVIEWER_CONTRACT.name == "adversarial_reviewer"

"""Tests for the persistence adapter."""

import uuid
from unittest.mock import MagicMock, patch

import pytest


class TestPipelinePersistence:
    """Test PipelinePersistence methods."""

    def _make_persistence(self, enabled=True):
        """Create a PipelinePersistence with mocked DB."""
        with patch("artifactforge.db.persistence.PipelinePersistence._check_enabled", return_value=enabled):
            from artifactforge.db.persistence import PipelinePersistence
            return PipelinePersistence()

    def test_noop_when_disabled(self):
        """All methods should no-op when DB is not configured."""
        p = self._make_persistence(enabled=False)

        assert p.start_run("trace-1", "test prompt", "report") is None
        p.complete_run("art-1", "completed", "draft", {}, {}, {})
        p.record_node("art-1", "node", 100, 0, 0.0, True)
        p.record_evaluation("art-1", "reviewer", [], True)
        p.record_quality_gate("art-1", "gate", True)
        assert p.extract_learnings("art-1", "report", [], None, []) == 0
        context, ids = p.fetch_learnings("agent", "report")
        assert context is None
        assert ids == []

    @patch("artifactforge.db.persistence._get_session")
    def test_start_run_creates_artifact(self, mock_get_session):
        """start_run should create an Artifact row."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        p = self._make_persistence(enabled=True)
        trace_id = str(uuid.uuid4())
        result = p.start_run(trace_id, "test prompt", "report")

        assert result == trace_id
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    @patch("artifactforge.db.persistence._get_session")
    def test_start_run_handles_db_error(self, mock_get_session):
        """start_run should return None on DB error."""
        mock_session = MagicMock()
        mock_session.commit.side_effect = Exception("DB error")
        mock_get_session.return_value = mock_session

        p = self._make_persistence(enabled=True)
        result = p.start_run(str(uuid.uuid4()), "test", "report")

        assert result is None
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()

    @patch("artifactforge.db.persistence._get_session")
    def test_record_node_writes_execution(self, mock_get_session):
        """record_node should write an Execution row."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        p = self._make_persistence(enabled=True)
        p.record_node(
            artifact_id=str(uuid.uuid4()),
            node_name="draft_writer",
            duration_ms=1500,
            tokens=3000,
            cost=0.01,
            success=True,
        )

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @patch("artifactforge.db.persistence._get_session")
    def test_record_node_with_error(self, mock_get_session):
        """record_node should record error details."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        p = self._make_persistence(enabled=True)
        p.record_node(
            artifact_id=str(uuid.uuid4()),
            node_name="research_lead",
            duration_ms=500,
            tokens=0,
            cost=0.0,
            success=False,
            error="LLM timeout",
        )

        mock_session.add.assert_called_once()
        added_obj = mock_session.add.call_args[0][0]
        assert added_obj.status == "failure"
        assert added_obj.error_message == "LLM timeout"

    @patch("artifactforge.db.persistence._get_session")
    def test_record_evaluation(self, mock_get_session):
        """record_evaluation should write an Evaluation row."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        p = self._make_persistence(enabled=True)
        issues = [
            {"severity": "HIGH", "problem_type": "unsupported_claim"},
            {"severity": "MEDIUM", "problem_type": "shallow_analysis"},
        ]
        p.record_evaluation(
            artifact_id=str(uuid.uuid4()),
            node_name="adversarial_reviewer",
            issues=issues,
            passed=False,
        )

        mock_session.add.assert_called_once()
        added_obj = mock_session.add.call_args[0][0]
        assert added_obj.passed is False
        assert added_obj.evaluator == "adversarial_reviewer"

    @patch("artifactforge.db.persistence._get_session")
    def test_record_quality_gate(self, mock_get_session):
        """record_quality_gate should write a QualityGateResult row."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        p = self._make_persistence(enabled=True)
        p.record_quality_gate(
            artifact_id=str(uuid.uuid4()),
            gate_name="final_arbiter",
            passed=True,
            score=0.92,
            details={"status": "READY"},
        )

        mock_session.add.assert_called_once()
        added_obj = mock_session.add.call_args[0][0]
        assert added_obj.passed is True
        assert added_obj.gate_name == "final_arbiter"

    @patch("artifactforge.db.persistence._get_session")
    def test_extract_learnings_from_revisions(self, mock_get_session):
        """extract_learnings should create learnings from revision history."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        p = self._make_persistence(enabled=True)
        revision_history = [
            {
                "trigger": "high_severity_review_issues",
                "changes_made": "Rerun from adversarial_reviewer",
                "issues_addressed": ["R001", "R002"],
            },
        ]

        count = p.extract_learnings(
            artifact_id=str(uuid.uuid4()),
            artifact_type="report",
            revision_history=revision_history,
            release_decision=None,
            errors=[],
        )

        assert count == 1
        mock_session.add.assert_called_once()

    @patch("artifactforge.db.persistence._get_session")
    def test_extract_learnings_from_errors(self, mock_get_session):
        """extract_learnings should create learnings from pipeline errors."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        p = self._make_persistence(enabled=True)
        count = p.extract_learnings(
            artifact_id=str(uuid.uuid4()),
            artifact_type="blog",
            revision_history=[],
            release_decision=None,
            errors=["research_lead: API timeout", "draft_writer: JSON parse failed"],
        )

        assert count == 2

    @patch("artifactforge.db.persistence._get_session")
    def test_extract_learnings_from_release_decision(self, mock_get_session):
        """extract_learnings should capture remaining risks and known gaps."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        p = self._make_persistence(enabled=True)
        count = p.extract_learnings(
            artifact_id=str(uuid.uuid4()),
            artifact_type="report",
            revision_history=[],
            release_decision={
                "status": "READY",
                "remaining_risks": ["Market data may be outdated"],
                "known_gaps": ["No competitor pricing data"],
            },
            errors=[],
        )

        assert count == 2

    @patch("artifactforge.db.persistence._get_session")
    def test_fetch_learnings_returns_none_when_empty(self, mock_get_session):
        """fetch_learnings should return None when no learnings match."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_session.query.return_value = mock_query
        mock_get_session.return_value = mock_session

        p = self._make_persistence(enabled=True)
        context, ids = p.fetch_learnings("draft_writer", "report")

        assert context is None
        assert ids == []

    @patch("artifactforge.db.persistence._get_session")
    def test_fetch_learnings_returns_insights(self, mock_get_session):
        """fetch_learnings should return formatted insights and learning IDs."""
        mock_learning = MagicMock()
        mock_learning.id = uuid.uuid4()
        mock_learning.failure_mode = "unsupported_claim: Missing source"
        mock_learning.fix_applied = "Added source reference"
        mock_learning.confidence = 0.85
        mock_learning.source = "adversarial_review"
        mock_learning.is_validated = False
        mock_learning.times_applied = 0

        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_learning]
        mock_session.query.return_value = mock_query
        mock_get_session.return_value = mock_session

        p = self._make_persistence(enabled=True)
        context, ids = p.fetch_learnings("draft_writer", "report")

        assert context is not None
        assert context["agent"] == "draft_writer"
        assert context["artifact_type"] == "report"
        assert len(context["insights"]) == 1
        assert context["insights"][0]["confidence"] == 0.85
        assert len(ids) == 1
        assert ids[0] == str(mock_learning.id)

    def test_noop_with_empty_artifact_id(self):
        """Methods should no-op when artifact_id is empty."""
        p = self._make_persistence(enabled=True)

        # These should not raise
        p.complete_run("", "completed", None, {}, {}, {})
        p.record_node("", "node", 100, 0, 0.0, True)
        p.record_evaluation("", "node", [], True)
        p.record_quality_gate("", "gate", True)
        assert p.extract_learnings("", "report", [], None, []) == 0


class TestBuildLearningsSection:
    """Test the learnings prompt section builder."""

    def test_empty_when_none(self):
        from artifactforge.agents.learnings_utils import build_learnings_section

        assert build_learnings_section(None) == ""

    def test_empty_when_no_insights(self):
        from artifactforge.agents.learnings_utils import build_learnings_section

        assert build_learnings_section({"insights": []}) == ""

    def test_formats_insights(self):
        from artifactforge.agents.learnings_utils import build_learnings_section

        context = {
            "insights": [
                {
                    "failure_mode": "unsupported_claim: No source",
                    "fix_applied": "Added citation",
                    "confidence": 0.85,
                    "source": "adversarial_review",
                },
            ]
        }
        result = build_learnings_section(context)
        assert "Learnings from Prior Runs" in result
        assert "unsupported_claim: No source" in result
        assert "Added citation" in result
        assert "85%" in result

    def test_multiple_insights(self):
        from artifactforge.agents.learnings_utils import build_learnings_section

        context = {
            "insights": [
                {"failure_mode": "issue1", "confidence": 0.9, "source": "a"},
                {"failure_mode": "issue2", "fix_applied": "fix2", "confidence": 0.7, "source": "b"},
            ]
        }
        result = build_learnings_section(context)
        assert "1." in result
        assert "2." in result
        assert "issue1" in result
        assert "issue2" in result

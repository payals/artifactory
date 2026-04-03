"""Persistence adapter — thin layer between MCRS pipeline and PostgreSQL.

All methods no-op when DATABASE_URL is not configured.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Confidence threshold for learnings injection
LEARNINGS_CONFIDENCE_THRESHOLD = 0.7
# Max learnings injected per agent per run
LEARNINGS_CAP_PER_AGENT = 5
# Learnings older than this are excluded from injection
LEARNINGS_MAX_AGE_DAYS = 90
# Learnings applied this many times with zero successes are excluded
LEARNINGS_MIN_SUCCESS_AFTER_N_APPLIES = 3
# How much a single success/failure nudges confidence (exponential moving average)
CONFIDENCE_ALPHA = 0.15

# Map pipeline nodes to Execution.phase for grouping
_NODE_PHASE = {
    "intent_architect": "intent",
    "research_lead": "research",
    "evidence_ledger": "research",
    "analyst": "analysis",
    "output_strategist": "strategy",
    "draft_writer": "generation",
    "adversarial_reviewer": "review",
    "verifier": "review",
    "polisher": "generation",
    "final_arbiter": "review",
    "visual_designer": "visual",
    "visual_reviewer": "visual",
    "visual_generator": "visual",
}

# Nodes whose output should be stored as Evaluation records
_EVALUATION_NODES = {"adversarial_reviewer", "verifier", "final_arbiter"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_session():
    """Get a new SQLAlchemy session, or None if DB not configured."""
    from artifactforge.db.session import SessionLocal

    if SessionLocal is None:
        return None
    return SessionLocal()


class PipelinePersistence:
    """Manages all DB reads/writes for the MCRS pipeline."""

    def __init__(self) -> None:
        self._enabled = self._check_enabled()

    @staticmethod
    def _check_enabled() -> bool:
        from artifactforge.db.session import SessionLocal

        return SessionLocal is not None

    @property
    def enabled(self) -> bool:
        return self._enabled

    # ------------------------------------------------------------------
    # Pipeline lifecycle
    # ------------------------------------------------------------------

    def start_run(
        self,
        trace_id: str,
        user_prompt: str,
        output_type: str,
    ) -> Optional[str]:
        """Create an Artifact row at pipeline start. Returns artifact_id or None."""
        if not self._enabled:
            return None

        from artifactforge.db.models import Artifact

        session = _get_session()
        if session is None:
            return None

        try:
            artifact = Artifact(
                id=uuid.UUID(trace_id),
                type=output_type,
                user_description=user_prompt,
                status="running",
                created_at=_now(),
                updated_at=_now(),
                meta={"trace_id": trace_id},
            )
            session.add(artifact)
            session.commit()
            artifact_id = str(artifact.id)
            logger.info("Created artifact %s for trace %s", artifact_id, trace_id)
            return artifact_id
        except Exception as e:
            session.rollback()
            logger.error("Failed to create artifact: %s", e)
            return None
        finally:
            session.close()

    def complete_run(
        self,
        artifact_id: str,
        status: str,
        final_draft: Optional[str],
        stage_timing: dict[str, float],
        tokens_used: dict[str, int],
        costs: dict[str, float],
        release_decision: Optional[dict] = None,
        review_results: Optional[dict] = None,
        verification_report: Optional[dict] = None,
    ) -> None:
        """Update Artifact row and write ArtifactMetrics on pipeline completion."""
        if not self._enabled or not artifact_id:
            return

        from artifactforge.db.models import Artifact
        from artifactforge.db.models_metrics import ArtifactMetrics

        session = _get_session()
        if session is None:
            return

        try:
            artifact_uuid = uuid.UUID(artifact_id)

            # Update artifact
            artifact = session.get(Artifact, artifact_uuid)
            if artifact:
                artifact.status = status
                artifact.completed_at = _now()
                artifact.updated_at = _now()
                if final_draft:
                    artifact.final_artifact = {"content": final_draft}
                if review_results:
                    artifact.review_results = review_results
                if verification_report:
                    artifact.verification_status = (
                        "passed" if verification_report.get("passed") else "failed"
                    )
                    artifact.verification_errors = verification_report

            # Compute aggregate metrics
            total_duration = int(sum(stage_timing.values()) * 1000)
            total_tokens_in = sum(tokens_used.values())
            total_cost = sum(costs.values())

            research_nodes = {"research_lead", "evidence_ledger"}
            gen_nodes = {"draft_writer", "polisher"}
            review_nodes = {"adversarial_reviewer", "verifier", "final_arbiter"}

            metrics = ArtifactMetrics(
                artifact_id=artifact_uuid,
                total_duration_ms=total_duration,
                research_duration_ms=int(
                    sum(v * 1000 for k, v in stage_timing.items() if k in research_nodes)
                ),
                generate_duration_ms=int(
                    sum(v * 1000 for k, v in stage_timing.items() if k in gen_nodes)
                ),
                review_duration_ms=int(
                    sum(v * 1000 for k, v in stage_timing.items() if k in review_nodes)
                ),
                total_input_tokens=total_tokens_in,
                total_output_tokens=0,
                estimated_cost_cents=total_cost * 100,
                evaluation_score=(
                    release_decision.get("confidence")
                    if release_decision
                    else None
                ),
                num_retries=0,
                created_at=_now(),
            )
            session.add(metrics)
            session.commit()
            logger.info("Completed artifact %s with status=%s", artifact_id, status)
        except Exception as e:
            session.rollback()
            logger.error("Failed to complete artifact: %s", e)
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Per-node execution recording
    # ------------------------------------------------------------------

    def record_node(
        self,
        artifact_id: str,
        node_name: str,
        duration_ms: int,
        tokens: int,
        cost: float,
        success: bool,
        error: Optional[str] = None,
        output_summary: Optional[dict] = None,
    ) -> None:
        """Write an Execution row for a completed node."""
        if not self._enabled or not artifact_id:
            return

        from artifactforge.db.models_executions import Execution

        session = _get_session()
        if session is None:
            return

        try:
            execution = Execution(
                artifact_id=uuid.UUID(artifact_id),
                phase=_NODE_PHASE.get(node_name, "unknown"),
                step=node_name,
                started_at=_now(),
                completed_at=_now(),
                duration_ms=duration_ms,
                input_tokens=tokens,
                output_tokens=0,
                status="success" if success else "failure",
                error_message=error,
                output=output_summary,
                meta={},
            )
            session.add(execution)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error("Failed to record node %s: %s", node_name, e)
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Evaluation persistence
    # ------------------------------------------------------------------

    def record_evaluation(
        self,
        artifact_id: str,
        node_name: str,
        issues: list[dict],
        passed: bool,
        confidence: Optional[float] = None,
    ) -> None:
        """Write an Evaluation row for reviewer/verifier/arbiter output."""
        if not self._enabled or not artifact_id:
            return

        from artifactforge.db.models_quality import Evaluation

        session = _get_session()
        if session is None:
            return

        try:
            high_count = sum(1 for i in issues if i.get("severity") == "HIGH")
            medium_count = sum(1 for i in issues if i.get("severity") == "MEDIUM")

            overall_score = 1.0 if passed else max(0.0, 1.0 - high_count * 0.3 - medium_count * 0.1)

            evaluation = Evaluation(
                artifact_id=uuid.UUID(artifact_id),
                evaluation_type="agent_review",
                evaluator=node_name,
                issues=issues,
                passed=passed,
                confidence=confidence,
                overall_score=overall_score,
                created_at=_now(),
            )
            session.add(evaluation)
            session.commit()

            # Backfill quality_score on prompt snapshots for this artifact
            self.backfill_quality_scores(artifact_id, overall_score)
        except Exception as e:
            session.rollback()
            logger.error("Failed to record evaluation for %s: %s", node_name, e)
        finally:
            session.close()

    def record_quality_gate(
        self,
        artifact_id: str,
        gate_name: str,
        passed: bool,
        score: Optional[float] = None,
        details: Optional[dict] = None,
        attempt: int = 1,
    ) -> None:
        """Write a QualityGateResult row."""
        if not self._enabled or not artifact_id:
            return

        from artifactforge.db.models_quality import QualityGateResult

        session = _get_session()
        if session is None:
            return

        try:
            gate = QualityGateResult(
                artifact_id=uuid.UUID(artifact_id),
                gate_name=gate_name,
                passed=passed,
                score=score,
                details=details,
                attempt=attempt,
                created_at=_now(),
            )
            session.add(gate)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error("Failed to record quality gate %s: %s", gate_name, e)
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Learnings — extraction (write)
    # ------------------------------------------------------------------

    def extract_learnings(
        self,
        artifact_id: str,
        artifact_type: str,
        revision_history: list[dict],
        release_decision: Optional[dict],
        errors: list[str],
        red_team_review: Optional[dict] = None,
    ) -> int:
        """Extract learnings from a completed run and write to DB.

        Returns number of learnings created.
        """
        if not self._enabled or not artifact_id:
            return 0

        from artifactforge.db.models_learnings import Learnings

        session = _get_session()
        if session is None:
            return 0

        learnings_to_add: list[Learnings] = []

        try:
            artifact_uuid = uuid.UUID(artifact_id)

            # 1. Extract from revision history — each revision is a learning opportunity
            for rev in revision_history:
                if rev.get("trigger") and rev["trigger"] != "draft":
                    learnings_to_add.append(
                        Learnings(
                            artifact_type=artifact_type,
                            context=f"Revision triggered by {rev.get('trigger', 'unknown')}",
                            failure_mode=f"Required revision: {rev.get('changes_made', 'unspecified')}",
                            fix_applied=f"Issues addressed: {', '.join(rev.get('issues_addressed', []))}",
                            outcome="success",
                            confidence=0.6,
                            source="revision_history",
                            artifact_id=artifact_uuid,
                            created_at=_now(),
                        )
                    )

            # 2. Extract from errors
            for error_msg in errors:
                learnings_to_add.append(
                    Learnings(
                        artifact_type=artifact_type,
                        context=f"Pipeline error in {error_msg.split(':')[0] if ':' in error_msg else 'unknown'}",
                        failure_mode=error_msg,
                        outcome="failure",
                        confidence=0.8,
                        source="pipeline_error",
                        artifact_id=artifact_uuid,
                        created_at=_now(),
                    )
                )

            # 3. Extract from release decision
            if release_decision:
                for risk in release_decision.get("remaining_risks", []):
                    learnings_to_add.append(
                        Learnings(
                            artifact_type=artifact_type,
                            context="Remaining risk identified by final arbiter",
                            failure_mode=f"Unresolved risk: {risk}",
                            outcome="needs_investigation",
                            confidence=0.5,
                            source="release_decision",
                            artifact_id=artifact_uuid,
                            created_at=_now(),
                        )
                    )
                for gap in release_decision.get("known_gaps", []):
                    learnings_to_add.append(
                        Learnings(
                            artifact_type=artifact_type,
                            context="Known gap identified by final arbiter",
                            failure_mode=f"Known gap: {gap}",
                            outcome="needs_investigation",
                            confidence=0.5,
                            source="release_decision",
                            artifact_id=artifact_uuid,
                            created_at=_now(),
                        )
                    )

            # 4. Extract from red team review — recurring HIGH issues become learnings
            if red_team_review:
                for issue in red_team_review.get("issues", []):
                    if issue.get("severity") == "HIGH":
                        learnings_to_add.append(
                            Learnings(
                                artifact_type=artifact_type,
                                context=f"HIGH severity issue from adversarial reviewer in section: {issue.get('section', 'unknown')}",
                                failure_mode=f"{issue.get('problem_type', 'unknown')}: {issue.get('explanation', '')}",
                                fix_applied=issue.get("suggested_fix"),
                                outcome="success" if release_decision and release_decision.get("status") == "READY" else "needs_investigation",
                                confidence=0.7,
                                source="adversarial_review",
                                artifact_id=artifact_uuid,
                                created_at=_now(),
                            )
                        )

            # Write all learnings
            for learning in learnings_to_add:
                session.add(learning)
            session.commit()

            count = len(learnings_to_add)
            if count:
                logger.info("Extracted %d learnings from artifact %s", count, artifact_id)
            return count

        except Exception as e:
            session.rollback()
            logger.error("Failed to extract learnings: %s", e)
            return 0
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Learnings — injection (read)
    # ------------------------------------------------------------------

    def fetch_learnings(
        self,
        agent_name: str,
        artifact_type: str,
    ) -> tuple[Optional[dict[str, Any]], list[str]]:
        """Fetch relevant learnings for an agent, filtered by confidence, age, and effectiveness.

        Returns:
            Tuple of (learnings context dict for prompt injection, list of learning IDs applied).
            Context is None if no learnings found.
        """
        if not self._enabled:
            return None, []

        from datetime import timedelta

        from sqlalchemy import and_, desc, or_

        from artifactforge.db.models_learnings import Learnings

        session = _get_session()
        if session is None:
            return None, []

        try:
            age_cutoff = _now() - timedelta(days=LEARNINGS_MAX_AGE_DAYS)

            rows = (
                session.query(Learnings)
                .filter(
                    Learnings.artifact_type == artifact_type,
                    Learnings.confidence >= LEARNINGS_CONFIDENCE_THRESHOLD,
                    # Deprecation: exclude learnings older than max age
                    Learnings.created_at >= age_cutoff,
                    # Deprecation: exclude proven-ineffective learnings
                    or_(
                        Learnings.times_applied < LEARNINGS_MIN_SUCCESS_AFTER_N_APPLIES,
                        Learnings.times_succeeded > 0,
                    ),
                )
                .order_by(
                    # Prefer validated learnings, then by confidence
                    desc(Learnings.is_validated),
                    desc(Learnings.confidence),
                    desc(Learnings.created_at),
                )
                .limit(LEARNINGS_CAP_PER_AGENT)
                .all()
            )

            if not rows:
                return None, []

            insights = []
            learning_ids = []
            for row in rows:
                insights.append({
                    "failure_mode": row.failure_mode,
                    "fix_applied": row.fix_applied,
                    "confidence": float(row.confidence),
                    "source": row.source,
                })
                learning_ids.append(str(row.id))

            # Update times_applied counter
            for row in rows:
                row.times_applied = (row.times_applied or 0) + 1
            session.commit()

            return {
                "agent": agent_name,
                "artifact_type": artifact_type,
                "insights": insights,
            }, learning_ids

        except Exception as e:
            session.rollback()
            logger.error("Failed to fetch learnings for %s: %s", agent_name, e)
            return None, []
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Learnings — confidence updates (feedback loop)
    # ------------------------------------------------------------------

    def update_learnings_outcome(
        self,
        learning_ids: list[str],
        success: bool,
    ) -> None:
        """Update confidence of applied learnings based on run outcome.

        After a pipeline run completes, this recalculates confidence for each
        learning that was injected, based on whether the run succeeded.
        Uses exponential moving average: new = old + alpha * (outcome - old).
        """
        if not self._enabled or not learning_ids:
            return

        from artifactforge.db.models import Artifact  # noqa: F401 — FK resolution
        from artifactforge.db.models_learnings import Learnings

        session = _get_session()
        if session is None:
            return

        try:
            for lid in learning_ids:
                row = session.get(Learnings, uuid.UUID(lid))
                if not row:
                    continue

                if success:
                    row.times_succeeded = (row.times_succeeded or 0) + 1

                # Recalculate confidence via EMA
                outcome = 1.0 if success else 0.0
                old_conf = float(row.confidence)
                new_conf = old_conf + CONFIDENCE_ALPHA * (outcome - old_conf)
                row.confidence = max(0.05, min(0.95, new_conf))

            session.commit()
            logger.info(
                "Updated %d learnings: outcome=%s",
                len(learning_ids),
                "success" if success else "failure",
            )
        except Exception as e:
            session.rollback()
            logger.error("Failed to update learnings outcome: %s", e)
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Learnings — validation and lifecycle management
    # ------------------------------------------------------------------

    def validate_learning(self, learning_id: str, validated: bool = True) -> bool:
        """Mark a learning as validated (or invalidated) by a human.

        Validated learnings get a confidence boost and are prioritized in injection.
        Invalidated learnings have their confidence zeroed out.
        """
        if not self._enabled:
            return False

        from artifactforge.db.models import Artifact  # noqa: F401 — FK resolution
        from artifactforge.db.models_learnings import Learnings

        session = _get_session()
        if session is None:
            return False

        try:
            row = session.get(Learnings, uuid.UUID(learning_id))
            if not row:
                return False

            row.is_validated = validated
            row.validated_at = _now()

            if validated:
                # Boost confidence — validated learnings are trustworthy
                row.confidence = min(0.95, float(row.confidence) + 0.15)
            else:
                # Zero out — human says this learning is wrong
                row.confidence = 0.0

            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error("Failed to validate learning %s: %s", learning_id, e)
            return False
        finally:
            session.close()

    def prune_learnings(self) -> int:
        """Remove deprecated learnings that will never be injected again.

        Criteria:
        - Confidence below threshold AND applied 3+ times with zero successes
        - Older than max age
        - Explicitly invalidated (is_validated=True with confidence=0)

        Returns number of rows deleted.
        """
        if not self._enabled:
            return 0

        from datetime import timedelta

        from sqlalchemy import and_, or_

        from artifactforge.db.models_learnings import Learnings

        session = _get_session()
        if session is None:
            return 0

        try:
            age_cutoff = _now() - timedelta(days=LEARNINGS_MAX_AGE_DAYS)

            stale = (
                session.query(Learnings)
                .filter(
                    or_(
                        # Expired by age
                        Learnings.created_at < age_cutoff,
                        # Proven ineffective
                        and_(
                            Learnings.times_applied >= LEARNINGS_MIN_SUCCESS_AFTER_N_APPLIES,
                            Learnings.times_succeeded == 0,
                            Learnings.confidence < LEARNINGS_CONFIDENCE_THRESHOLD,
                        ),
                        # Explicitly invalidated
                        and_(
                            Learnings.is_validated == True,
                            Learnings.confidence <= 0.0,
                        ),
                    )
                )
                .all()
            )

            count = len(stale)
            for row in stale:
                session.delete(row)
            session.commit()

            if count:
                logger.info("Pruned %d deprecated learnings", count)
            return count
        except Exception as e:
            session.rollback()
            logger.error("Failed to prune learnings: %s", e)
            return 0
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Prompt snapshots — capture every LLM call
    # ------------------------------------------------------------------

    def persist_prompt_snapshot(
        self,
        artifact_id: Optional[str],
        agent_name: str,
        system_prompt: str,
        user_prompt: str,
        response_text: Optional[str],
        response_tokens: int,
        model: Optional[str],
        temperature: float,
        duration_ms: float,
        learnings_context: Optional[dict] = None,
    ) -> None:
        """Persist a prompt snapshot for every LLM call."""
        if not self._enabled:
            return

        from artifactforge.db.models import Artifact  # noqa: F401
        from artifactforge.db.models_prompts import PromptSnapshot

        session = _get_session()
        if session is None:
            return

        try:
            snapshot = PromptSnapshot(
                artifact_id=uuid.UUID(artifact_id) if artifact_id else None,
                agent_name=agent_name or "unknown",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                learnings_injected=learnings_context,
                response_text=response_text or None,
                response_tokens=response_tokens,
                model=model,
                temperature=temperature,
                duration_ms=duration_ms,
                created_at=_now(),
            )
            session.add(snapshot)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.debug("Failed to persist prompt snapshot: %s", e)
        finally:
            session.close()

    def backfill_quality_scores(
        self,
        artifact_id: str,
        quality_score: float,
    ) -> int:
        """Backfill quality_score on prompt_snapshots for a given artifact.

        Called after evaluations are recorded so each prompt gets its outcome signal.
        Returns number of rows updated.
        """
        if not self._enabled or not artifact_id:
            return 0

        from artifactforge.db.models import Artifact  # noqa: F401
        from artifactforge.db.models_prompts import PromptSnapshot

        session = _get_session()
        if session is None:
            return 0

        try:
            artifact_uuid = uuid.UUID(artifact_id)
            rows = (
                session.query(PromptSnapshot)
                .filter(
                    PromptSnapshot.artifact_id == artifact_uuid,
                    PromptSnapshot.quality_score.is_(None),
                )
                .all()
            )
            for row in rows:
                row.quality_score = quality_score
            session.commit()
            return len(rows)
        except Exception as e:
            session.rollback()
            logger.debug("Failed to backfill quality scores: %s", e)
            return 0
        finally:
            session.close()

    def list_prompt_snapshots(
        self,
        artifact_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """List prompt snapshots, optionally filtered."""
        if not self._enabled:
            return []

        from sqlalchemy import desc

        from artifactforge.db.models import Artifact  # noqa: F401
        from artifactforge.db.models_prompts import PromptSnapshot

        session = _get_session()
        if session is None:
            return []

        try:
            query = session.query(PromptSnapshot)
            if artifact_id:
                query = query.filter(PromptSnapshot.artifact_id == uuid.UUID(artifact_id))
            if agent_name:
                query = query.filter(PromptSnapshot.agent_name == agent_name)
            rows = query.order_by(desc(PromptSnapshot.created_at)).limit(limit).all()

            return [
                {
                    "id": str(row.id),
                    "artifact_id": str(row.artifact_id) if row.artifact_id else None,
                    "agent_name": row.agent_name,
                    "model": row.model,
                    "system_prompt_len": len(row.system_prompt) if row.system_prompt else 0,
                    "user_prompt_len": len(row.user_prompt) if row.user_prompt else 0,
                    "response_tokens": row.response_tokens,
                    "duration_ms": row.duration_ms,
                    "quality_score": row.quality_score,
                    "has_learnings": bool(row.learnings_injected),
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ]
        except Exception as e:
            logger.error("Failed to list prompt snapshots: %s", e)
            return []
        finally:
            session.close()

    def get_prompt_snapshot(self, snapshot_id: str) -> Optional[dict[str, Any]]:
        """Get full prompt snapshot by ID (includes full prompt text)."""
        if not self._enabled:
            return None

        from artifactforge.db.models import Artifact  # noqa: F401
        from artifactforge.db.models_prompts import PromptSnapshot

        session = _get_session()
        if session is None:
            return None

        try:
            row = session.get(PromptSnapshot, uuid.UUID(snapshot_id))
            if not row:
                return None
            return {
                "id": str(row.id),
                "artifact_id": str(row.artifact_id) if row.artifact_id else None,
                "agent_name": row.agent_name,
                "system_prompt": row.system_prompt,
                "user_prompt": row.user_prompt,
                "learnings_injected": row.learnings_injected,
                "response_text": row.response_text,
                "response_tokens": row.response_tokens,
                "model": row.model,
                "temperature": row.temperature,
                "duration_ms": row.duration_ms,
                "quality_score": row.quality_score,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        except Exception as e:
            logger.error("Failed to get prompt snapshot: %s", e)
            return None
        finally:
            session.close()

    def list_learnings(
        self,
        artifact_type: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """List all learnings, optionally filtered by artifact type."""
        if not self._enabled:
            return []

        from sqlalchemy import desc

        from artifactforge.db.models_learnings import Learnings

        session = _get_session()
        if session is None:
            return []

        try:
            query = session.query(Learnings)
            if artifact_type:
                query = query.filter(Learnings.artifact_type == artifact_type)
            rows = query.order_by(desc(Learnings.confidence)).all()

            return [
                {
                    "id": str(row.id),
                    "artifact_type": row.artifact_type,
                    "failure_mode": row.failure_mode,
                    "fix_applied": row.fix_applied,
                    "confidence": float(row.confidence),
                    "times_applied": row.times_applied or 0,
                    "times_succeeded": row.times_succeeded or 0,
                    "source": row.source,
                    "outcome": row.outcome,
                    "is_validated": row.is_validated,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ]
        except Exception as e:
            logger.error("Failed to list learnings: %s", e)
            return []
        finally:
            session.close()


# ------------------------------------------------------------------
# Module-level singleton
# ------------------------------------------------------------------

_persistence: Optional[PipelinePersistence] = None


def get_persistence() -> PipelinePersistence:
    """Get or create the singleton persistence adapter."""
    global _persistence
    if _persistence is None:
        _persistence = PipelinePersistence()
    return _persistence


__all__ = ["PipelinePersistence", "get_persistence"]

"""Quality assurance models."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from artifactforge.db.base import Base


class Evaluation(Base):
    """Evaluation model - LLM-as-Judge results."""

    __tablename__ = "evaluations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id", ondelete="CASCADE")
    )
    evaluation_type: Mapped[str] = mapped_column(String(20), nullable=False)
    evaluator: Mapped[Optional[str]] = mapped_column(String(50))
    completeness_score: Mapped[Optional[float]] = mapped_column()
    clarity_score: Mapped[Optional[float]] = mapped_column()
    accuracy_score: Mapped[Optional[float]] = mapped_column()
    quality_score: Mapped[Optional[float]] = mapped_column()
    overall_score: Mapped[Optional[float]] = mapped_column()
    issues: Mapped[list] = mapped_column(JSONB, default=[])
    suggestions: Mapped[list] = mapped_column(JSONB, default=[])
    passed: Mapped[Optional[bool]] = mapped_column(Boolean)
    confidence: Mapped[Optional[float]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class HumanFeedback(Base):
    """Human feedback model."""

    __tablename__ = "human_feedback"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id", ondelete="CASCADE")
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    usefulness: Mapped[Optional[int]] = mapped_column(Integer)
    accuracy: Mapped[Optional[int]] = mapped_column(Integer)
    quality: Mapped[Optional[int]] = mapped_column(Integer)
    overall_rating: Mapped[Optional[int]] = mapped_column(Integer)
    feedback: Mapped[Optional[str]] = mapped_column(String)
    would_regenerate: Mapped[Optional[bool]] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class QualityGateResult(Base):
    """Quality gate result model."""

    __tablename__ = "quality_gate_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id", ondelete="CASCADE")
    )
    gate_name: Mapped[str] = mapped_column(String(100), nullable=False)
    gate_type: Mapped[Optional[str]] = mapped_column(String(50))
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[Optional[float]] = mapped_column()
    details: Mapped[Optional[dict]] = mapped_column(JSONB)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


__all__ = ["Evaluation", "HumanFeedback", "QualityGateResult"]

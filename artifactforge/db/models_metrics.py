"""Metrics models."""

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from artifactforge.db.base import Base


class ArtifactMetrics(Base):
    """Artifact metrics model."""

    __tablename__ = "artifact_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id", ondelete="CASCADE")
    )

    # Timing (milliseconds)
    total_duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    research_duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    generate_duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    review_duration_ms: Mapped[Optional[int]] = mapped_column(Integer)

    # Tokens
    total_input_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    total_output_tokens: Mapped[Optional[int]] = mapped_column(Integer)

    # Costs
    estimated_cost_cents: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))

    # Quality
    evaluation_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    human_rating: Mapped[Optional[int]] = mapped_column(Integer)

    # Counts
    num_retries: Mapped[Optional[int]] = mapped_column(Integer)
    num_user_questions: Mapped[Optional[int]] = mapped_column(Integer)
    num_tools_used: Mapped[Optional[int]] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DailyMetrics(Base):
    """Daily aggregated metrics."""

    __tablename__ = "daily_metrics"

    date: Mapped[date] = mapped_column(Date, primary_key=True)

    # Volume
    artifacts_created: Mapped[int] = mapped_column(Integer, default=0)
    artifacts_completed: Mapped[int] = mapped_column(Integer, default=0)
    artifacts_failed: Mapped[int] = mapped_column(Integer, default=0)

    # Timing
    avg_total_duration_ms: Mapped[Optional[int]] = mapped_column(Integer)

    # Tokens
    total_input_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    total_output_tokens: Mapped[Optional[int]] = mapped_column(Integer)

    # Costs
    total_cost_cents: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))

    # Quality
    avg_evaluation_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))

    # Rates
    success_rate: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


__all__ = ["ArtifactMetrics", "DailyMetrics"]

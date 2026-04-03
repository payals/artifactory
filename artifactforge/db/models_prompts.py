"""Prompt snapshot models — records every LLM call for debugging and dataset building."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from artifactforge.db.base import Base


class PromptSnapshot(Base):
    """Records the full prompt sent to and response received from an LLM call.

    Serves two purposes:
    - Option A (debugging): diff prompts for the same agent across runs to see
      how learnings injection changed behavior.
    - Option B (dataset): query (system_prompt, user_prompt, response, quality_score)
      tuples for prompt optimization or fine-tuning.
    """

    __tablename__ = "prompt_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    artifact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id", ondelete="CASCADE")
    )
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    learnings_injected: Mapped[Optional[dict]] = mapped_column(JSONB)
    response_text: Mapped[Optional[str]] = mapped_column(Text)
    response_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    model: Mapped[Optional[str]] = mapped_column(String(100))
    temperature: Mapped[Optional[float]] = mapped_column(Float)
    duration_ms: Mapped[Optional[float]] = mapped_column(Float)
    quality_score: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )


__all__ = ["PromptSnapshot"]

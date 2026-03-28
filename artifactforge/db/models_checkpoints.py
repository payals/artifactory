"""Checkpoint models."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from artifactforge.db.base import Base


class Checkpoint(Base):
    """State checkpoint model."""

    __tablename__ = "checkpoints"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id", ondelete="CASCADE")
    )
    step: Mapped[str] = mapped_column(String(50), nullable=False)
    node: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[dict] = mapped_column(JSONB, nullable=False)
    parent_checkpoint_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("checkpoints.id")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


__all__ = ["Checkpoint"]

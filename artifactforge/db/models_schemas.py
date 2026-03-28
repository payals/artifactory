"""Schema registry models."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from artifactforge.db.base import Base


class ArtifactSchema(Base):
    """Artifact schema model."""

    __tablename__ = "artifact_schemas"

    type: Mapped[str] = mapped_column(String(50), primary_key=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    schema_definition: Mapped[dict] = mapped_column(JSONB, nullable=False)
    research_config: Mapped[Optional[dict]] = mapped_column(JSONB)
    generation_config: Mapped[Optional[dict]] = mapped_column(JSONB)
    review_config: Mapped[Optional[dict]] = mapped_column(JSONB)
    output_config: Mapped[Optional[dict]] = mapped_column(JSONB)
    quality_gates: Mapped[Optional[list]] = mapped_column(JSONB)
    description: Mapped[Optional[str]] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class ToolConfig(Base):
    """Tool configuration model."""

    __tablename__ = "tool_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    tool_definition: Mapped[dict] = mapped_column(JSONB, nullable=False)
    capabilities: Mapped[list] = mapped_column(JSONB, default=[])
    supported_artifact_types: Mapped[list] = mapped_column(JSONB, default=[])


__all__ = ["ArtifactSchema", "ToolConfig"]

"""Core SQLAlchemy models for ArtifactForge."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from artifactforge.db.base import Base


class User(Base):
    """User model."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    api_key: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    preferences: Mapped[dict] = mapped_column(JSONB, default={})
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Session(Base):
    """Session model."""

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    title: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    context: Mapped[dict] = mapped_column(JSONB, default={})
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    user: Mapped["User"] = relationship("User", backref="sessions")


class Artifact(Base):
    """Artifact model - core entity."""

    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="SET NULL")
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    # Identification
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Input
    user_description: Mapped[str] = mapped_column(Text, nullable=False)
    input_schema: Mapped[Optional[dict]] = mapped_column(JSONB)
    input_context: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Research Phase
    research_context: Mapped[Optional[dict]] = mapped_column(JSONB)
    research_sources: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Generation Phase
    artifact_draft: Mapped[Optional[str]] = mapped_column(Text)
    generation_metadata: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Review Phase
    review_results: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Verification
    verification_status: Mapped[str] = mapped_column(String(20), default="pending")
    verification_errors: Mapped[Optional[dict]] = mapped_column(JSONB)
    verification_gates: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Lifecycle
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Evolution
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id")
    )
    resume_mode: Mapped[Optional[str]] = mapped_column(String(20))

    # Output
    final_artifact: Mapped[Optional[dict]] = mapped_column(JSONB)
    output_format: Mapped[Optional[str]] = mapped_column(String(20))

    # Metadata
    meta: Mapped[dict] = mapped_column(JSONB, default={})

    session: Mapped[Optional["Session"]] = relationship("Session", backref="artifacts")
    user: Mapped[Optional["User"]] = relationship("User", backref="artifacts")
    parent: Mapped[Optional["Artifact"]] = relationship(
        "Artifact", remote_side=[id], backref="children"
    )


__all__ = [
    "Base",
    "User",
    "Session",
    "Artifact",
]

# ArtifactForge Bootstrap Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Bootstrap ArtifactForge - a universal knowledge artifact generator with Python, PostgreSQL, and LangGraph. Implement all 5 phases from the bootstrap prompt.

**Architecture:** Hybrid composable tool ecosystem with specialized tools dynamically assembled per artifact type. LangGraph orchestrates the pipeline with state machine, checkpointing, and tool invocation.

**Tech Stack:** Python 3.11+, PostgreSQL (Docker), LangGraph, SQLAlchemy, Alembic

---

## Prerequisites

```bash
# Start PostgreSQL
cd /Users/pi/Projects/ArtifactForge/artifactforge-design
docker-compose up -d postgres

# Wait for health check
docker-compose ps  # Should show healthy
```

---

## Phase 1: Foundation

### Task 1.1: Set Up Python Package Structure

**Files:**
- Create: `src/artifactforge/__init__.py`
- Create: `src/artifactforge/py.typed`
- Create: `src/artifactforge/config.py`

**Step 1: Create package directories**

```bash
mkdir -p src/artifactforge
mkdir -p src/artifactforge/{coordinator,router,context,learnings,validation,evaluation,observability,tools,schemas,verification,cli}
mkdir -p migrations/versions
mkdir -p tests/{unit,integration}
```

**Step 2: Create `src/artifactforge/__init__.py`**

```python
"""ArtifactForge - Universal knowledge artifact generator."""

__version__ = "0.1.0"

from artifactforge.config import Settings

__all__ = ["Settings", "__version__"]
```

**Step 3: Create `src/artifactforge/py.typed`**

```python
# Marker file for type checking
```

**Step 4: Create `src/artifactforge/config.py`**

```python
"""Configuration management for ArtifactForge."""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = Field(
        default="postgresql://artifactforge:artifactforge@localhost:5432/artifactforge",
        description="PostgreSQL connection string",
    )

    # LLM Providers
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    anthropic_api_key: Optional[str] = Field(description="Anthropic API key")

    # Application
    log_level: str = Field(default="INFO", description="Logging level")
    environment: str = Field(default="development", description="Environment")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
```

**Step 5: Verify package can be imported**

```bash
cd /Users/pi/Projects/ArtifactForge/artifactforge-design
pip install -e .
python -c "from artifactforge import Settings, __version__; print(f'OK: {__version__}')"
```

Expected: `OK: 0.1.0`

---

### Task 1.2: Create SQLAlchemy Models (Core Tables)

**Files:**
- Create: `src/artifactforge/db/base.py`
- Create: `src/artifactforge/db/models.py`
- Create: `src/artifactforge/db/__init__.py`
- Create: `src/artifactforge/db/session.py`

**Step 1: Create database base module**

Create `src/artifactforge/db/base.py`:

```python
"""Database base classes and utilities."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""

    pass
```

**Step 2: Create core SQLAlchemy models**

Create `src/artifactforge/db/models.py`:

```python
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
    preferences: Mapped[dict] = mapped_column(JSONB, default_factory=dict)
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
    context: Mapped[dict] = mapped_column(JSONB, default_factory=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

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
    verification_status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )
    verification_errors: Mapped[Optional[dict]] = mapped_column(JSONB)
    verification_gates: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Lifecycle
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
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
    metadata: Mapped[dict] = mapped_column(JSONB, default_factory=dict)

    session: Mapped[Optional["Session"]] = relationship("Session", backref="artifacts")
    user: Mapped[Optional["User"]] = relationship("User", backref="artifacts")
    parent: Mapped[Optional["Artifact"]] = relationship(
        "Artifact", remote_side=[id], backref="children"
    )


# Import additional models after base classes are defined
from artifactforge.db.models_learnings import Learnings, Knowledge
from artifactforge.db.models_executions import Execution, ExecutionTrace, ExecutionLog
from artifactforge.db.models_quality import Evaluation, HumanFeedback, QualityGateResult
from artifactforge.db_models_metrics import ArtifactMetrics
from artifactforge.db.models_schemas import ArtifactSchema, ToolConfig
from artifactforge.db.models_checkpoints import Checkpoint

__all__ = [
    "Base",
    "User",
    "Session",
    "Artifact",
]
```

**Step 3: Create Learnings model**

Create `src/artifactforge/db/models_learnings.py`:

```python
"""Learnings and Knowledge models."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from artifactforge.db.base import Base


class Learnings(Base):
    """Learnings model - auto-captured insights from failures."""

    __tablename__ = "learnings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    context: Mapped[str] = mapped_column(Text, nullable=False)
    failure_mode: Mapped[str] = mapped_column(Text, nullable=False)
    fix_applied: Mapped[Optional[str]] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(default=0.5)
    times_applied: Mapped[int] = mapped_column(Integer, default=0)
    times_succeeded: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    artifact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id", ondelete="SET NULL")
    )
    is_validated: Mapped[bool] = mapped_column(default=False)
    validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Knowledge(Base):
    """Knowledge model - curated human-maintained patterns."""

    __tablename__ = "knowledge"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_reference: Mapped[Optional[str]] = mapped_column(Text)
    times_used: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    is_verified: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


__all__ = ["Learnings", "Knowledge"]
```

**Step 4: Create Execution models**

Create `src/artifactforge/db/models_executions.py`:

```python
"""Execution and tracing models."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from artifactforge.db.base import Base


class Execution(Base):
    """Execution model - top-level execution tracking."""

    __tablename__ = "executions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id", ondelete="CASCADE")
    )
    phase: Mapped[str] = mapped_column(String(50), nullable=False)
    step: Mapped[str] = mapped_column(String(100), nullable=False)
    input: Mapped[Optional[dict]] = mapped_column(JSONB)
    output: Mapped[Optional[dict]] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    previous_execution_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("executions.id")
    )
    metadata: Mapped[dict] = mapped_column(JSONB, default_factory=dict)

    artifact: Mapped["Artifact"] = relationship("Artifact", backref="executions")


class ExecutionTrace(Base):
    """Execution trace - detailed trace for debugging."""

    __tablename__ = "execution_traces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("executions.id", ondelete="CASCADE")
    )
    trace_type: Mapped[str] = mapped_column(String(50), nullable=False)
    layer: Mapped[Optional[str]] = mapped_column(String(50))
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)

    execution: Mapped["Execution"] = relationship("Execution", backref="traces")


class ExecutionLog(Base):
    """Execution log - structured logging."""

    __tablename__ = "execution_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    artifact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id", ondelete="SET NULL")
    )
    execution_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("executions.id", ondelete="SET NULL")
    )
    level: Mapped[str] = mapped_column(String(10), nullable=False)
    component: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict] = mapped_column(JSONB, default_factory=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


__all__ = ["Execution", "ExecutionTrace", "ExecutionLog"]
```

**Step 5: Create Quality models**

Create `src/artifactforge/db/models_quality.py`:

```python
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
    issues: Mapped[list] = mapped_column(JSONB, default_factory=list)
    suggestions: Mapped[list] = mapped_column(JSONB, default_factory=list)
    passed: Mapped[Optional[bool]] = mapped_column(Boolean)
    confidence: Mapped[Optional[float]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    artifact: Mapped["Artifact"] = relationship("Artifact", backref="evaluations")


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
```

**Step 6: Create Metrics model**

Create `src/artifactforge/db/models_metrics.py`:

```python
"""Metrics models."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

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

    artifact: Mapped["Artifact"] = relationship("Artifact", backref="metrics")


class DailyMetrics(Base):
    """Daily aggregated metrics."""

    __tablename__ = "daily_metrics"

    date: Mapped[datetime.date] = mapped_column(Date, primary_key=True)

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
```

**Step 7: Create Schema and Config models**

Create `src/artifactforge/db/models_schemas.py`:

```python
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
    capabilities: Mapped[list] = mapped_column(JSONB, default_factory=list)
    supported_artifact_types: Mapped[list] = mapped_column(
        JSONB, default_factory=list
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    rate_limit_per_minute: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


__all__ = ["ArtifactSchema", "ToolConfig"]
```

**Step 8: Create Checkpoint model**

Create `src/artifactforge/db/models_checkpoints.py`:

```python
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

    artifact: Mapped["Artifact"] = relationship("Artifact", backref="checkpoints")


__all__ = ["Checkpoint"]
```

**Step 9: Create session module**

Create `src/artifactforge/db/session.py`:

```python
"""Database session management."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from artifactforge.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


__all__ = ["engine", "SessionLocal", "get_db"]
```

**Step 10: Create `src/artifactforge/db/__init__.py`**

```python
"""Database module."""

from artifactforge.db.base import Base
from artifactforge.db.session import engine, get_db, SessionLocal

__all__ = ["Base", "engine", "get_db", "SessionLocal"]
```

---

### Task 1.3: Set Up Alembic Migrations

**Files:**
- Create: `alembic.ini`
- Create: `migrations/env.py`
- Create: `migrations/script.py.mako`

**Step 1: Initialize Alembic**

```bash
cd /Users/pi/Projects/ArtifactForge/artifactforge-design
alembic init migrations
```

**Step 2: Configure `alembic.ini`**

Update the `sqlalchemy.url` in `alembic.ini`:

```ini
sqlalchemy.url = postgresql://artifactforge:artifactforge@localhost:5432/artifactforge
```

**Step 3: Update `migrations/env.py`**

Add the following import and configuration:

```python
# At the top of the file
from artifactforge.db.base import Base
from artifactforge.db import models

# In the run_migrations_offline() function
target_metadata = Base.metadata
```

**Step 4: Create initial migration**

```bash
cd /Users/pi/Projects/ArtifactForge/artifactforge-design
alembic revision --autogenerate -m "initial schema"
```

**Step 5: Verify migration runs successfully**

```bash
cd /Users/pi/Projects/ArtifactForge/artifactforge-design
alembic upgrade head
```

Expected: No errors, tables created

---

### Task 1.4: Verify Phase 1 Complete

**Step 1: Run verification command**

```bash
cd /Users/pi/Projects/ArtifactForge/artifactforge-design
alembic upgrade head
python -c "from artifactforge.db import models; print('OK')"
```

---

## Phase 2: LangGraph Coordinator

### Task 2.1: Build State Machine with Stub Nodes

**Files:**
- Create: `src/artifactforge/coordinator/state.py`
- Create: `src/artifactforge/coordinator/nodes.py`
- Create: `src/artifactforge/coordinator/__init__.py`

**Step 1: Create state definition**

Create `src/artifactforge/coordinator/state.py`:

```python
"""LangGraph state definitions."""

from typing import Annotated, Literal, Optional

from langgraph.graph import add_states
from typing_extensions import TypedDict


class GraphState(TypedDict):
    """Main graph state."""

    # Identification
    artifact_id: Optional[str]
    artifact_type: str
    user_description: str

    # Schema
    schema: Optional[dict]

    # Research Phase
    research_output: Optional[dict]
    research_sources: Optional[list]

    # Generation Phase
    artifact_draft: Optional[str]
    generation_metadata: Optional[dict]

    # Review Phase
    review_results: Optional[list]

    # Verification
    verification_status: Literal["pending", "passed", "failed"]
    verification_errors: Optional[list]

    # User Interaction
    user_questions: Optional[list]
    user_answers: Optional[dict]

    # Errors
    errors: Optional[list]

    # Metadata
    num_retries: int


__all__ = ["GraphState"]
```

**Step 2: Create stub nodes**

Create `src/artifactforge/coordinator/nodes.py`:

```python
"""LangGraph nodes - stub implementations."""

from artifactforge.coordinator.state import GraphState


def router_node(state: GraphState) -> GraphState:
    """Route to appropriate workflow."""
    return {
        "schema": {"type": state["artifact_type"]},
    }


def research_node(state: GraphState) -> GraphState:
    """Research phase - stub."""
    return {
        "research_output": {"stub": "research completed"},
        "research_sources": [],
    }


def generate_node(state: GraphState) -> GraphState:
    """Generation phase - stub."""
    return {
        "artifact_draft": "stub artifact draft",
        "generation_metadata": {"stub": True},
    }


def review_node(state: GraphState) -> GraphState:
    """Review phase - stub."""
    return {
        "review_results": [],
    }


def verify_node(state: GraphState) -> GraphState:
    """Verification phase - stub."""
    return {
        "verification_status": "passed",
    }


def ask_user_node(state: GraphState) -> GraphState:
    """Ask user questions - stub."""
    return {
        "user_questions": [],
    }


def error_node(state: GraphState) -> GraphState:
    """Handle errors - stub."""
    errors = state.get("errors", [])
    errors.append("stub error")
    return {"errors": errors}


__all__ = [
    "router_node",
    "research_node",
    "generate_node",
    "review_node",
    "verify_node",
    "ask_user_node",
    "error_node",
]
```

**Step 3: Create coordinator app**

Create `src/artifactforge/coordinator/__init__.py`:

```python
"""LangGraph coordinator."""

from langgraph.graph import END, StateGraph

from artifactforge.coordinator.state import GraphState
from artifactforge.coordinator import nodes


def create_app() -> StateGraph:
    """Create the LangGraph application."""
    graph = StateGraph(GraphState)

    # Add nodes
    graph.add_node("router", nodes.router_node)
    graph.add_node("research", nodes.research_node)
    graph.add_node("generate", nodes.generate_node)
    graph.add_node("review", nodes.review_node)
    graph.add_node("verify", nodes.verify_node)
    graph.add_node("ask_user", nodes.ask_user_node)

    # Set entry point
    graph.set_entry_point("router")

    # Add edges
    graph.add_edge("router", "research")
    graph.add_edge("research", "generate")
    graph.add_edge("generate", "review")
    graph.add_edge("review", "verify")

    # Conditional edges from verify
    def should_continue(state: GraphState) -> str:
        if state.get("verification_status") == "passed":
            return "end"
        return "ask_user"

    graph.add_conditional_edges(
        "verify",
        should_continue,
        {
            "end": END,
            "ask_user": "ask_user",
        },
    )

    graph.add_edge("ask_user", "research")

    return graph


# Compile the app
app = create_app().compile()


__all__ = ["app", "create_app"]
```

---

### Task 2.2: Add PostgreSQL Checkpointer

**Step 1: Install PostgreSQL checkpointer**

The LangGraph PostgreSQL checkpointer requires `langgraph.checkpoint`:

```bash
pip install langgraph-checkpoint-postgres
```

**Step 2: Update coordinator to use checkpointer**

Update `src/artifactforge/coordinator/__init__.py`:

```python
"""LangGraph coordinator with PostgreSQL checkpointing."""

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, StateGraph

from artifactforge.coordinator.state import GraphState
from artifactforge.coordinator import nodes
from artifactforge.config import get_settings

settings = get_settings()


def create_app() -> StateGraph:
    """Create the LangGraph application."""
    graph = StateGraph(GraphState)

    # Add nodes
    graph.add_node("router", nodes.router_node)
    graph.add_node("research", nodes.research_node)
    graph.add_node("generate", nodes.generate_node)
    graph.add_node("review", nodes.review_node)
    graph.add_node("verify", nodes.verify_node)
    graph.add_node("ask_user", nodes.ask_user_node)

    # Set entry point
    graph.set_entry_point("router")

    # Add edges
    graph.add_edge("router", "research")
    graph.add_edge("research", "generate")
    graph.add_edge("generate", "review")
    graph.add_edge("review", "verify")

    # Conditional edges from verify
    def should_continue(state: GraphState) -> str:
        if state.get("verification_status") == "passed":
            return "end"
        return "ask_user"

    graph.add_conditional_edges(
        "verify",
        should_continue,
        {
            "end": END,
            "ask_user": "ask_user",
        },
    )

    graph.add_edge("ask_user", "research")

    return graph


def get_checkpointer() -> PostgresSaver:
    """Get PostgreSQL checkpointer."""
    return PostgresSaver.from_conn_string(settings.database_url)


# Compile the app with checkpointer
checkpointer = get_checkpointer()
app = create_app().compile(checkpointer=checkpointer)


__all__ = ["app", "create_app", "get_checkpointer"]
```

---

### Task 2.3: Verify Phase 2 Complete

**Step 1: Run verification command**

```bash
cd /Users/pi/Projects/ArtifactForge/artifactforge-design
python -c "from artifactforge.coordinator import app; print('OK')"
```

Expected: `OK`

---

## Phase 3: Tools (Research)

### Task 3.1: Implement WebSearcher Tool (Stub)

**Files:**
- Create: `src/artifactforge/tools/__init__.py`
- Create: `src/artifactforge/tools/research/__init__.py`
- Create: `src/artifactforge/tools/research/web_searcher.py`

**Step 1: Create research tools module**

Create `src/artifactforge/tools/research/web_searcher.py`:

```python
"""Web searcher tool - stub implementation."""

from typing import Any, Dict, List

from langchain_core.tools import tool


class WebSearchInput(BaseModel):
    """Input for web searcher."""

    query: str = Field(description="The search query")
    num_results: int = Field(default=10, description="Number of results")


@tool(args_schema=WebSearchInput)
def web_searcher(query: str, num_results: int = 10) -> Dict[str, Any]:
    """Search the web for information. Returns URLs and summaries.

    This is a stub implementation that returns mock data.
    """
    # Stub: Return mock search results
    return {
        "query": query,
        "results": [
            {
                "title": f"Result {i+1} for {query}",
                "url": f"https://example.com/result-{i+1}",
                "snippet": f"This is a mock search result for: {query}",
            }
            for i in range(num_results)
        ],
        "sources": [f"https://example.com/result-{i+1}" for i in range(num_results)],
    }


__all__ = ["web_searcher"]
```

---

### Task 3.2: Implement DeepAnalyzer Tool

**Files:**
- Create: `src/artifactforge/tools/research/deep_analyzer.py`

**Step 1: Create deep analyzer tool**

Create `src/artifactforge/tools/research/deep_analyzer.py`:

```python
"""Deep analyzer tool - analyzes search results."""

from typing import Any, Dict, List

from langchain_core.tools import tool


class DeepAnalyzeInput(BaseModel):
    """Input for deep analyzer."""

    sources: List[str] = Field(description="List of URLs to analyze")
    query: str = Field(description="Original query context")


@tool(args_schema=DeepAnalyzeInput)
def deep_analyzer(sources: List[str], query: str) -> Dict[str, Any]:
    """Analyze search results in depth, extracting key information.

    This is a stub implementation that returns mock analysis.
    """
    # Stub: Return mock analysis
    return {
        "query": query,
        "sources": sources,
        "analysis": {
            "key_findings": [
                "Stub finding 1",
                "Stub finding 2",
            ],
            "summary": f"Mock analysis of {len(sources)} sources for: {query}",
        },
    }


__all__ = ["deep_analyzer"]
```

**Step 2: Create research tools __init__**

Create `src/artifactforge/tools/research/__init__.py`:

```python
"""Research tools."""

from artifactforge.tools.research.web_searcher import web_searcher
from artifactforge.tools.research.deep_analyzer import deep_analyzer

__all__ = ["web_searcher", "deep_analyzer"]
```

**Step 3: Create tools __init__**

Create `src/artifactforge/tools/__init__.py`:

```python
"""ArtifactForge tools."""

from artifactforge.tools.research import web_searcher, deep_analyzer

__all__ = ["web_searcher", "deep_analyzer"]
```

---

### Task 3.3: Verify Phase 3 Complete

**Step 1: Run verification command**

```bash
cd /Users/pi/Projects/ArtifactForge/artifactforge-design
python -c "from artifactforge.tools.research import web_searcher; print('OK')"
```

Expected: `OK`

---

## Phase 4: Generation (Generic)

### Task 4.1: Implement Schema-Based Generator

**Files:**
- Create: `src/artifactforge/tools/generate/__init__.py`
- Create: `src/artifactforge/tools/generic_generator.py`

**Step 1: Create generic generator**

Create `src/artifactforge/tools/generic_generator.py`:

```python
"""Generic generator tool - schema-based artifact generation."""

from typing import Any, Dict, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class GenerateInput(BaseModel):
    """Input for generic generator."""

    artifact_type: str = Field(description="Type of artifact to generate")
    schema: Dict[str, Any] = Field(description="Artifact schema definition")
    context: Dict[str, Any] = Field(description="Research context")
    user_description: str = Field(description="Original user description")


@tool(args_schema=GenerateInput)
def generic_generator(
    artifact_type: str,
    schema: Dict[str, Any],
    context: Dict[str, Any],
    user_description: str,
) -> Dict[str, Any]:
    """Generate an artifact based on schema and context.

    This is a stub implementation.
    """
    # Stub: Return mock generated artifact
    return {
        "artifact_type": artifact_type,
        "draft": f"Mock artifact draft for: {user_description}",
        "metadata": {
            "confidence": 0.5,
            "requires_review": ["generic"],
        },
    }


__all__ = ["generic_generator"]
```

---

### Task 4.2: Add One Example Artifact Type (Simple Report)

**Step 1: Create example schema module**

Create `src/artifactforge/schemas/__init__.py`:

```python
"""Artifact schemas."""

from artifactforge.schemas.simple_report import generate_simple_report

__all__ = ["generate_simple_report"]
```

Create `src/artifactforge/schemas/simple_report.py`:

```python
"""Simple report schema and generator."""


def generate_simple_report(user_description: str, context: dict) -> str:
    """Generate a simple report artifact.

    This is a stub implementation.
    """
    return f"""
# Simple Report

## Description
{user_description}

## Research Context
{context.get('summary', 'No research available')}

## Content
This is a stub report generated from: {user_description}
"""


__all__ = ["generate_simple_report"]
```

---

### Task 4.3: Verify Phase 4 Complete

**Step 1: Run verification command**

```bash
cd /Users/pi/Projects/ArtifactForge/artifactforge-design
python -c "from artifactforge.tools.generic_generator import generic_generator; print('OK')"
```

Expected: `OK`

---

## Phase 5: Review + Verification

### Task 5.1: Implement Generic Reviewer

**Files:**
- Create: `src/artifactforge/tools/review/__init__.py`
- Create: `src/artifactforge/tools/review/generic_reviewer.py`

**Step 1: Create generic reviewer**

Create `src/artifactforge/tools/review/generic_reviewer.py`:

```python
"""Generic reviewer tool."""

from typing import Any, Dict, List

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class ReviewInput(BaseModel):
    """Input for generic reviewer."""

    artifact_type: str = Field(description="Type of artifact")
    draft: str = Field(description="Artifact draft to review")
    context: Dict[str, Any] = Field(description="Research context")


@tool(args_schema=ReviewInput)
def generic_reviewer(artifact_type: str, draft: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Review artifact draft for quality.

    This is a stub implementation.
    """
    # Stub: Return mock review
    return {
        "passed": True,
        "issues": [],
        "suggestions": [],
        "scores": {
            "completeness": 0.5,
            "clarity": 0.5,
            "accuracy": 0.5,
        },
    }


__all__ = ["generic_reviewer"]
```

Create `src/artifactforge/tools/review/__init__.py`:

```python
"""Review tools."""

from artifactforge.tools.review.generic_reviewer import generic_reviewer

__all__ = ["generic_reviewer"]
```

---

### Task 5.2: Add Quality Gates Framework

**Files:**
- Create: `src/artifactforge/verification/__init__.py`
- Create: `src/artifactforge/verification/gates.py`

**Step 1: Create quality gates framework**

Create `src/artifactforge/verification/gates.py`:

```python
"""Quality gates framework."""

from typing import Any, Dict, List, Protocol
from pydantic import BaseModel, Field


class GateResult(BaseModel):
    """Result of a quality gate check."""

    name: str
    passed: bool
    score: float = Field(default=0.0)
    details: Dict[str, Any] = Field(default_factory=dict)


class QualityGate(Protocol):
    """Protocol for quality gates."""

    name: str

    def check(self, artifact: Dict[str, Any]) -> GateResult:
        """Check if artifact passes this gate."""
        ...


class GateRunner:
    """Runs quality gates on artifacts."""

    def __init__(self, gates: List[QualityGate]):
        self.gates = gates

    def run(self, artifact: Dict[str, Any]) -> List[GateResult]:
        """Run all gates on artifact."""
        results = []
        for gate in self.gates:
            result = gate.check(artifact)
            results.append(result)
        return results

    def all_passed(self, results: List[GateResult]) -> bool:
        """Check if all gates passed."""
        return all(r.passed for r in results)


# Stub gates
class CompletenessGate:
    """Checks artifact completeness."""

    name = "completeness"

    def check(self, artifact: Dict[str, Any]) -> GateResult:
        return GateResult(
            name=self.name,
            passed=True,
            score=0.5,
            details={"message": "Stub completeness check"},
        )


class QualityGateRunner:
    """Stub quality gate runner."""

    def __init__(self, gates: List[QualityGate] = None):
        self.gates = gates or [CompletenessGate()]

    def run(self, artifact: Dict[str, Any]) -> List[GateResult]:
        return [gate.check(artifact) for gate in self.gates]


__all__ = ["GateResult", "QualityGate", "GateRunner", "QualityGateRunner"]
```

---

### Task 5.3: Create CLI Entry Point

**Files:**
- Create: `src/artifactforge/cli/__init__.py`
- Create: `src/artifactforge/cli/main.py`

**Step 1: Create CLI module**

Create `src/artifactforge/cli/main.py`:

```python
"""CLI entry point for ArtifactForge."""

import asyncio
from typing import Optional

import structlog
from pydantic import BaseModel

from artifactforge.config import get_settings
from artifactforge.coordinator import app

logger = structlog.get_logger(__name__)
settings = get_settings()


class GenerateInput(BaseModel):
    """Input for generate command."""

    artifact_type: str
    description: str


async def generate(artifact_type: str, description: str) -> dict:
    """Generate an artifact."""
    initial_state = {
        "artifact_type": artifact_type,
        "user_description": description,
        "verification_status": "pending",
        "num_retries": 0,
    }

    result = await app.ainvoke(initial_state)
    return result


def main():
    """Main CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="ArtifactForge CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate an artifact")
    gen_parser.add_argument("type", help="Artifact type (e.g., rfp, report)")
    gen_parser.add_argument("description", help="Artifact description")

    args = parser.parse_args()

    if args.command == "generate":
        result = asyncio.run(generate(args.type, args.description))
        print(result)


if __name__ == "__main__":
    main()
```

Create `src/artifactforge/cli/__init__.py`:

```python
"""CLI module."""

from artifactforge.cli.main import main

__all__ = ["main"]
```

---

### Task 5.4: Verify Phase 5 Complete

**Step 1: Run verification command**

```bash
cd /Users/pi/Projects/ArtifactForge/artifactforge-design
python -c "from artifactforge.cli import main; print('OK')"
```

Expected: `OK`

---

## Final Verification

**Run all verification commands:**

```bash
# Phase 1
cd /Users/pi/Projects/ArtifactForge/artifactforge-design
alembic upgrade head

# Phase 2
python -c "from artifactforge.coordinator import app; print('OK')"

# Phase 3
python -c "from artifactforge.tools.research import web_searcher; print('OK')"

# Phase 4
python -c "from artifactforge.tools.generic_generator import generic_generator; print('OK')"

# Phase 5
python -c "from artifactforge.cli import main; print('OK')"
```

All should output: `OK`

---

## Summary

| Phase | Tasks | Status |
|-------|-------|--------|
| Phase 1: Foundation | 1.1-1.4 | - |
| Phase 2: LangGraph Coordinator | 2.1-2.3 | - |
| Phase 3: Tools (Research) | 3.1-3.3 | - |
| Phase 4: Generation | 4.1-4.3 | - |
| Phase 5: Review + Verification | 5.1-5.4 | - |

---

**Plan complete and saved to `docs/plans/2026-03-27-artifactforge-bootstrap.md`**.

## Execution Options

Two execution options:

1. **Subagent-Driven (this session)** - Dispatch fresh subagent per task, review between tasks, fast iteration

2. **Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?

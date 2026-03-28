# ArtifactForge Database Schema Design

> **System:** ArtifactForge  
> **Purpose:** Unified knowledge artifact generation pipeline  
> **Database:** PostgreSQL (Docker)  
> **Designed as:** Senior Database Architect  

---

## 1. Design Philosophy & Principles

### 1.1 Core Principles

| Principle | Implementation |
|-----------|---------------|
| **Normalization** | 3NF minimum - no redundant data, foreign key integrity |
| **Domain-Driven** | Table names reflect business concepts, not technical artifacts |
| **Audit Trail** | Every significant action is traceable |
| **Performance** | Indexes on query patterns, not just foreign keys |
| **Evolutability** | Schema supports versioning, migrations are reversible |

### 1.2 Data Model Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CORE ENTITIES                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────┐     ┌──────────────┐     ┌─────────────┐                  │
│   │  Users   │────▶│   Sessions   │────▶│  Artifacts  │                  │
│   └──────────┘     └──────────────┘     └──────┬──────┘                  │
│                                                  │                          │
│                                                  ▼                          │
│   ┌──────────────┐     ┌─────────────┐     ┌─────────────┐               │
│   │  Schemas     │◀────│ ToolConfigs │     │ Executions  │               │
│   └──────────────┘     └─────────────┘     └──────┬──────┘               │
│                                                     │                       │
│   ┌──────────────┐     ┌─────────────┐             │                       │
│   │  Learnings   │     │  Knowledge  │◀────────────┘                       │
│   └──────────────┘     └─────────────┘                                    │
│                                                                             │
│                         QUALITY & FEEDBACK                                 │
│   ┌──────────────┐     ┌─────────────┐     ┌─────────────┐               │
│   │ Evaluations  │     │HumanFeedback│     │ Metrics     │               │
│   └──────────────┘     └─────────────┘     └─────────────┘               │
│                                                                             │
│                         OBSERVABILITY                                       │
│   ┌──────────────┐     ┌─────────────┐                                    │
│   │Exec Traces   │     │ Exec Logs   │                                    │
│   └──────────────┘     └─────────────┘                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Tables

### 2.1 Users

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(100),
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    
    -- Authentication
    password_hash VARCHAR(255),
    api_key VARCHAR(64) UNIQUE,
    
    -- Preferences
    preferences JSONB DEFAULT '{}',
    
    -- Tracking
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE
);

-- Indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_api_key ON users(api_key) WHERE api_key IS NOT NULL;
CREATE INDEX idx_users_role ON users(role);

-- Constraints
ALTER TABLE users ADD CONSTRAINT chk_role CHECK (
    role IN ('user', 'admin', 'viewer')
);
```

**Rationale:**
- `UUID` for distributed system compatibility
- Separate `password_hash` and `api_key` for multiple auth methods
- `JSONB` for flexible preferences without schema changes

---

### 2.2 Sessions

```sql
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Session info
    title VARCHAR(255),
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    
    -- Context for this session
    context JSONB DEFAULT '{}',
    
    -- Lifecycle
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    last_activity_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Metadata
    metadata JSONB DEFAULT '{}'
);

-- Indexes
CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_status ON sessions(status);
CREATE INDEX idx_sessions_last_activity ON sessions(last_activity_at DESC);

-- Constraints
ALTER TABLE sessions ADD CONSTRAINT chk_session_status CHECK (
    status IN ('active', 'paused', 'completed', 'cancelled')
);
```

**Rationale:**
- Sessions group related artifacts together
- `last_activity_at` enables cleanup of stale sessions
- `context` stores runtime state that can be resumed

---

### 2.3 Artifacts (Core Entity)

```sql
CREATE TABLE artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    
    -- Identification
    type VARCHAR(50) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    
    -- Input
    user_description TEXT NOT NULL,
    input_schema JSONB,
    input_context JSONB,
    
    -- Research Phase
    research_context JSONB,
    research_sources JSONB,
    
    -- Generation Phase
    artifact_draft TEXT,
    generation_metadata JSONB,
    
    -- Review Phase
    review_results JSONB,
    
    -- Verification
    verification_status VARCHAR(20) DEFAULT 'pending',
    verification_errors JSONB,
    verification_gates JSONB,
    
    -- Lifecycle
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Evolution (from pnc_rfp)
    parent_id UUID REFERENCES artifacts(id),
    resume_mode VARCHAR(20),
    
    -- Output
    final_artifact JSONB,
    output_format VARCHAR(20),
    
    -- Metadata
    metadata JSONB DEFAULT '{}'
);

-- Indexes
CREATE INDEX idx_artifacts_session ON artifacts(session_id);
CREATE INDEX idx_artifacts_user ON artifacts(user_id);
CREATE INDEX idx_artifacts_type ON artifacts(type);
CREATE INDEX idx_artifacts_status ON artifacts(status);
CREATE INDEX idx_artifacts_created ON artifacts(created_at DESC);
CREATE INDEX idx_artifacts_parent ON artifacts(parent_id);

-- Constraints
ALTER TABLE artifacts ADD CONSTRAINT chk_artifact_status CHECK (
    status IN ('pending', 'researching', 'generating', 'reviewing', 
               'verifying', 'completed', 'failed', 'cancelled')
);

ALTER TABLE artifacts ADD CONSTRAINT chk_verification_status CHECK (
    verification_status IN ('pending', 'passed', 'failed', 'skipped')
);

ALTER TABLE artifacts ADD CONSTRAINT chk_resume_mode CHECK (
    resume_mode IN ('preserve', 'enhance', 'replace', NULL)
);
```

**Rationale:**
- Single source of truth for artifact lifecycle
- All phases stored as JSONB - flexible schema per artifact type
- `parent_id` enables iteration/evolution workflow
- Gates stored explicitly for auditability

---

### 2.4 Artifact Versions

```sql
CREATE TABLE artifact_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    
    -- Snapshot of artifact at this version
    snapshot JSONB NOT NULL,
    
    -- Change info
    change_summary TEXT,
    change_reason VARCHAR(50),
    
    -- Quality at this version
    evaluation_score DECIMAL(5, 4),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES users(id)
);

-- Indexes
CREATE INDEX idx_artifact_versions_artifact ON artifact_versions(artifact_id, version DESC);
CREATE UNIQUE INDEX idx_artifact_versions_unique ON artifact_versions(artifact_id, version);

-- Constraints
ALTER TABLE artifact_versions ADD CONSTRAINT chk_version_positive CHECK (version > 0);
```

**Rationale:**
- Full history of artifact changes
- Enables rollback capability
- Tracks what changed and why

---

## 3. Schema Registry

### 3.1 Artifact Schemas

```sql
CREATE TABLE artifact_schemas (
    type VARCHAR(50) PRIMARY KEY,
    version VARCHAR(20) NOT NULL,
    
    -- Schema definition
    schema_definition JSONB NOT NULL,
    
    -- Tool requirements
    research_config JSONB,
    generation_config JSONB,
    review_config JSONB,
    output_config JSONB,
    
    -- Quality gates for this schema
    quality_gates JSONB,
    
    -- Metadata
    description TEXT,
    examples JSONB,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES users(id),
    
    is_active BOOLEAN DEFAULT TRUE
);

-- Indexes
CREATE INDEX idx_artifact_schemas_active ON artifact_schemas(type) WHERE is_active = TRUE;
```

**Rationale:**
- Declarative schema definitions stored in DB
- Enables runtime schema updates without code changes
- Quality gates defined per artifact type

---

### 3.2 Tool Configurations

```sql
CREATE TABLE tool_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) UNIQUE NOT NULL,
    type VARCHAR(50) NOT NULL,  -- 'research', 'generate', 'review'
    
    -- Tool definition
    tool_definition JSONB NOT NULL,
    
    -- Capabilities
    capabilities JSONB DEFAULT '[]',
    supported_artifact_types JSONB DEFAULT '[]',
    
    -- Configuration
    is_active BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,
    
    -- Rate limiting (not primary, but available)
    rate_limit_per_minute INTEGER,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_tool_configs_type ON tool_configs(type);
CREATE INDEX idx_tool_configs_active ON tool_configs(is_active) WHERE is_active = TRUE;
```

---

## 4. Self-Evolution System

### 4.1 Learnings

```sql
CREATE TABLE learnings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_type VARCHAR(50) NOT NULL,
    
    -- What happened
    context TEXT NOT NULL,  -- What was the situation?
    failure_mode TEXT NOT NULL,  -- What went wrong
    
    -- What was done
    fix_applied TEXT,
    outcome VARCHAR(20) NOT NULL,
    
    -- Confidence tracking
    confidence DECIMAL(3, 2) DEFAULT 0.5,
    times_applied INTEGER DEFAULT 0,
    times_succeeded INTEGER DEFAULT 0,
    
    -- Source
    source VARCHAR(50) NOT NULL,  -- 'auto', 'human'
    artifact_id UUID REFERENCES artifacts(id) ON DELETE SET NULL,
    
    -- Validation
    is_validated BOOLEAN DEFAULT FALSE,
    validated_at TIMESTAMP WITH TIME ZONE,
    validated_by UUID REFERENCES users(id),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE  -- For time-based decay
);

-- Indexes
CREATE INDEX idx_learnings_type ON learnings(artifact_type);
CREATE INDEX idx_learnings_outcome ON learnings(outcome);
CREATE INDEX idx_learnings_confidence ON learnings(confidence DESC);
CREATE INDEX idx_learnings_validated ON learnings(is_validated) WHERE is_validated = FALSE;
CREATE INDEX idx_learnings_expires ON learnings(expires_at) WHERE expires_at IS NOT NULL;

-- Constraints
ALTER TABLE learnings ADD CONSTRAINT chk_learning_outcome CHECK (
    outcome IN ('success', 'still_failed', 'partial')
);
```

**Rationale:**
- Automatic capture of failure patterns
- Confidence tracking for self-validation
- Expiration for temporal learnings

---

### 4.2 Knowledge

```sql
CREATE TABLE knowledge (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_type VARCHAR(50) NOT NULL,
    category VARCHAR(50) NOT NULL,  -- 'pattern', 'guideline', 'template', 'example'
    
    -- Content
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    
    -- Provenance
    source VARCHAR(50) NOT NULL,  -- 'human', 'learned', 'imported'
    source_reference TEXT,
    created_by UUID REFERENCES users(id),
    
    -- Usage tracking
    times_used INTEGER DEFAULT 0,
    last_used_at TIMESTAMP WITH TIME ZONE,
    
    -- Validation
    is_verified BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMP WITH TIME ZONE,
    verified_by UUID REFERENCES users(id),
    
    -- Lifecycle
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deprecated_at TIMESTAMP WITH TIME ZONE
);

-- Indexes
CREATE INDEX idx_knowledge_type ON knowledge(artifact_type);
CREATE INDEX idx_knowledge_category ON knowledge(category);
CREATE INDEX idx_knowledge_status ON knowledge(status);
CREATE INDEX idx_knowledge_verified ON knowledge(is_verified) WHERE is_verified = TRUE;
CREATE INDEX idx_knowledge_usage ON knowledge(times_used DESC);

-- Constraints
ALTER TABLE knowledge ADD CONSTRAINT chk_knowledge_category CHECK (
    category IN ('pattern', 'guideline', 'template', 'example', 'invariant')
);

ALTER TABLE knowledge ADD CONSTRAINT chk_knowledge_status CHECK (
    status IN ('active', 'deprecated', 'archived')
);
```

**Rationale:**
- Curated, human-maintained patterns
- Usage tracking identifies valuable knowledge
- Deprecation without deletion preserves history

---

### 4.3 Knowledge-Artifact Junction

```sql
CREATE TABLE artifact_knowledge (
    artifact_id UUID NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    knowledge_id UUID NOT NULL REFERENCES knowledge(id) ON DELETE CASCADE,
    
    -- How was this knowledge used?
    usage_type VARCHAR(50) NOT NULL,  -- 'context', 'reference', 'template'
    relevance_score DECIMAL(3, 2),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    PRIMARY KEY (artifact_id, knowledge_id)
);

-- Indexes
CREATE INDEX idx_artifact_knowledge_knowledge ON artifact_knowledge(knowledge_id);
```

---

## 5. Execution & Tracing

### 5.1 Executions (Top-Level)

```sql
CREATE TABLE executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    
    -- Execution context
    phase VARCHAR(50) NOT NULL,  -- 'research', 'generate', 'review', 'verify'
    step VARCHAR(100) NOT NULL,  -- 'web_search', 'rfp_generator', etc.
    
    -- Tool configuration
    tool_config_id UUID REFERENCES tool_configs(id),
    
    -- Input/Output
    input JSONB,
    output JSONB,
    
    -- Timing
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_ms INTEGER,
    
    -- Tokens (for cost tracking)
    input_tokens INTEGER,
    output_tokens INTEGER,
    
    -- Outcome
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    error_message TEXT,
    error_details JSONB,
    
    -- Retry tracking
    attempt_number INTEGER DEFAULT 1,
    previous_execution_id UUID REFERENCES executions(id),
    
    metadata JSONB DEFAULT '{}'
);

-- Indexes
CREATE INDEX idx_executions_artifact ON executions(artifact_id);
CREATE INDEX idx_executions_artifact_phase ON executions(artifact_id, phase);
CREATE INDEX idx_executions_status ON executions(status);
CREATE INDEX idx_executions_started ON executions(started_at DESC);

-- Constraints
ALTER TABLE executions ADD CONSTRAINT chk_execution_status CHECK (
    status IN ('running', 'success', 'failed', 'timeout', 'cancelled')
);
```

**Rationale:**
- Granular execution tracking
- Parent-child relationships for retries
- Full input/output for debugging

---

### 5.2 Execution Traces (Detailed)

```sql
CREATE TABLE execution_traces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id UUID NOT NULL REFERENCES executions(id) ON DELETE CASCADE,
    
    -- Trace info
    trace_type VARCHAR(50) NOT NULL,  -- 'llm_call', 'tool_call', 'state_change'
    layer VARCHAR(50),  -- 'research', 'generate', 'review'
    
    -- Data
    data JSONB NOT NULL,
    
    -- Timing
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    sequence_number INTEGER NOT NULL,
    
    metadata JSONB DEFAULT '{}'
);

-- Indexes
CREATE INDEX idx_traces_execution ON execution_traces(execution_id);
CREATE INDEX idx_traces_type ON execution_traces(trace_type);
CREATE INDEX idx_traces_sequence ON execution_traces(execution_id, sequence_number);
```

**Rationale:**
- Detailed trace for debugging complex failures
- Sequence numbers enable reconstruction of execution order

---

### 5.3 Execution Logs

```sql
CREATE TABLE execution_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID REFERENCES artifacts(id) ON DELETE SET NULL,
    execution_id UUID REFERENCES executions(id) ON DELETE SET NULL,
    
    -- Log info
    level VARCHAR(10) NOT NULL,  -- 'DEBUG', 'INFO', 'WARN', 'ERROR'
    component VARCHAR(50) NOT NULL,  -- 'coordinator', 'tool', 'verifier', 'router'
    message TEXT NOT NULL,
    
    -- Structured context
    context JSONB DEFAULT '{}',
    
    -- For correlation
    trace_id UUID,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_logs_artifact ON execution_logs(artifact_id);
CREATE INDEX idx_logs_execution ON execution_logs(execution_id);
CREATE INDEX idx_logs_level ON execution_logs(level);
CREATE INDEX idx_logs_component ON execution_logs(component);
CREATE INDEX idx_logs_created ON execution_logs(created_at DESC);

-- Partitioning candidate for high-volume logs
-- CREATE INDEX idx_logs_created_partition ON execution_logs(created_at DESC);

-- Constraints
ALTER TABLE execution_logs ADD CONSTRAINT chk_log_level CHECK (
    level IN ('DEBUG', 'INFO', 'WARN', 'ERROR', 'FATAL')
);
```

---

## 6. Quality Assurance

### 6.1 Evaluations

```sql
CREATE TABLE evaluations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    execution_id UUID REFERENCES executions(id),
    
    -- Evaluation type
    evaluation_type VARCHAR(20) NOT NULL,  -- 'auto', 'human', 'gate'
    evaluator VARCHAR(50),  -- 'llm_judge', 'specific_reviewer', 'user'
    
    -- Quality scores (0-1)
    completeness_score DECIMAL(5, 4),
    clarity_score DECIMAL(5, 4),
    accuracy_score DECIMAL(5, 4),
    quality_score DECIMAL(5, 4),
    overall_score DECIMAL(5, 4),
    
    -- Detailed feedback
    issues JSONB DEFAULT '[]',
    suggestions JSONB DEFAULT '[]',
    strengths JSONB DEFAULT '[]',
    
    -- Pass/fail
    passed BOOLEAN,
    confidence DECIMAL(3, 2),
    
    -- Evaluation criteria used
    criteria JSONB,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_evaluations_artifact ON evaluations(artifact_id);
CREATE INDEX idx_evaluations_type ON evaluations(evaluation_type);
CREATE INDEX idx_evaluations_passed ON evaluations(passed);
CREATE INDEX idx_evaluations_created ON evaluations(created_at DESC);
```

**Rationale:**
- LLM-as-Judge results stored for review
- Granular scores enable targeted improvement
- Issues/suggestions enable iterative refinement

---

### 6.2 Human Feedback

```sql
CREATE TABLE human_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    
    -- Ratings (1-5)
    usefulness INTEGER,
    accuracy INTEGER,
    quality INTEGER,
    overall_rating INTEGER,
    
    -- Qualitative
    feedback TEXT,
    would_regenerate BOOLEAN,
    
    -- Specific concerns
    concerns JSONB DEFAULT '[]',
    praised JSONB DEFAULT '[]',
    
    -- Follow-up
    requested_changes TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_human_feedback_artifact ON human_feedback(artifact_id);
CREATE INDEX idx_human_feedback_user ON human_feedback(user_id);
CREATE INDEX idx_human_feedback_created ON human_feedback(created_at DESC);

-- Constraints
ALTER TABLE human_feedback ADD CONSTRAINT chk_rating_range CHECK (
    (usefulness IS NULL OR (usefulness >= 1 AND usefulness <= 5)) AND
    (accuracy IS NULL OR (accuracy >= 1 AND accuracy <= 5)) AND
    (quality IS NULL OR (quality >= 1 AND quality <= 5)) AND
    (overall_rating IS NULL OR (overall_rating >= 1 AND overall_rating <= 5))
);
```

---

### 6.3 Quality Gates History

```sql
CREATE TABLE quality_gate_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    execution_id UUID REFERENCES executions(id),
    
    -- Gate info
    gate_name VARCHAR(100) NOT NULL,
    gate_type VARCHAR(50),  -- 'llm', 'deterministic', 'invariant'
    
    -- Result
    passed BOOLEAN NOT NULL,
    score DECIMAL(5, 4),
    details JSONB,
    
    -- Retry info
    attempt INTEGER DEFAULT 1,
    was_retried BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_gate_results_artifact ON quality_gate_results(artifact_id);
CREATE INDEX idx_gate_results_gate ON quality_gate_results(gate_name);
CREATE INDEX idx_gate_results_passed ON quality_gate_results(passed);
```

---

## 7. Metrics & Analytics

### 7.1 Artifact Metrics

```sql
CREATE TABLE artifact_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    
    -- Timing (milliseconds)
    total_duration_ms INTEGER,
    research_duration_ms INTEGER,
    generate_duration_ms INTEGER,
    review_duration_ms INTEGER,
    verify_duration_ms INTEGER,
    
    -- Tokens
    total_input_tokens INTEGER,
    total_output_tokens INTEGER,
    research_tokens INTEGER,
    generation_tokens INTEGER,
    review_tokens INTEGER,
    
    -- Costs (configurable price per 1M tokens)
    estimated_cost_cents DECIMAL(10, 4),
    
    -- Quality
    evaluation_score DECIMAL(5, 4),
    human_rating INTEGER,
    
    -- Counts
    num_retries INTEGER,
    num_user_questions INTEGER,
    num_tools_used INTEGER,
    num_gates_passed INTEGER,
    num_gates_failed INTEGER,
    
    -- Research
    num_sources_collected INTEGER,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_artifact_metrics_artifact ON artifact_metrics(artifact_id);
CREATE INDEX idx_artifact_metrics_created ON artifact_metrics(created_at DESC);
```

---

### 7.2 Daily Aggregations

```sql
CREATE TABLE daily_metrics (
    date DATE PRIMARY KEY,
    
    -- Volume
    artifacts_created INTEGER DEFAULT 0,
    artifacts_completed INTEGER DEFAULT 0,
    artifacts_failed INTEGER DEFAULT 0,
    
    -- Timing (averages)
    avg_total_duration_ms INTEGER,
    avg_research_duration_ms INTEGER,
    avg_generate_duration_ms INTEGER,
    avg_review_duration_ms INTEGER,
    
    -- Tokens (totals)
    total_input_tokens BIGINT,
    total_output_tokens BIGINT,
    
    -- Costs
    total_cost_cents DECIMAL(12, 4),
    
    -- Quality
    avg_evaluation_score DECIMAL(5, 4),
    avg_human_rating DECIMAL(3, 2),
    
    -- Rates
    success_rate DECIMAL(5, 4),
    retry_rate DECIMAL(5, 4),
    question_rate DECIMAL(5, 4),
    
    -- Artifact types
    by_type JSONB DEFAULT '{}',
    
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index
CREATE INDEX idx_daily_metrics_date ON daily_metrics(date DESC);
```

---

### 7.3 User Activity

```sql
CREATE TABLE user_activity (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    
    -- Activity
    activity_type VARCHAR(50) NOT NULL,
    
    -- Context
    artifact_id UUID REFERENCES artifacts(id) ON DELETE SET NULL,
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    
    -- Details
    details JSONB DEFAULT '{}',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_user_activity_user ON user_activity(user_id);
CREATE INDEX idx_user_activity_type ON user_activity(activity_type);
CREATE INDEX idx_user_activity_created ON user_activity(created_at DESC);

-- Constraints
ALTER TABLE user_activity ADD CONSTRAINT chk_activity_type CHECK (
    activity_type IN ('created_artifact', 'viewed_artifact', 'provided_feedback', 
                     'asked_question', 'downloaded_artifact', 'shared_artifact')
);
```

---

## 8. User Interactions

### 8.1 User Questions

```sql
CREATE TABLE user_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    
    -- Question
    question_text TEXT NOT NULL,
    context TEXT,  -- What we know so far
    
    -- Options (if multiple choice)
    options JSONB,
    
    -- Resolution
    is_blocking BOOLEAN DEFAULT TRUE,
    answered_at TIMESTAMP WITH TIME ZONE,
    answer TEXT,
    selected_option VARCHAR(255),
    
    -- If unanswered/answered with assumption
    proceeded_without_answer BOOLEAN DEFAULT FALSE,
    assumption_made TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_user_questions_artifact ON user_questions(artifact_id);
CREATE INDEX idx_user_questions_blocking ON user_questions(is_blocking) WHERE answered_at IS NULL;
```

---

### 8.2 API Keys

```sql
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Key info
    name VARCHAR(100) NOT NULL,
    key_hash VARCHAR(64) NOT NULL,  -- SHA-256 prefix stored
    key_prefix VARCHAR(8) NOT NULL,  -- First 8 chars for display
    
    -- Limits
    rate_limit_per_minute INTEGER,
    monthly_token_limit INTEGER,
    tokens_used_this_month INTEGER DEFAULT 0,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    
    -- Expiry
    expires_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_api_keys_user ON api_keys(user_id);
CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_active ON api_keys(is_active) WHERE is_active = TRUE;
```

---

## 9. Checkpointing (LangGraph)

### 9.1 State Checkpoints

```sql
CREATE TABLE checkpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    
    -- Checkpoint info
    step VARCHAR(50) NOT NULL,
    node VARCHAR(100) NOT NULL,
    
    -- State snapshot
    state JSONB NOT NULL,
    
    -- Metadata
    parent_checkpoint_id UUID REFERENCES checkpoints(id),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_checkpoints_artifact ON checkpoints(artifact_id);
CREATE INDEX idx_checkpoints_step ON checkpoints(artifact_id, step);
CREATE INDEX idx_checkpoints_created ON checkpoints(created_at DESC);

-- Note: LangGraph's PostgresSaver will create its own tables
-- This table is for application-level checkpoints if needed
```

---

## 10. Summary Table

### Table Count: 18 Core Tables

| Category | Tables |
|----------|--------|
| **Core** | `users`, `sessions`, `artifacts`, `artifact_versions` |
| **Schema Registry** | `artifact_schemas`, `tool_configs` |
| **Evolution** | `learnings`, `knowledge`, `artifact_knowledge` |
| **Execution** | `executions`, `execution_traces`, `execution_logs` |
| **Quality** | `evaluations`, `human_feedback`, `quality_gate_results` |
| **Metrics** | `artifact_metrics`, `daily_metrics`, `user_activity` |
| **Interaction** | `user_questions`, `api_keys` |
| **Checkpointing** | `checkpoints` |

---

## 11. Indexing Strategy Summary

### Always Indexed (Foreign Keys)
- All foreign key columns are indexed automatically via `CREATE INDEX` statements above

### Query-Driven Indexes

| Table | Query Pattern | Index |
|-------|--------------|-------|
| artifacts | By type + status | `idx_artifacts_type, status` |
| artifacts | Recent first | `idx_artifacts_created` |
| learnings | Unvalidated first | `idx_learnings_validated` |
| executions | By artifact + phase | `idx_executions_artifact_phase` |
| evaluations | Passed/failed | `idx_evaluations_passed` |
| logs | By component + level | `idx_logs_component, level` |

### Partial Indexes (Performance)

```sql
-- Active sessions only
CREATE INDEX idx_sessions_active ON sessions(user_id) 
    WHERE status = 'active';

-- Unvalidated learnings
CREATE INDEX idx_learnings_unvalidated ON learnings(artifact_type) 
    WHERE is_validated = FALSE;

-- Blocking questions
CREATE INDEX idx_questions_blocking ON user_questions(artifact_id) 
    WHERE answered_at IS NULL AND is_blocking = TRUE;
```

---

## 12. Data Retention Policy

| Data Type | Retention | Rationale |
|-----------|-----------|-----------|
| Execution logs | 30 days | High volume, debug only |
| Execution traces | 7 days | Detailed debugging |
| Checkpoints | 7 days | Resume capability |
| Failed artifacts | Forever | Analysis |
| Completed artifacts | Forever | Value |
| Learnings | 90 days default | Can be extended |
| Metrics | Forever | Analytics |

---

## 13. Migration Strategy

### Version 1.0 → 2.0 Example: Adding User Questions

```sql
-- UP Migration
BEGIN;

-- Add table
CREATE TABLE user_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    context TEXT,
    options JSONB,
    is_blocking BOOLEAN DEFAULT TRUE,
    answered_at TIMESTAMP WITH TIME ZONE,
    answer TEXT,
    selected_option VARCHAR(255),
    proceeded_without_answer BOOLEAN DEFAULT FALSE,
    assumption_made TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add index
CREATE INDEX idx_user_questions_artifact ON user_questions(artifact_id);
CREATE INDEX idx_user_questions_blocking ON user_questions(is_blocking) 
    WHERE answered_at IS NULL;

-- Add column to artifacts if needed
ALTER TABLE artifacts ADD COLUMN user_questions JSONB DEFAULT '[]';

COMMIT;

-- DOWN Migration
BEGIN;

DROP TABLE user_questions;
ALTER TABLE artifacts DROP COLUMN IF EXISTS user_questions;

COMMIT;
```

---

## 14. Future Considerations

### Partitioning
For high-volume deployments:
- `execution_logs`: Partition by `created_at` (daily)
- `executions`: Partition by `artifact_id` or `started_at`
- `artifact_metrics`: Partition by `created_at` (monthly)

### TimescaleDB Extension
Consider TimescaleDB for:
- Automatic retention policies
- Continuous aggregates for metrics
- Improved time-series queries

### Read Replicas
For read-heavy workloads:
- Replicate to read-only replicas
- Route queries to replicas
- Keep writes on primary

---

## 15. Database Initialization Script

```sql
-- Run as superuser or with CREATEDB privilege

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Run table creation scripts (see sections above)
-- Run index creation scripts
-- Run initial data (default schemas, admin user)

-- Example: Insert default RFP schema
INSERT INTO artifact_schemas (type, version, schema_definition, research_config, 
                               generation_config, review_config, quality_gates, description)
VALUES (
    'rfp', '1.0',
    '{
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "executive_summary": {"type": "string"},
            "requirements": {"type": "array"},
            "timeline": {"type": "object"},
            "budget": {"type": "string"},
            "evaluation_criteria": {"type": "array"}
        },
        "required": ["title", "executive_summary", "requirements"]
    }'::jsonb,
    '{"required": true, "depth": "deep", "domains": ["competitor-analysis", "requirements-gathering"]}'::jsonb,
    '{"structure": "standard", "sections": ["executive_summary", "requirements", "timeline", "budget", "evaluation_criteria"]}'::jsonb,
    '{"always": ["compliance", "technical"], "conditional": [{"if": "has-legal", "then": ["legal"]}]}'::jsonb,
    '[{"name": "completeness", "threshold": 0.9}, {"name": "clarity", "threshold": 0.8}]'::jsonb,
    'Request for Proposal - standard template'
);
```

---

**End of Schema Design**

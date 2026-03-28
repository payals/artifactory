# Knowledge Artifact Generator - Architecture Design

> **For Claude:** This is a design document. For implementation planning, use `development/writing-plans` skill after this design is validated.

**Goal:** Create a unified pipeline system that generates any knowledge artifact type from a user description, unifying patterns from commit-review, pg_rag_slide_generator, and pnc_rfp.

**Architecture:** Hybrid composable tool ecosystem with specialized tools that can be dynamically assembled per artifact type. Tools have granular specialization options with a smart coordinator that decides which tools to invoke based on artifact schema.

**Why Python?** Native LangGraph support (vs 2nd-class JS), leverages existing pg_rag_slide_generator code, dominant LLM ecosystem (OpenAI/Anthropic/HuggingFace ship Python SDKs first), natural data/AI integration.

**Tech Stack:** Python, Postgres (Docker), LangGraph for orchestration

---

## 1. Core Architecture

### 1.1 Tool-First Design Philosophy

```
┌─────────────────────────────────────────────────────────────────┐
│                    Artifact Generator                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   User Description ──▶ Router ──▶ Coordinator ──▶ Output        │
│                              │                                    │
│                              ▼                                    │
│                    ┌─────────────────┐                           │
│                    │   Tool Registry  │◀── Schema Definitions    │
│                    └────────┬────────┘                           │
│                             │                                      │
│         ┌──────────────────┼──────────────────┐                   │
│         │                  │                  │                   │
│    ┌────▼────┐       ┌─────▼─────┐      ┌─────▼─────┐          │
│    │Research │       │ Generate  │      │  Review   │          │
│    │  Layer  │       │   Layer   │      │   Layer   │          │
│    └────┬────┘       └──────┬────┘      └─────┬─────┘          │
│         │                   │                   │                  │
│    ┌────▼────┐       ┌─────▼─────┐      ┌─────▼─────┐        │
│    │Specialized      │ Specialized    │ Specialized     │        │
│    │+ Generic  │      │ + Generic     │ + Generic       │        │
│    │(router)   │      │ (generate)    │ (review)        │        │
│    └───────────┘      └───────────────┘ └─────────────────┘      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Key Insight: Selective Invocation

**Not all tools run on every artifact.** The Coordinator decides based on:
- Artifact schema (defines required tools)
- Tool capabilities (what each tool can do)
- Context (what has already been generated)

---

## 2. Tool Layers

### 2.1 Research Layer

**Responsibility:** Gather context, information, and inputs needed for artifact generation.

**Composition:**

| Tool | Type | When to Use |
|------|------|-------------|
| `WebSearcher` | Generic | Always - gather initial context |
| `DeepAnalyzer` | Generic | Analyze search results in depth |
| `RFPResearcher` | Specialized | RFP-specific: competitor analysis, requirements gathering |
| `BlogPostResearcher` | Specialized | Blog-specific: trending topics, SEO keywords |
| `ResearchRouter` | Meta | Decides which specialized research to run OR runs generic |

**Research Flow:**
```
User Description
       │
       ▼
┌──────────────────┐
│  ResearchRouter  │ ◀── Determines research strategy
└────────┬─────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
WebSearch  DomainSpecific
 +         (optional)
DeepAnalyzer
    │
    ▼
Research Output
(Context for generation)
```

**Key Capability:** `WebSearcher` AND `DeepAnalyzer` work together - search finds URLs, analyzer extracts and synthesizes information from them.

### 2.2 Generate Layer

**Responsibility:** Create the artifact based on research output and schema.

**Composition:**

| Tool | Type | When to Use |
|------|------|-------------|
| `GenericGenerator` | Generic | Default - prompt-driven generation |
| `RFPGenerator` | Specialized | RFP structure, sections, compliance |
| `SlideGenerator` | Specialized | Slide deck format, visual constraints |
| `BlogPostGenerator` | Specialized | Blog format, SEO optimization |
| `GenerateRouter` | Meta | Selects generator based on artifact type |

**Generation Contract:**
```python
from pydantic import BaseModel
from typing import Optional

class GenerateInput(BaseModel):
    artifact_type: str
    schema: ArtifactSchema
    context: ResearchOutput
    constraints: GenerationConstraints

class GenerateOutput(BaseModel):
    artifact: ArtifactDraft
    confidence: float
    requires_review: list[str]  # Which reviewers to invoke
```

### 2.3 Review Layer

**Responsibility:** Quality assurance, self-critique, validation.

**Critical Design:** **Not all reviewers run on every artifact.** The generator output specifies which reviewers to invoke.

**Composition:**

| Tool | Type | When to Use |
|------|------|-------------|
| `GenericReviewer` | Generic | Always - baseline quality check |
| `ComplianceReviewer` | Specialized | When legal/regulatory requirements exist |
| `TechnicalReviewer` | Specialized | When technical accuracy matters |
| `StyleReviewer` | Specialized | When tone/voice consistency matters |
| `FactCheckReviewer` | Specialized | When factual accuracy is critical |
| `ReviewRouter` | Meta | Determines which reviewers needed |

**Review Selection Logic:**
```
Generator Output
       │
       ▼
┌──────────────────┐
│   ReviewRouter   │ ◀── Reads requiresReview array
└────────┬─────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
Specific    Generic
Reviewers   Reviewer
(required)  (always)
    │
    ▼
Review Output
(Pass/Fail/Issues)
```

---

## 3. Coordinator (The Brain)

### 3.1 Responsibilities

1. **Tool Chain Assembly** - Build execution plan from artifact schema
2. **State Management** - Pass context between tools (like commit-review's state machine)
3. **Decision Point** - When to ask user questions (critical for "A with follow-up")
4. **Rerouting** - On verification failure, decide: retry, escalate, or ask user
5. **Checkpointing** - Save state for resume (like pnc_rfp's resume modes)

### 3.2 State Machine

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  IDLE   │────▶│RESEARCH │────▶│GENERATE │────▶│ REVIEW  │
└─────────┘     └─────────┘     └─────────┘     └────┬────┘
     ▲                                               │
     │                                               │
     │    ┌─────────┐     ┌─────────┐               │
     │    │  ASK    │◀────│ VERIFY  │◀────────────┘
     │    │  USER   │     │ (Pass?) │
     │    └─────────┘     └────┬────┘
     │                          │ No
     └──────────────────────────┘
              Yes (complete)
```

### 3.3 User Question Protocol

When Coordinator encounters ambiguity:
```python
from pydantic import BaseModel
from typing import Optional

class UserQuestion(BaseModel):
    id: str
    question: str
    options: Optional[list[str]] = None  # Multiple choice
    context: str  # What we know so far
    can_proceed_without: bool  # Is this blocking?
```

**Decision Tree:**
- Critical ambiguity → MUST ask user
- Non-critical → Can proceed with assumption, note for review
- User doesn't respond → Use conservative default, flag for later review

---

## 4. Schema System

### 4.1 Artifact Schema Definition

Each artifact type defines its requirements in a declarative schema:

```python
from pydantic import BaseModel
from typing import Optional, Literal

class ArtifactSchema(BaseModel):
    type: str  # "rfp", "blog-post", "slide-deck"
    version: str

    # Tool requirements
    research: "ResearchConfig"
    generation: "GenerationConfig"
    review: "ReviewConfig"
    output: "OutputConfig"

class ResearchConfig(BaseModel):
    required: bool
    depth: Literal["shallow", "medium", "deep"]
    domains: Optional[list[str]] = None  # Specialized researchers to use

class ReviewConfig(BaseModel):
    required: "ReviewRequirements"
    gates: list[ValidationGate]  # From pg_rag_slide_generator

class ReviewRequirements(BaseModel):
    always: list[str]  # Always run these reviewers
    conditional: list[ConditionalReview]  # Run based on content type

class ConditionalReview(BaseModel):
    if_condition: str
    then_reviewers: list[str]
```

### 4.2 Example Schemas

**RFP Schema:**
```python
rfp_schema = ArtifactSchema(
    type="rfp",
    version="1.0",
    research=ResearchConfig(
        required=True,
        depth="deep",
        domains=["competitor-analysis", "requirements-gathering"]
    ),
    review=ReviewConfig(
        required=ReviewRequirements(
            always=["compliance", "technical"],
            conditional=[
                ConditionalReview(
                    if_condition="has-legal-requirements",
                    then_reviewers=["legal"]
                )
            ]
        ),
        gates=[
            ValidationGate(name="completeness", threshold=0.9),
            ValidationGate(name="clarity", threshold=0.8)
        ]
    )
)
```

**Blog Post Schema:**
```python
blog_schema = ArtifactSchema(
    type="blog-post",
    version="1.0",
    research=ResearchConfig(
        required=True,
        depth="medium",
        domains=["seo", "trending-topics"]
    ),
    review=ReviewConfig(
        required=ReviewRequirements(
            always=["style", "fact-check"],
            conditional=[]
        ),
        gates=[
            ValidationGate(name="seo-score", threshold=0.7),
            ValidationGate(name="readability", threshold=0.8)
        ]
    )
)
```

---

## 5. Verification & Rerouting

### 5.1 Validation Gates (from pg_rag_slide_generator)

Each artifact type defines its own gates:

```python
from pydantic import BaseModel
from typing import Literal

class ValidationGate(BaseModel):
    name: str
    validator: str  # Which validator tool
    threshold: float  # Pass threshold (0-1)
    on_fail: Literal["retry", "ask-user", "escalate"]
```

### 5.2 Rerouting Strategy

```
Verification Failed
       │
       ▼
┌──────────────────┐
│  Analyze Failure  │
│  - Which gate?    │
│  - How severe?    │
│  - Retryable?     │
└────────┬─────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
Retryable    Non-Retryable
    │             │
    ▼             ▼
Re-run       ┌─────┴─────┐
Tool(s)      │            │
             ▼            ▼
        Ask User     Escalate
        (if safe)    (log, alert)
```

---

## 6. Six-Layer Context System

Inspired by Dash's approach, every generation request retrieves context across 6 layers:

| Layer | Purpose | Source |
|-------|---------|--------|
| **Schema** | What fields/structure does this artifact need? | Artifact schema definition |
| **Guidelines** | Domain-specific rules and conventions | Human annotations |
| **Patterns** | Proven approaches that worked before | Query patterns |
| **Sources** | Current research findings | Web search |
| **Learnings** | What worked/failed in prior generations | Auto-learned |
| **Runtime** | User preferences, recent feedback | Live context |

### 6.1 Context Retrieval Flow

```
User Request
     │
     ▼
┌─────────────────┐
│  ContextBuilder │ ◀── Hybrid search across all layers
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
Weighted    Semantic
Search      Search
    │         │
    └────┬────┘
         │
         ▼
┌─────────────────┐
│   Merged Context │ ◀── Ranked + deduplicated
└────────┬────────┘
         │
         ▼
  Generation Prompt
```

---

## 7. Self-Evolution System (Learnings)

The system improves itself with each run without retraining:

### 7.1 Two Memory Systems

| System | Type | Content | Management |
|--------|------|---------|-------------|
| **Knowledge** | Curated | Proven generation patterns, domain guidelines, templates | Human-maintained |
| **Learnings** | Auto-discovered | Error patterns, successful fixes, what failed → what worked | System-maintained |

### 7.2 Learning Capture

```python
class LearningCapture(BaseModel):
    artifact_type: str
    context: str  # What was the situation?
    failure_mode: str  # What went wrong
    fix_applied: str  # What fixed it
    outcome: Literal["success", "still_failed"]
    confidence: float
    # Learned: "position is TEXT not INTEGER" → always cast in queries
```

### 7.3 Learning Application

On each generation:
1. Retrieve relevant learnings for this artifact type
2. Inject into context as guidance
3. After generation, capture new learnings if anything failed
4. Periodically review and elevate to Knowledge if validated

---

## 8. Input Validation & Invariants

### 8.1 String Validation

All user inputs validated before processing:

```python
class InputValidator:
    @staticmethod
    def validate_description(description: str) -> ValidationResult:
        # Min length check
        if len(description) < 10:
            return ValidationResult(False, "Description too short")
        
        # Max length check  
        if len(description) > 10000:
            return ValidationResult(False, "Description too long")
        
        # Block harmful patterns
        if contains_injection_patterns(description):
            return ValidationResult(False, "Invalid input detected")
        
        return ValidationResult(True, None)
    
    @staticmethod
    def validate_schema_type(schema_type: str) -> bool:
        allowed = ["rfp", "blog-post", "slide-deck", ...]
        return schema_type in allowed
```

### 8.2 Structural Invariants

Defined per artifact type - must hold at all times:

```python
class RFPInvariant:
    @staticmethod
    def check(artifact: "RFPArtifact") -> list[InvariantViolation]:
        violations = []
        
        # Must have executive summary
        if not artifact.sections.get("executive_summary"):
            violations.append(InvariantViolation(
                name="has_executive_summary",
                severity="error",
                message="RFP must have executive summary"
            ))
        
        # Must have at least one requirement section
        if not artifact.sections.get("requirements"):
            violations.append(InvariantViolation(
                name="has_requirements",
                severity="error", 
                message="RFP must have requirements section"
            ))
        
        # Budget must be numeric if present
        if artifact.sections.get("budget"):
            if not is_numeric(artifact.sections["budget"]):
                violations.append(InvariantViolation(
                    name="budget_is_numeric",
                    severity="warning",
                    message="Budget should be numeric"
                ))
        
        return violations
```

---

## 9. Evaluation Framework

### 9.1 LLM-as-Judge Evaluation

Automatic quality assessment after generation:

```python
class EvaluationResult(BaseModel):
    artifact_id: UUID
    evaluation_type: str  # "auto", "human"
    
    # Quality scores (0-1)
    completeness_score: float
    clarity_score: float
    accuracy_score: float
    quality_score: float
    
    # Detailed feedback
    issues: list[EvaluationIssue]
    suggestions: list[str]
    
    # Pass/fail decision
    passed: bool
    confidence: float

class Evaluator:
    async def evaluate(self, artifact: Artifact) -> EvaluationResult:
        # Build evaluation prompt with criteria
        prompt = self._build_evaluation_prompt(artifact)
        
        # Get LLM judgment
        response = await self.llm.ainvoke(prompt)
        
        # Parse into structured result
        return self._parse_response(response)
```

### 9.2 Evaluation Criteria by Artifact Type

| Artifact | Completeness | Clarity | Accuracy | Quality |
|---------|--------------|---------|----------|---------|
| RFP | All sections present | Clear requirements | Factual correctness | Professional tone |
| Blog Post | Full narrative | Engaging prose | Citations accurate | SEO optimized |
| Slide Deck | All slides complete | Concise bullets | Data accurate | Visually clear |

### 9.3 Human Feedback Loop

```python
class HumanFeedback(BaseModel):
    artifact_id: UUID
    user_id: str
    
    # Ratings (1-5)
    usefulness: int
    accuracy: int
    quality: int
    
    # Qualitative
    feedback: Optional[str]
    would_regenerate: bool
    
    # Stored and used to improve future generations
    # If avg rating < 3 → trigger learning capture
```

---

## 10. Observability (Postgres-native)

All observability data stored in Postgres for now. Langfuse/Prometheus/Grafana can be added later.

### 10.1 Execution Tracing

```python
# Every tool execution logged
class ExecutionTrace(BaseModel):
    id: UUID
    artifact_id: UUID
    step: str  # "research", "generate", "review"
    tool_name: str
    
    # Timing
    started_at: datetime
    completed_at: Optional[datetime]
    duration_ms: Optional[int]
    
    # Context
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    
    # Outcome
    status: Literal["success", "error", "timeout"]
    error: Optional[str]
    
    # For debugging
    metadata: dict
```

### 10.2 Metrics Tables

```sql
-- Artifact-level metrics
CREATE TABLE artifact_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID REFERENCES artifacts(id),
    
    -- Timing
    total_duration_ms INTEGER,
    research_duration_ms INTEGER,
    generate_duration_ms INTEGER,
    review_duration_ms INTEGER,
    
    -- Tokens
    total_input_tokens INTEGER,
    total_output_tokens INTEGER,
    
    -- Costs (configurable price per 1M tokens)
    estimated_cost_cents DECIMAL(10, 4),
    
    -- Quality
    evaluation_score DECIMAL(5, 4),
    human_rating INTEGER,
    
    -- Counts
    num_retries INTEGER,
    num_user_questions INTEGER,
    num_tools_used INTEGER,
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Daily aggregation for dashboards later
CREATE TABLE daily_metrics (
    date DATE PRIMARY KEY,
    artifacts_created INTEGER,
    artifacts_completed INTEGER,
    avg_duration_ms INTEGER,
    avg_evaluation_score DECIMAL(5, 4),
    total_tokens INTEGER,
    total_cost_cents DECIMAL(10, 4),
    success_rate DECIMAL(5, 4)
);
```

### 10.3 Queryable Logs

```sql
-- Structured logs for debugging
CREATE TABLE execution_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID REFERENCES artifacts(id),
    level VARCHAR(10),  -- DEBUG, INFO, WARN, ERROR
    component VARCHAR(50),  -- coordinator, tool, verifier
    message TEXT,
    context JSONB,  -- Structured context for debugging
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_logs_artifact ON execution_logs(artifact_id);
CREATE INDEX idx_logs_level ON execution_logs(level);
CREATE INDEX idx_logs_created ON execution_logs(created_at DESC);
```

---

## 11. Lightweight Spec + Quality Gates

Per Peter S.'s "Just Talk To It" philosophy - lightweight specs, but quality enforced via gates:

### 11.1 Minimal Spec Input

```
User can provide:
- Short description (1-2 sentences)
- OR reference URLs to learn from
- OR existing artifact to iterate on

NOT required:
- Full specification document
- Detailed requirements
```

### 11.2 Quality Gates (Non-Negotiable)

Before artifact is considered complete, ALL gates must pass:

```python
class QualityGate(BaseModel):
    name: str
    description: str
    check_function: str  # Python function to run
    
    # Gate configuration
    blocking: bool  # If True, must pass to proceed
    retry_on_fail: bool  # If True, regenerate and retry
    
    # Thresholds
    min_score: float = 0.0  # 0-1 for LLM gates
    exact_match: bool = False  # For deterministic checks

GATES_FOR_RFP = [
    QualityGate(
        name="has_executive_summary",
        description="RFP must have executive summary",
        check_function="check_has_section",
        blocking=True,
        exact_match=True
    ),
    QualityGate(
        name="completeness_score",
        description="LLM evaluation of completeness",
        check_function="evaluate_completeness",
        blocking=True,
        min_score=0.8
    ),
    QualityGate(
        name="no_hallucinations",
        description="Verify factual claims against sources",
        check_function="verify_facts",
        blocking=True,
        retry_on_fail=True
    ),
    QualityGate(
        name="readability",
        description="Minimum readability score",
        check_function="check_readability",
        blocking=False,
        min_score=0.6
    ),
]
```

### 11.3 Iterative Refinement

If gates fail:
1. First retry: Apply learnings from similar failures
2. Second retry: Ask user for clarification
3. Escalate: Log for human review, provide best effort output

---

## 12. Parallel Tool Execution

Independent tools run in parallel where safely possible:

### 12.1 Parallel Opportunities

| Phase | Can Parallelize | Dependencies |
|-------|-----------------|--------------|
| Research | Web search + Source validation | None - independent |
| Review | Multiple reviewers (style + fact-check + compliance) | None - different aspects |
| Verification | Independent gate checks | None - each gate is separate |

### 12.2 Execution Patterns

```python
# Parallel research + setup
async def research_phase(state: GraphState):
    # These can run in parallel:
    web_search_task = asyncio.create_task(run_web_search(state))
    source_validation_task = asyncio.create_task(validate_sources(state))
    
    # Wait for both
    web_results, source_results = await asyncio.gather(
        web_search_task, source_validation_task
    )
    
    # Then run deep analysis on combined results
    return await run_deep_analysis(web_results, source_results)

# Parallel review execution
async def review_phase(state: GraphState):
    required_reviewers = state["requires_review"]
    
    # Run independent reviewers in parallel
    review_tasks = [
        asyncio.create_task(run_reviewer(name, state))
        for name in required_reviewers
    ]
    
    results = await asyncio.gather(*review_tasks, return_exceptions=True)
    
    # Aggregate results
    return aggregate_review_results(results)
```

### 12.3 Safety Rules

- **Never parallelize**: Tools that modify state
- **Always await**: Tools that other tools depend on
- **Idempotency**: Parallel tools must be safe to run multiple times
- **Timeout per tool**: Individual timeouts prevent one stuck tool blocking all

---

## 13. Key Decisions Summary (Updated)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Tool Specialization | Hybrid (A + composable) | Specialized when needed, generic as fallback + router |
| Research Flow | WebSearcher → DeepAnalyzer | Search finds, analyzer synthesizes |
| Review Invocation | Selective (not all always) | Performance + relevance |
| State Management | Postgres (Docker) | Per user request - leverages pg_rag_slide_generator pattern |
| User Questions | Coordinator-managed | Critical for "A with follow-up" requirement |
| Evolution | pnc_rfp-style watch + resume + Learnings | Proven pattern + self-improvement |
| Orchestration | LangGraph | Built-in state management, checkpointing, tool calling, Postgres checkpointer |
| First Artifact | RFP | Per user request - most complex, tests all layers |
| Context System | 6-Layer | Dash-inspired for grounded generation |
| Input Validation | String + Invariants | Quality gates without rate limiting |
| Evaluation | LLM-as-Judge + Human | Automatic + human feedback loop |
| Observability | Postgres-native | Langfuse/Prometheus later |
| Spec Approach | Lightweight + Gates | Fast iteration, quality enforced |
| Parallel Execution | Where safe | Performance + safety |

---

## 14. Data Flow

```
1. User Input
   "Create an RFP for cloud migration to AWS"

2. Router
   └─▶ Matches to "rfp" schema
   └─▶ Identifies required tools

3. Coordinator executes:
   │
   ├─▶ Research Layer
   │    ├─▶ WebSearcher (generic web search)
   │    ├─▶ DeepAnalyzer (analyze results)
   │    └─▶ RFPResearcher (specialized if needed)
   │         └─▶ Research Output (context + sources)
   │
   ├─▶ Generate Layer
   │    ├─▶ GenericGenerator (base generation)
   │    └─▶ RFPGenerator (structured output)
   │         └─▶ Artifact Draft + requiresReview
   │
   └─▶ Review Layer
        ├─▶ GenericReviewer (always)
        ├─▶ ComplianceReviewer (from schema)
        ├─▶ TechnicalReviewer (from schema)
        └─▶ Review Output (pass/fail/issues)

4. Verification
   └─▶ Run validation gates
   └─▶ Pass? → Output artifact
   └─▶ Fail? → Reroute to appropriate tool

5. Done
   └─▶ Artifact + metadata + evolution config
```

---

## 15. File Structure

```
/knowledge-artifact-generator
├── src/
│   ├── coordinator/           # State machine + orchestration
│   │   ├── state_machine.py
│   │   ├── tool_selector.py
│   │   └── checkpoint.py
│   ├── router/               # Schema matching + routing
│   │   ├── schema_registry.py
│   │   └── artifact_router.py
│   ├── context/              # 6-layer context system
│   │   ├── context_builder.py
│   │   ├── knowledge_retriever.py
│   │   └── learnings_retriever.py
│   ├── learnings/            # Self-evolution system
│   │   ├── capture.py       # Capture learnings from failures
│   │   ├── validate.py      # Validate and promote learnings
│   │   └── apply.py         # Apply learnings to generation
│   ├── validation/           # Input validation + invariants
│   │   ├── input_validator.py
│   │   └── invariants.py
│   ├── evaluation/           # LLM-as-Judge framework
│   │   ├── evaluator.py
│   │   ├── criteria.py
│   │   └── human_feedback.py
│   ├── observability/        # Tracing + metrics
│   │   ├── tracer.py
│   │   └── metrics.py
│   ├── tools/
│   │   ├── research/        # Research layer
│   │   │   ├── web_searcher.py
│   │   │   ├── deep_analyzer.py
│   │   │   ├── research_router.py
│   │   │   └── specialized/
│   │   │       ├── rfp_researcher.py
│   │   │       └── blog_researcher.py
│   │   ├── generate/         # Generation layer
│   │   │   ├── generic_generator.py
│   │   │   ├── generate_router.py
│   │   │   └── specialized/
│   │   │       ├── rfp_generator.py
│   │   │       └── slide_generator.py
│   │   └── review/           # Review layer
│   │       ├── generic_reviewer.py
│   │       ├── review_router.py
│   │       └── specialized/
│   │           ├── compliance_reviewer.py
│   │           ├── style_reviewer.py
│   │           └── fact_check_reviewer.py
│   ├── schemas/              # Artifact schemas
│   │   ├── rfp_schema.py
│   │   ├── blog_post_schema.py
│   │   └── slide_deck_schema.py
│   ├── verification/        # Validation gates
│   │   ├── gate_runner.py
│   │   └── quality_gates.py
│   └── cli/                  # Entry point
│       └── __main__.py
├── schemas/                  # Schema definitions (JSON)
├── tests/
├── docs/
├── pyproject.toml
└── README.md
```

---

## 16. LangGraph Architecture

LangGraph is the orchestration backbone. Here's how it maps to our design:

### 15.1 Graph Structure

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from typing import TypedDict, Annotated
import operator

# State definition
class GraphState(TypedDict):
    artifact_type: str
    user_description: str
    schema: ArtifactSchema
    research_output: ResearchOutput | None
    artifact_draft: ArtifactDraft | None
    review_results: list[ReviewResult] | None
    verification_status: Literal["pending", "passed", "failed"]
    user_questions: list[UserQuestion]
    errors: list[str]

# Nodes (as Python functions)
def router(state: GraphState) -> GraphState:
    """Match schema, set tool requirements"""
    ...

def research(state: GraphState) -> GraphState:
    """Invoke research layer"""
    ...

def generate(state: GraphState) -> GraphState:
    """Invoke generation layer"""
    ...

def review(state: GraphState) -> GraphState:
    """Invoke review layer"""
    ...

def verify(state: GraphState) -> GraphState:
    """Run validation gates"""
    ...

def ask_user(state: GraphState) -> GraphState:
    """Handle user questions"""
    ...

# Build the graph
graph = StateGraph(GraphState)
graph.add_node("router", router)
graph.add_node("research", research)
graph.add_node("generate", generate)
graph.add_node("review", review)
graph.add_node("verify", verify)
graph.add_node("ask_user", ask_user)

# Edges
graph.set_entry_point("router")
graph.add_edge("router", "research")
graph.add_edge("research", "generate")
graph.add_edge("generate", "review")
graph.add_edge("review", "verify")

# Conditional routing
def should_continue(state: GraphState) -> str:
    if state["verification_status"] == "passed":
        return "done"
    if state["verification_status"] == "failed":
        return "ask_user"
    return "research"  # retry

graph.add_conditional_edges("verify", should_continue, {
    "done": END,
    "ask_user": "ask_user",
    "research": "research"
})
```

### 15.2 Checkpointing (Postgres)

```python
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_postgres import ChatMessageHistory
import asyncpg

# PostgreSQL checkpointer (built-in to LangGraph)
checkpointer = PostgresSaver.from_conn_string(
    "postgresql://user:pass@localhost:5432/artifact_generator"
)
checkpointer.setup()  # Creates tables if needed

# Compile with checkpointer
app = graph.compile(checkpointer=checkpointer)
```

### 15.3 Tool Invocation (as LangGraph Tools)

```python
from langchain_core.tools import tool
from pydantic import BaseModel, Field

class WebSearchInput(BaseModel):
    query: str = Field(description="The search query")
    num_results: int = Field(default=10, description="Number of results")

@tool(args_schema=WebSearchInput)
def web_searcher(query: str, num_results: int = 10) -> dict:
    """Search the web for information. Returns URLs and summaries."""
    results = search_web(query, num_results)
    return {
        "query": query,
        "results": results,
        "sources": [r["url"] for r in results]
    }

# Bind tools to LLM
llm_with_tools = llm.bind_tools([web_searcher, deep_analyzer, ...])
```

---

## 16. Next Steps

1. **Validate Design** - Confirm this matches vision ✓ (user approved)
2. **Set Up Worktree** - Create isolated workspace for implementation
3. **Implement MVP** - Start with core LangGraph + RFP schema + minimal tools

---

## 17. Postgres Schema (Complete)

```sql
-- Core tables for artifact generation

CREATE TABLE artifacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  type VARCHAR(50) NOT NULL,  -- 'rfp', 'blog-post', etc.
  user_description TEXT NOT NULL,
  status VARCHAR(20) DEFAULT 'pending',
  
  -- Research
  research_context JSONB,
  research_sources JSONB,
  
  -- Generation
  artifact_draft TEXT,
  generation_metadata JSONB,
  
  -- Review
  review_results JSONB,
  
  -- Verification
  verification_status VARCHAR(20),
  verification_errors JSONB,
  
  -- Evolution
  version INTEGER DEFAULT 1,
  parent_id UUID REFERENCES artifacts(id),
  resume_mode VARCHAR(20),  -- 'preserve', 'enhance', 'replace'
  
  -- Metadata
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  completed_at TIMESTAMP,
  metadata JSONB
);

-- Learnings: Auto-captured insights from failures
CREATE TABLE learnings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  artifact_type VARCHAR(50) NOT NULL,
  context TEXT NOT NULL,  -- What was the situation?
  failure_mode TEXT NOT NULL,  -- What went wrong
  fix_applied TEXT,  -- What fixed it
  outcome VARCHAR(20),  -- 'success', 'still_failed'
  confidence FLOAT,
  times_applied INTEGER DEFAULT 0,
  times_succeeded INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW(),
  validated_at TIMESTAMP
);

-- Knowledge: Curated human-maintained patterns
CREATE TABLE knowledge (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  artifact_type VARCHAR(50) NOT NULL,
  category VARCHAR(50),  -- 'pattern', 'guideline', 'template'
  content TEXT NOT NULL,
  source VARCHAR(50),  -- 'human', 'learned'
  created_by VARCHAR(100),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Evaluation results (LLM-as-judge)
CREATE TABLE evaluations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  artifact_id UUID REFERENCES artifacts(id),
  evaluation_type VARCHAR(20),  -- 'auto', 'human'
  
  -- Quality scores (0-1)
  completeness_score FLOAT,
  clarity_score FLOAT,
  accuracy_score FLOAT,
  quality_score FLOAT,
  
  -- Detailed feedback
  issues JSONB,
  suggestions JSONB,
  
  -- Pass/fail
  passed BOOLEAN,
  confidence FLOAT,
  
  created_at TIMESTAMP DEFAULT NOW()
);

-- Human feedback
CREATE TABLE human_feedback (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  artifact_id UUID REFERENCES artifacts(id),
  user_id VARCHAR(100),
  
  -- Ratings (1-5)
  usefulness INTEGER,
  accuracy INTEGER,
  quality INTEGER,
  
  -- Qualitative
  feedback TEXT,
  would_regenerate BOOLEAN,
  
  created_at TIMESTAMP DEFAULT NOW()
);

-- Execution traces
CREATE TABLE execution_traces (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  artifact_id UUID REFERENCES artifacts(id),
  step VARCHAR(50),
  tool_name VARCHAR(100),
  
  -- Timing
  started_at TIMESTAMP DEFAULT NOW(),
  completed_at TIMESTAMP,
  duration_ms INTEGER,
  
  -- Tokens
  input_tokens INTEGER,
  output_tokens INTEGER,
  
  -- Outcome
  status VARCHAR(20),
  error TEXT,
  
  metadata JSONB
);

-- Artifact metrics (for dashboards)
CREATE TABLE artifact_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  artifact_id UUID REFERENCES artifacts(id),
  
  -- Timing
  total_duration_ms INTEGER,
  research_duration_ms INTEGER,
  generate_duration_ms INTEGER,
  review_duration_ms INTEGER,
  
  -- Tokens
  total_input_tokens INTEGER,
  total_output_tokens INTEGER,
  
  -- Costs
  estimated_cost_cents DECIMAL(10, 4),
  
  -- Quality
  evaluation_score DECIMAL(5, 4),
  human_rating INTEGER,
  
  -- Counts
  num_retries INTEGER,
  num_user_questions INTEGER,
  num_tools_used INTEGER,
  
  created_at TIMESTAMP DEFAULT NOW()
);

-- Daily aggregation
CREATE TABLE daily_metrics (
  date DATE PRIMARY KEY,
  artifacts_created INTEGER,
  artifacts_completed INTEGER,
  avg_duration_ms INTEGER,
  avg_evaluation_score DECIMAL(5, 4),
  total_tokens INTEGER,
  total_cost_cents DECIMAL(10, 4),
  success_rate DECIMAL(5, 4)
);

-- Structured logs
CREATE TABLE execution_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  artifact_id UUID REFERENCES artifacts(id),
  level VARCHAR(10),
  component VARCHAR(50),
  message TEXT,
  context JSONB,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_learnings_type ON learnings(artifact_type);
CREATE INDEX idx_learnings_outcome ON learnings(outcome);
CREATE INDEX idx_evaluations_artifact ON evaluations(artifact_id);
CREATE INDEX idx_traces_artifact ON execution_traces(artifact_id);
CREATE INDEX idx_logs_artifact ON execution_logs(artifact_id);
CREATE INDEX idx_logs_created ON execution_logs(created_at DESC);

-- Checkpoints (LangGraph)
CREATE TABLE checkpoints (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  artifact_id UUID REFERENCES artifacts(id),
  step VARCHAR(50) NOT NULL,
  state JSONB NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Tool executions
CREATE TABLE tool_executions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  artifact_id UUID REFERENCES artifacts(id),
  tool_name VARCHAR(100) NOT NULL,
  input JSONB,
  output JSONB,
  status VARCHAR(20) DEFAULT 'running',
  error TEXT,
  started_at TIMESTAMP DEFAULT NOW(),
  completed_at TIMESTAMP
);

-- Schemas
CREATE TABLE schemas (
  type VARCHAR(50) PRIMARY KEY,
  version VARCHAR(20) NOT NULL,
  definition JSONB NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## 18. Next Steps

1. **Validate Design** - Confirm this matches vision (user approved all enhancements)
2. **Set Up Worktree** - Create isolated workspace for implementation
3. **Implement MVP** - Start with core LangGraph + RFP schema + minimal tools
4. **Iterate** - Add blog-post and slide-deck schemas after RFP is proven

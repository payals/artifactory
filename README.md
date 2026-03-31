# artifactforge
> Universal AI-powered pipeline for generating any knowledge artifact - self-evolving, observable, customizable
Generate reports, RFPs, commit reviews, runlists, whitepapers, blog posts, slide decks — or any knowledge artifact — from a simple description. artifactforge uses AI that learns from its mistakes and improves over time.
## Features
### Universal Artifact Generation
- **Schema-driven** — Define any artifact type via schema in the database
- **Specialized + Generic tools** — Coordinator intelligently selects which tools to run
- **Extensible** — Add new artifact types without code changes
### Self-Evolving
- **Learnings System** — Automatically captures failure patterns and successful fixes
- **Knowledge Base** — Curated patterns that improve future generations
- **Confidence Tracking** — Learns what works, ignores what doesn't
### Observable
- **Full Execution Tracing** — Every step logged with timing, tokens, and context
- **PostgreSQL-Native** — All data in your database, no external dependencies
- **Quality Metrics** — Track evaluation scores, costs, and performance
### Quality Guaranteed
- **Quality Gates** — Configurable pass/fail thresholds per artifact type
- **LLM-as-Judge** — Automatic quality evaluation
- **Human Feedback Loop** — Users can rate and improve future outputs
### Production-Ready
- **LangGraph Orchestration** — State machine with checkpointing
- **Parallel Tool Execution** — Independent tools run simultaneously
- **Docker Support** — One-command PostgreSQL setup
## Quick Start
```bash
# Start PostgreSQL
docker-compose up -d postgres
# Install
pip install artifactforge
# Generate an artifact
artifactforge generate "Create an RFP for cloud migration to AWS" --type rfp
```

## Model Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Required: OpenAI-compatible API (OpenRouter, Ollama, etc.)
OPENAI_API_KEY=sk-or-v1-...
OPENAI_API_BASE=https://openrouter.ai/api/v1

# OR use Ollama for local inference
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=kimi-k2.5:cloud

# Research APIs (optional)
TAVILY_API_KEY=...
EXA_API_KEY=...
FIRECRAWL_API_KEY=...
CONTEXT7_API_KEY=...
PERPLEXITY_API_KEY=...

# Database (optional)
DATABASE_URL=postgresql://user:pass@localhost:5432/artifactforge
```

### Model Configuration
The gateway uses a single model for all agents, configured via environment variables:

```bash
# Set provider and model in .env
LLM_PROVIDER=openrouter          # or: anthropic, ollama
LLM_MODEL=z-ai/glm-4.5-air:free # any model your provider supports
```

Per-agent temperature tuning is defined in `AGENT_TEMPERATURES` in `artifactforge/agents/llm_gateway.py`.

## MCRS Pipeline Architecture

The MCRS (Multi-agent Content Reasoning System) is a 13-node pipeline with epistemic tracking:

```
User Prompt
     │
     ▼
┌─────────────────┐
│ Intent Architect │ ──▶ Execution Brief
└────────┬────────┘
         ▼
┌─────────────────┐
│   Research Lead  │ ──▶ Research Map
└────────┬────────┘
         ▼
┌─────────────────┐
│  Evidence Ledger │ ──▶ Claim Ledger (epistemic classification)
└────────┬────────┘
         ▼
┌─────────────────┐
│     Analyst      │ ──▶ Analytical Backbone
└────────┬────────┘
         ▼
┌──────────────────┐
│ Output Strategist │ ──▶ Content Blueprint
└────────┬─────────┘
         ▼
┌─────────────────┐
│   Draft Writer   │ ──▶ Draft v1
└────────┬────────┘
         ▼
┌─────────────────────┐
│ Adversarial Reviewer │ ──┬──▶ Verify → Final Arbiter ──▶ Polish
└─────────────────────┘    │              ▲
                           └───revise──────┘
                           │
                           ▼
                   ┌─────────────────┐
                   │ Visual Designer  │ ──▶ Visual Spec
                   └────────┬────────┘
                            ▼
                   ┌─────────────────┐
                   │ Visual Reviewer  │ ──▶ Visual Review
                   └────────┬────────┘
                            ▼
                   ┌──────────────────┐
                   │ Visual Generator │ ──▶ Final Artifact
                   └──────────────────┘
```

**Key Features:**
- **Epistemic Tracking**: Evidence Ledger classifies claims (VERIFIED/UNVERIFIED/SPECULATIVE)
- **Revision Loops**: Max 3 revisions between Draft Writer ↔ Reviewer
- **Final Arbiter**: Routes to polish, revise_draft, revise_research, or end
- **Visual Generation**: Optional branch for visual artifacts (slides, infographics)
- **Checkpointing**: LangGraph MemorySaver for state persistence

## Observability

Every pipeline run is fully instrumented with structured logging:

### What's Captured

| Metric | Description |
|--------|-------------|
| **Node Timing** | Duration for each of the 13 pipeline nodes |
| **LLM Calls** | Number of LLM requests per node |
| **LLM Cost** | Cumulative cost per node (USD) |
| **Errors** | Full error details with stack traces |
| **Trace ID** | Unique UUID per pipeline execution |

### Log Output

```
2026-03-29 15:10:38 [info] Starting MCRS pipeline...
2026-03-29 15:10:39 [info] node_entry node=intent_architect trace_id=abc-123
2026-03-29 15:10:40 [info] node_exit node=intent_architect duration_ms=1500 llm_calls=2 llm_cost_usd=0.0001
2026-03-29 15:10:41 [info] node_entry node=research_lead trace_id=abc-123
...
```

### PostgreSQL Metrics

When connected to PostgreSQL, metrics are persisted:

```sql
-- Pipeline executions
SELECT * FROM pipeline_runs;

-- Per-stage metrics
SELECT * FROM stage_metrics WHERE trace_id = 'abc-123';
```

### Environment Variables

```bash
# For PostgreSQL metrics storage (optional)
# Copy .env.example to .env and update with your credentials
```

## Artifact Types
artifactforge ships with schemas for:
- RFPs — Request for Proposals with requirements, timeline, budget
- Blog Posts — SEO-optimized articles with research
- Commit Reviews — Code review summaries
- Reports — Structured analytical documents
Add your own — just insert a schema into the database.

Evaluation & Quality Assurance
artifactforge includes built-in evaluation mechanisms to ensure artifact quality:
LLM-as-Judge
- Automated quality assessment using the same LLM that generated the artifact
- Scores across multiple dimensions: accuracy, coherence, completeness, tone
- Configurable evaluation criteria per artifact type
Quality Gates
- Structural validation: output matches defined schema
- Invariant checking: business rules enforced
- Threshold-based acceptance: minimum scores required before artifact is marked "ready"
Human Feedback Loop
- Users can rate artifact quality (1-5 stars)
- Collect specific feedback on sections, tone, accuracy
- Feedback stored and used to improve future generations
Metrics Dashboard
- Track artifact success rate by type
- Measure revision cycles (generations per final artifact)
- User satisfaction trends over time

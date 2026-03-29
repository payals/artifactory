# ArtifactForge
> Universal AI-powered pipeline for generating any knowledge artifact - self-evolving, observable, customizable
Generate reports, RFPs, commit reviews, runlists, whitepapers, blog posts, slide decks — or any knowledge artifact — from a simple description. ArtifactForge uses AI that learns from its mistakes and improves over time.
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
artifactforge generate rfp "Create an RFP for cloud migration to AWS"
```

## Model Configuration

### Environment Variables
```bash
# Required: OpenAI-compatible API (OpenRouter, Ollama, etc.)
OPENAI_API_KEY=sk-...

# Optional: Override base URL (defaults to OpenRouter)
OPENAI_BASE_URL=https://openrouter.ai/api/v1
```

### Preflight Check
Every pipeline run automatically checks model availability before execution:
- Fetches live list of free models from OpenRouter
- Tests each configured model with a quick request
- Auto-replaces failed models with the best available alternative

Logs show which models are being used:
```
preflight - Running model preflight check...
preflight - Found 25 free models available
preflight -   default: z-ai/glm-4.5-air:free (available)
preflight -   coding: qwen/qwen2.5-coder-7b-instruct (paid, testing OK)
```

### Default Model Registry
The gateway uses these models by default:
| Slot | Model | Type |
|------|-------|------|
| default | z-ai/glm-4.5-air:free | Free |
| reasoning | z-ai/glm-4.5-air:free | Free |
| deep_reasoning | nvidia/nemotron-3-nano-30b-a3b:free | Free |
| coding | qwen/qwen2.5-coder-7b-instruct | Paid |
| review | meta-llama/llama-3.2-3b-instruct | Paid |
| verification | meta-llama/llama-3.2-3b-instruct | Paid |
| cheap_worker | z-ai/glm-4.5-air:free | Free |

Override via `MODEL_REGISTRY` in `artifactforge/agents/llm_gateway.py`.

## MCRS Pipeline Architecture

The MCRS (Multi-agent Content Reasoning System) is a 10-agent pipeline with epistemic tracking:

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
│ Adversarial Reviewer │ ──┬──▶ Verify → Final Arbiter ──▶ Polish ──▶ END
└─────────────────────┘    │              ▲
                           └───revise──────┘
```

**Key Features:**
- **Epistemic Tracking**: Evidence Ledger classifies claims (VERIFIED/UNVERIFIED/SPECULATIVE)
- **Revision Loops**: Max 3 revisions between Draft Writer ↔ Reviewer
- **Final Arbiter**: Routes to polish, revise_draft, revise_research, or end
- **Checkpointing**: LangGraph MemorySaver for state persistence
## Artifact Types
ArtifactForge ships with schemas for:
- RFPs — Request for Proposals with requirements, timeline, budget
- Blog Posts — SEO-optimized articles with research
- Commit Reviews — Code review summaries
- Reports — Structured analytical documents
Add your own — just insert a schema into the database.

Evaluation & Quality Assurance
ArtifactForge includes built-in evaluation mechanisms to ensure artifact quality:
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

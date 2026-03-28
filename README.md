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
Architecture
```
User Description
      │
      ▼
   ┌───────┐     ┌──────────┐     ┌─────────┐
   │Router │────▶│Coordinator│────▶│ Output  │
   └───────┘     └─────┬────┘     └─────────┘
                        │
           ┌───────────┼───────────┐
           ▼           ▼           ▼
       Research    Generate     Review
           │           │           │
           ▼           ▼           ▼
      WebSearch   RFP Gen    Compliance
      Analysis    Blog Gen   Technical
                               Style
```
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

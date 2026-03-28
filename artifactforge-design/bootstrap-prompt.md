# ArtifactForge - Bootstrap Prompt

> Use with: `/ulw-loop` in oh-my-opencode

## Workflow Instructions

Execute in PHASES below. After EACH phase:
1. Run the verification command
2. Show the output
3. Fix any issues before proceeding

DO NOT skip phases. Verify each phase works before continuing to the next.

## Context

You're building a universal knowledge artifact generator — ANY type: reports, commit reviews, runlists, whitepapers, RFPs, blog posts, slide decks, etc. The system should accept any artifact type via schema definition.

## Reference Documents
- `architecture-design.md` - Full architecture
- `database-schema.md` - 18-table schema
- `docker-compose.yml` - PostgreSQL
- `pyproject.toml` - Dependencies

## Phases

### Phase 1: Foundation
1. Set up Python package structure in `src/artifactforge/`
2. Create SQLAlchemy models (core tables: artifacts, users, sessions)
3. Set up Alembic migrations
4. Verify: `alembic upgrade head` runs successfully

### Phase 2: LangGraph Coordinator
1. Build state machine with stub nodes (router, research, generate, review, verify)
2. Add PostgreSQL checkpointer
3. Verify: `python -c "from artifactforge.coordinator import app; print('OK')"` works

### Phase 3: Tools (Research)
1. Implement WebSearcher tool (stub - returns mock data)
2. Implement DeepAnalyzer tool
3. Verify: Tools can be invoked

### Phase 4: Generation (Generic)
1. Implement schema-based generator (NOT hardcoded to any artifact type)
2. Add one example artifact type (e.g., simple report)
3. Verify: Can generate artifact from description

### Phase 5: Review + Verification
1. Implement generic reviewer
2. Add quality gates framework
3. Verify: Full pipeline runs end-to-end

## Key Design Principle

The system is GENERIC by default. Each artifact type is defined via schema in the database, not hardcoded. The coordinator decides which tools to invoke based on the artifact's schema requirements.

## Rules

- AFTER EACH PHASE: Run verification, show output, fix issues before continuing
- Use subagents for isolated tasks
- Save SUMMARY after each phase

## Verification Commands

```bash
# Phase 1
alembic upgrade head

# Phase 2
python -c "from artifactforge.coordinator import app; print('OK')"

# Phase 3
python -c "from artifactforge.tools.research import web_searcher; print('OK')"

# Phase 4
python -c "from artifactforge.tools.generate import generic_generator; print('OK')"

# Phase 5
python -c "from artifactforge.cli import main; print('OK')"
```

---

## Alternative: Design Review Prompt

Before bootstrapping, you may want design review:

```
You are a senior software architect. Review the ArtifactForge design documents and propose improvements.

## Documents to Review
1. `architecture-design.md` - System architecture
2. `database-schema.md` - PostgreSQL schema (18 tables)
3. `docker-compose.yml` - PostgreSQL setup
4. `pyproject.toml` - Dependencies

## Your Task
Read all documents thoroughly, then provide:

1. **Architectural Concerns** - Anything that seems problematic
2. **Schema Improvements** - Any table designs that could be better
3. **Missing Components** - What else is needed?
4. **Simplifications** - What could be simpler?
5. **Priority Changes** - What to do first vs. later?

Output as structured review with severity (critical/important/nice-to-have).
```

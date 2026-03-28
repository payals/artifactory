# ArtifactForge

> Unified knowledge artifact generation pipeline

**System:** ArtifactForge  
**Purpose:** Generate any knowledge artifact type (reports, commit reviews, RFPs, blog posts, runlists, whitepapers, etc.) from user descriptions  
**Tech Stack:** Python, PostgreSQL (Docker), LangGraph

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- OpenAI API key (or Anthropic)

### Setup

```bash
# 1. Clone/copy this directory to your new repository

# 2. Start PostgreSQL
docker-compose up -d postgres

# 3. Install dependencies
pip install -e .

# 4. Set environment variables
export DATABASE_URL="postgresql://artifactforge:artifactforge@localhost:5432/artifactforge"
export OPENAI_API_KEY="sk-..."

# 5. Run database migrations
alembic upgrade head

# 6. Start the API
python -m artifactforge.cli
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `OPENAI_API_KEY` | Yes | OpenAI API key for LLM calls |
| `ANTHROPIC_API_KEY` | No | Anthropic API key (alternative to OpenAI) |
| `LOG_LEVEL` | No | Logging level (default: INFO) |
| `ENVIRONMENT` | No | Environment (development/production) |

---

## Architecture

See [architecture-design.md](./architecture-design.md) for full system architecture.

---

## Database

See [database-schema.md](./database-schema.md) for complete schema design.

### Running Migrations

```bash
# Create migration
alembic revision --autogenerate -m "initial schema"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Docker PostgreSQL

```bash
# Start
docker-compose up -d postgres

# Stop
docker-compose down

# View logs
docker-compose logs -f postgres

# Connect
psql postgresql://artifactforge:artifactforge@localhost:5432/artifactforge
```

---

## Usage

### CLI

```bash
# Generate an RFP
artifactforge generate rfp "Create an RFP for cloud migration to AWS"

# Generate a blog post
artifactforge generate blog-post "Write about LLM agent architectures"

# List artifacts
artifactforge list

# Get artifact status
artifactforge status <artifact-id>
```

### Python API

```python
from artifactforge import ArtifactForge

client = ArtifactForge()

# Generate artifact
artifact = await client.generate(
    artifact_type="rfp",
    description="Create an RFP for cloud migration to AWS"
)

print(artifact.final_artifact)
```

---

## Development

### Running Tests

```bash
pytest tests/
```

### Code Style

- Black for formatting
- Ruff for linting
- MyPy for type checking

```bash
black .
ruff check .
mypy src/
```

---

## Project Structure

```
artifactforge/
├── src/
│   └── artifactforge/
│       ├── coordinator/      # State machine + orchestration
│       ├── router/          # Schema matching + routing
│       ├── context/         # 6-layer context system
│       ├── learnings/        # Self-evolution system
│       ├── validation/       # Input validation + invariants
│       ├── evaluation/      # LLM-as-Judge framework
│       ├── observability/   # Tracing + metrics
│       ├── tools/           # Research, Generate, Review tools
│       ├── schemas/         # Artifact schemas
│       ├── verification/    # Validation gates
│       └── cli/             # Entry point
├── migrations/              # Alembic migrations
├── tests/                  # Test suite
├── docs/                   # Documentation
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

## License

MIT

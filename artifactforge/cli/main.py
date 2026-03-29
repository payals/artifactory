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
    from artifactforge.agents.llm_gateway import run_model_preflight_check

    logger.info("Running model preflight check...")
    preflight_result = run_model_preflight_check()
    logger.info("Preflight check complete", result=preflight_result)

    initial_state = {
        "artifact_type": artifact_type,
        "user_prompt": description,
        "verification_status": "pending",
        "num_retries": 0,
    }

    result = await app.ainvoke(
        initial_state, config={"configurable": {"thread_id": "cli-session"}}
    )
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

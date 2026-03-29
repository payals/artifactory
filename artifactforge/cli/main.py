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


async def generate(description: str, output_type: str = "report") -> dict:
    """Generate an artifact using the MCRS pipeline.

    Args:
        description: What you want the artifact to be about
        output_type: Type of artifact (report, blog, slides, memo, etc.)
    """
    from artifactforge.agents.llm_gateway import run_model_preflight_check

    logger.info("Running model preflight check...")
    preflight_result = run_model_preflight_check()
    logger.info("Preflight check complete", result=preflight_result)

    # MCRS state - all fields from MCRSState TypedDict
    initial_state = {
        # Input
        "user_prompt": description,
        "conversation_context": None,
        "output_constraints": {"output_type": output_type},
        # Pipeline tracking
        "revision_history": [],
        "current_stage": "",
        "retry_count": 0,
        # Errors & timing
        "errors": [],
        "stage_timing": {},
    }

    logger.info(
        "Starting MCRS pipeline...", description=description, output_type=output_type
    )

    result = await app.ainvoke(
        initial_state, config={"configurable": {"thread_id": "cli-session"}}
    )

    logger.info("Pipeline complete", stage=result.get("current_stage"))
    return result


def main():
    """Main CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="ArtifactForge CLI")
    subparsers = parser.add_subparsers(dest="command")

    gen_parser = subparsers.add_parser("generate", help="Generate an artifact")
    gen_parser.add_argument("description", help="What you want to generate")
    gen_parser.add_argument(
        "--type",
        "-t",
        default="report",
        help="Output type: report, blog, slides, memo, technical_writeup, decision_doc",
    )

    args = parser.parse_args()

    if args.command == "generate":
        result = asyncio.run(generate(args.description, args.type))
        print(result.get("polished_draft") or result.get("draft_v1") or result)


if __name__ == "__main__":
    main()

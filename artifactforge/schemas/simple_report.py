"""Simple report schema and generator."""


def generate_simple_report(user_description: str, context: dict) -> str:
    """Generate a simple report artifact.

    This is a stub implementation.
    """
    return f"""# Simple Report

## Description
{user_description}

## Research Context
{context.get("summary", "No research available")}

## Content
This is a stub report generated from: {user_description}
"""


__all__ = ["generate_simple_report"]

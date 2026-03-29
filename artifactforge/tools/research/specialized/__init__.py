"""Specialized research strategies for domain-specific artifacts."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from artifactforge.tools.research.research_router import (
        ResearchStrategy,
        SpecializedResearcher,
    )


def get_researcher(artifact_type: str) -> "SpecializedResearcher | None":
    """Get specialized researcher for artifact type.

    Returns None if no specialized researcher exists for the artifact type.
    """
    # Lazy loading to avoid circular imports and allow future extension
    researchers = {
        "rfp": _get_rfp_researcher,
        "blog-post": _get_blog_researcher,
        "simple_report": _get_simple_report_researcher,
    }

    if artifact_type in researchers:
        return researchers[artifact_type]()

    return None


def _get_rfp_researcher() -> "SpecializedResearcher":
    """Get RFP specialized researcher."""
    from artifactforge.tools.research.specialized.rfp_researcher import (
        RFPSpecializedResearcher,
    )

    return RFPSpecializedResearcher()


def _get_blog_researcher() -> "SpecializedResearcher":
    """Get blog post specialized researcher."""
    from artifactforge.tools.research.specialized.blog_researcher import (
        BlogSpecializedResearcher,
    )

    return BlogSpecializedResearcher()


def _get_simple_report_researcher() -> "SpecializedResearcher":
    from artifactforge.tools.research.specialized.simple_report_researcher import (
        SimpleReportSpecializedResearcher,
    )

    return SimpleReportSpecializedResearcher()


__all__ = ["get_researcher"]

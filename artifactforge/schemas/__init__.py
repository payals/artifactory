"""Artifact schemas."""

from artifactforge.schemas.simple_report import (
    build_simple_report_schema,
    generate_simple_report,
    infer_report_kind,
)

__all__ = [
    "build_simple_report_schema",
    "generate_simple_report",
    "infer_report_kind",
]

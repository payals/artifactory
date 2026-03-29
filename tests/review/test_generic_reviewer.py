from artifactforge.schemas.simple_report import build_simple_report_schema
from artifactforge.tools.review.generic_reviewer import run_generic_reviewer


def test_generic_reviewer_flags_missing_required_simple_report_sections() -> None:
    schema = build_simple_report_schema(
        "Assess the feasibility of opening an Indian takeout restaurant in Chincoteague"
    )

    result = run_generic_reviewer(
        artifact_type="simple_report",
        draft="# Report\n\n## Executive Summary\nShort draft without the decision sections.",
        context={"summary": "Some research context"},
        schema=schema,
    )

    assert result["passed"] is False
    assert any("Recommendation" in issue for issue in result["issues"])
    assert any("Unit Economics" in issue for issue in result["issues"])
    assert "readability" in result["scores"]

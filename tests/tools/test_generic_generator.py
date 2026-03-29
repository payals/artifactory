from artifactforge.schemas.simple_report import build_simple_report_schema
from artifactforge.tools.generic_generator import run_generic_generator


def test_generic_generator_uses_structured_simple_report_generation() -> None:
    schema = build_simple_report_schema(
        "Assess the feasibility of opening an Indian takeout restaurant in Chincoteague"
    )

    result = run_generic_generator(
        artifact_type="simple_report",
        schema=schema,
        context={
            "summary": "Demand looks seasonal with upside during summer tourism.",
            "key_findings": ["The market is highly seasonal."],
        },
        user_description="Assess the feasibility of opening an Indian takeout restaurant in Chincoteague",
    )

    assert "## Recommendation" in result["draft"]
    assert "## Sources and Evidence Gaps" in result["draft"]
    assert result["metadata"]["model"] == "schema-renderer"

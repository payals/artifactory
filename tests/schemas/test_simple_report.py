from artifactforge.schemas.simple_report import (
    build_simple_report_schema,
    generate_simple_report,
)


def test_build_simple_report_schema_infers_market_feasibility_sections() -> None:
    schema = build_simple_report_schema(
        "Assess the feasibility of opening an Indian takeout restaurant in Chincoteague"
    )

    section_titles = [section["title"] for section in schema["sections"]]

    assert schema["report_kind"] == "market_feasibility"
    assert "Recommendation" in section_titles
    assert "Unit Economics" in section_titles
    assert "Competition and Alternatives" in section_titles


def test_build_simple_report_schema_infers_comparison_sections() -> None:
    schema = build_simple_report_schema(
        "Compare Linear and Jira for a small product team"
    )

    section_titles = [section["title"] for section in schema["sections"]]

    assert schema["report_kind"] == "comparison"
    assert "Options Compared" in section_titles
    assert "Comparison Criteria" in section_titles
    assert "Recommendation" in section_titles


def test_generate_simple_report_renders_sections_and_context() -> None:
    schema = build_simple_report_schema(
        "Assess the feasibility of opening an Indian takeout restaurant in Chincoteague"
    )

    report = generate_simple_report(
        user_description="Assess the feasibility of opening an Indian takeout restaurant in Chincoteague",
        context={
            "summary": "Tourism creates seasonal demand but staffing risk is material.",
            "key_findings": [
                "Peak-season traffic materially exceeds year-round resident demand.",
                "Comparable Indian takeout options are limited nearby.",
            ],
            "research_gaps": ["Validate local permit and meals-tax details."],
            "sources": [{"title": "Town tourism data", "url": "https://example.com"}],
        },
        schema=schema,
    )

    assert "## Recommendation" in report
    assert "## Unit Economics" in report
    assert (
        "Peak-season traffic materially exceeds year-round resident demand." in report
    )
    assert "Validate local permit and meals-tax details." in report

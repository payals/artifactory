from artifactforge.tools.research.specialized.simple_report_researcher import (
    SimpleReportSpecializedResearcher,
)


class TestSimpleReportSpecializedResearcher:
    def setup_method(self) -> None:
        self.researcher = SimpleReportSpecializedResearcher()

    def test_expand_queries_adds_market_feasibility_research_lanes(self) -> None:
        base = ["indian takeout in chincoteague overview"]

        expanded = self.researcher.expand_queries(
            "Assess the feasibility of opening an Indian takeout restaurant in Chincoteague",
            base,
        )

        assert len(expanded) > len(base)
        assert any("competitor" in q.lower() for q in expanded)
        assert any(
            "regulation" in q.lower() or "license" in q.lower() for q in expanded
        )
        assert any("labor" in q.lower() or "staffing" in q.lower() for q in expanded)
        assert any(
            "break-even" in q.lower()
            or "startup" in q.lower()
            or "economics" in q.lower()
            for q in expanded
        )

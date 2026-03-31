"""Tests for RFP specialized researcher."""

import pytest

from artifactforge.tools.research.specialized.rfp_researcher import (
    RFPSpecializedResearcher,
)


class TestRFPSpecializedResearcher:
    def setup_method(self):
        self.researcher = RFPSpecializedResearcher()

    def test_expand_queries_adds_competitor_analysis(self):
        base = ["initial query"]
        expanded = self.researcher.expand_queries("cloud migration", base)
        assert len(expanded) > len(base)
        assert any("competitor" in q.lower() for q in expanded)

    def test_expand_queries_adds_compliance(self):
        base = ["initial query"]
        expanded = self.researcher.expand_queries("data processing", base)
        assert any("compliance" in q.lower() for q in expanded)

    def test_expand_queries_adds_industry_standards(self):
        base = ["initial query"]
        expanded = self.researcher.expand_queries("payment processing", base)
        assert any(
            "industry" in q.lower() or "standards" in q.lower() for q in expanded
        )

    def test_analyze_results_returns_required_keys(self):
        sources = [
            {
                "title": "Top Vendors",
                "snippet": "Vendor comparison",
                "url": "http://ex.com",
            },
        ]
        result = self.researcher.analyze_results(sources, "test query")
        assert "competitors" in result
        assert "requirements_patterns" in result
        assert "compliance_requirements" in result

    def test_extract_competitors(self):
        sources = [
            {
                "title": "Top Cloud Vendors 2026",
                "snippet": "AWS, Azure comparison",
                "url": "http://ex.com",
            },
            {
                "title": "Vendor Selection Guide",
                "snippet": "How to choose",
                "url": "http://ex2.com",
            },
        ]
        competitors = self.researcher._extract_competitors(sources)
        assert len(competitors) > 0

    def test_extract_compliance_keywords(self):
        sources = [
            {
                "title": "GDPR Compliance",
                "snippet": "Requirements for GDPR",
                "url": "http://ex.com",
            },
        ]
        compliance = self.researcher._extract_compliance(sources)
        assert "compliance" in compliance or "GDPR" in compliance

    def test_extract_requirements_patterns_returns_list(self):
        patterns = self.researcher._extract_requirements_patterns()
        assert isinstance(patterns, list)
        assert len(patterns) > 0

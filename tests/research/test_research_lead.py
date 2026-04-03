from artifactforge.agents.research_lead import run_research_lead


def test_run_research_lead_multi_pass_with_deep_analysis(monkeypatch) -> None:
    """Test that the rewritten research_lead:
    1. Generates a research plan via LLM
    2. Executes landscape scan with web_searcher
    3. Runs deep analysis on found URLs
    4. Runs gap-fill pass
    5. Synthesizes into ResearchMap with research_plan attached
    """
    deep_analysis_calls: list[tuple[list[str], str]] = []
    llm_calls: list[tuple[str, str]] = []  # (system_snippet, prompt_snippet)

    # Track which LLM call we're on to return different responses
    call_count = {"n": 0}

    def fake_call_llm(system: str, prompt: str) -> str:
        call_count["n"] += 1
        llm_calls.append((system[:50], prompt[:100]))

        if call_count["n"] == 1:
            # First call: research plan generation
            return """{
                "categories": ["landscape", "technical"],
                "queries": [
                    {"question": "What are AI agents?", "search_query": "AI agents overview", "category": "landscape", "priority": "HIGH", "why_needed": "Core topic"},
                    {"question": "Key frameworks?", "search_query": "AI agent frameworks 2026", "category": "technical", "priority": "MEDIUM", "why_needed": "Technical depth"}
                ],
                "research_depth": "medium",
                "domain_context": "AI agents research"
            }"""
        elif call_count["n"] == 2:
            # Second call: gap-fill analysis
            return '{"unanswered": []}'
        else:
            # Third call: synthesis
            return """{
                "sources": [{"title": "AI Agents Guide", "url": "https://example.com", "source_type": "research", "reliability": "MEDIUM", "notes": "Overview", "publish_date": null}],
                "facts": ["AI agents are autonomous systems"],
                "key_dimensions": ["Architecture", "Capabilities"],
                "competing_views": ["Agents vs workflows debate"],
                "data_gaps": ["Benchmark data missing"],
                "followup_questions": ["What about safety?"]
            }"""

    monkeypatch.setattr(
        "artifactforge.agents.research_lead.run_web_searcher",
        lambda query, **kwargs: {
            "query": query,
            "sources": [
                f"https://example.com/{query.replace(' ', '-')}/1",
                f"https://example.com/{query.replace(' ', '-')}/2",
            ],
            "results": [
                {
                    "title": f"Result for {query}",
                    "url": f"https://example.com/{query.replace(' ', '-')}/1",
                    "snippet": "Relevant snippet about AI agents",
                }
            ],
        },
    )
    monkeypatch.setattr(
        "artifactforge.agents.research_lead.run_deep_analyzer",
        lambda sources, query: (
            deep_analysis_calls.append((sources, query))
            or {
                "summary": f"Deep analysis for {query}",
                "key_findings": [f"Finding for {query}"],
            }
        ),
    )
    monkeypatch.setattr(
        "artifactforge.agents.research_lead._call_llm",
        fake_call_llm,
    )

    result = run_research_lead(
        {
            "user_goal": "AI agents",
            "output_type": "report",
            "audience": "technical",
            "must_answer_questions": ["What matters most?"],
            "likely_missing_dimensions": [],
            "open_questions_to_resolve": [],
            "rigor_level": "MEDIUM",
            "decision_required": False,
        },
        existing_research={"data_gaps": ["Safety concerns"]},
        repair_context={
            "source_node": "final_arbiter",
            "reason": "arbiter_repair_reroute",
        },
    )

    # Verify research plan was generated (first LLM call)
    assert call_count["n"] >= 3, f"Expected at least 3 LLM calls, got {call_count['n']}"

    # Verify deep analysis was called
    assert deep_analysis_calls, "Deep analysis should have been called"

    # Verify synthesis result
    assert result["facts"] == ["AI agents are autonomous systems"]
    assert result["key_dimensions"] == ["Architecture", "Capabilities"]
    assert result["data_gaps"] == ["Benchmark data missing"]

    # Verify research_plan is attached to the result
    assert result.get("research_plan") is not None
    plan = result["research_plan"]
    assert "landscape" in plan["categories"]
    assert len(plan["queries"]) == 2


def test_run_research_lead_fallback_on_plan_failure(monkeypatch) -> None:
    """If research plan generation fails, should fall back to basic queries."""
    call_count = {"n": 0}

    def fake_call_llm(system: str, prompt: str) -> str:
        call_count["n"] += 1
        if call_count["n"] == 1:
            return "INVALID JSON"  # Plan generation fails
        elif call_count["n"] == 2:
            return '{"unanswered": []}'
        else:
            return """{
                "sources": [],
                "facts": ["Fallback fact"],
                "key_dimensions": [],
                "competing_views": [],
                "data_gaps": ["Everything"],
                "followup_questions": []
            }"""

    monkeypatch.setattr(
        "artifactforge.agents.research_lead.run_web_searcher",
        lambda query, **kwargs: {"sources": [], "results": []},
    )
    monkeypatch.setattr(
        "artifactforge.agents.research_lead.run_deep_analyzer",
        lambda sources, query: {"summary": "", "key_findings": []},
    )
    monkeypatch.setattr(
        "artifactforge.agents.research_lead._call_llm",
        fake_call_llm,
    )

    result = run_research_lead(
        {"user_goal": "test topic", "output_type": "report"},
    )

    # Should still produce a result via fallback plan
    assert result.get("research_plan") is not None
    plan = result["research_plan"]
    assert plan["categories"] == ["general"]
    assert len(plan["queries"]) >= 1

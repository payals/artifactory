from artifactforge.agents.evidence_ledger import (
    run_evidence_ledger,
    _build_classification_prompt,
    _create_fallback_claims,
)


class TestBuildClassificationPrompt:
    def test_prompt_includes_sources(self):
        sources = [{"title": "Source A", "source_id": "SRC_001"}]
        facts = ["Fact 1"]
        key_dimensions = ["Dimension 1"]
        prompt = _build_classification_prompt(sources, facts, key_dimensions)
        assert "Source A" in prompt
        assert "SRC_001" in prompt

    def test_prompt_includes_facts(self):
        sources = []
        facts = ["Fact 1", "Fact 2"]
        key_dimensions = []
        prompt = _build_classification_prompt(sources, facts, key_dimensions)
        assert "Fact 1" in prompt
        assert "Fact 2" in prompt

    def test_prompt_includes_key_dimensions(self):
        sources = []
        facts = []
        key_dimensions = ["Dim 1", "Dim 2"]
        prompt = _build_classification_prompt(sources, facts, key_dimensions)
        assert "Dim 1" in prompt
        assert "Dim 2" in prompt

    def test_prompt_includes_repair_context(self):
        sources = []
        facts = []
        key_dimensions = []
        repair = {"source_node": "analyst"}
        prompt = _build_classification_prompt(sources, facts, key_dimensions, repair)
        assert "Repair Context" in prompt


class TestCreateFallbackClaims:
    def test_creates_claims_from_facts_with_sources(self):
        facts = ["Fact 1", "Fact 2"]
        sources = [{"source_id": "SRC_001"}]
        claims = _create_fallback_claims(facts, sources)
        assert len(claims) == 2
        assert claims[0]["claim_id"] == "C001"
        assert claims[0]["claim_text"] == "Fact 1"
        assert claims[0]["classification"] == "VERIFIED"
        assert claims[0]["source_refs"] == ["SRC_001"]
        assert claims[0]["confidence"] == 0.9

    def test_creates_claims_without_sources(self):
        facts = ["Fact 1"]
        sources = []
        claims = _create_fallback_claims(facts, sources)
        assert len(claims) == 1
        assert claims[0]["classification"] == "ASSUMED"
        assert claims[0]["confidence"] == 0.3
        assert claims[0]["source_refs"] == []

    def test_claim_ids_are_sequential(self):
        facts = ["A", "B", "C"]
        sources = []
        claims = _create_fallback_claims(facts, sources)
        assert claims[0]["claim_id"] == "C001"
        assert claims[1]["claim_id"] == "C002"
        assert claims[2]["claim_id"] == "C003"


class TestRunEvidenceLedger:
    def test_returns_empty_when_no_facts_or_dimensions(self, monkeypatch):
        research_map = {"sources": [], "facts": [], "key_dimensions": []}
        result = run_evidence_ledger(research_map)
        assert result["claims"] == []

    def test_successful_classification(self, monkeypatch):
        mock_response = """{
            "claims": [
                {
                    "claim_id": "C001",
                    "claim_text": "Verified fact",
                    "classification": "VERIFIED",
                    "source_refs": ["SRC_001"],
                    "confidence": 0.9,
                    "importance": "HIGH",
                    "dependent_on": [],
                    "notes": "Directly from source"
                }
            ],
            "summary": "1 verified claim"
        }"""
        monkeypatch.setattr(
            "artifactforge.agents.evidence_ledger._call_llm",
            lambda system, prompt: mock_response,
        )
        research_map = {
            "sources": [{"source_id": "SRC_001", "title": "Source A"}],
            "facts": ["Verified fact"],
            "key_dimensions": ["Market size"],
        }
        result = run_evidence_ledger(research_map)
        assert len(result["claims"]) == 1
        assert result["claims"][0]["classification"] == "VERIFIED"
        assert result["summary"] == "1 verified claim"

    def test_auto_generates_claim_id_when_missing(self, monkeypatch):
        mock_response = """{
            "claims": [
                {
                    "claim_text": "No ID claim",
                    "classification": "ASSUMED",
                    "source_refs": [],
                    "confidence": 0.3,
                    "importance": "LOW",
                    "dependent_on": [],
                    "notes": ""
                }
            ],
            "summary": "Fallback"
        }"""
        monkeypatch.setattr(
            "artifactforge.agents.evidence_ledger._call_llm",
            lambda system, prompt: mock_response,
        )
        result = run_evidence_ledger(
            {"sources": [], "facts": ["No ID claim"], "key_dimensions": []}
        )
        assert result["claims"][0]["claim_id"] == "C001"

    def test_llm_failure_triggers_fallback(self, monkeypatch):
        monkeypatch.setattr(
            "artifactforge.agents.evidence_ledger._call_llm",
            lambda system, prompt: "not json",
        )
        research_map = {
            "sources": [{"source_id": "SRC_001"}],
            "facts": ["Fact 1"],
            "key_dimensions": [],
        }
        result = run_evidence_ledger(research_map)
        assert len(result["claims"]) == 1
        assert result["claims"][0]["classification"] == "VERIFIED"
        assert "fallback" in result["summary"].lower()

    def test_deep_analyze_skips_when_no_urls(self, monkeypatch):
        call_llm_calls = []
        monkeypatch.setattr(
            "artifactforge.agents.evidence_ledger._call_llm",
            lambda system, prompt: (
                call_llm_calls.append(True) or '{"claims":[],"summary":""}'
            ),
        )
        research_map = {
            "sources": [{"source_id": "S1", "title": "No URL"}],
            "facts": ["Fact"],
            "key_dimensions": [],
        }
        run_evidence_ledger(research_map, deep_analyze=True)
        assert len(call_llm_calls) == 1

    def test_contract_is_registered(self):
        from artifactforge.coordinator.contracts import (
            EVIDENCE_LEDGER_CONTRACT,
            AGENT_REGISTRY,
        )

        assert "evidence_ledger" in AGENT_REGISTRY
        assert EVIDENCE_LEDGER_CONTRACT.name == "evidence_ledger"

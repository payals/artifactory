from artifactforge.agents.verifier import (
    run_verifier,
    _build_verification_prompt,
)


class TestBuildVerificationPrompt:
    def test_prompt_includes_draft(self):
        prompt = _build_verification_prompt("Draft content", {"claims": []})
        assert "Draft content" in prompt

    def test_prompt_includes_claims_to_verify(self):
        claims = {
            "claims": [
                {
                    "classification": "VERIFIED",
                    "claim_text": "Fact 1",
                    "confidence": 0.9,
                }
            ]
        }
        prompt = _build_verification_prompt("Draft", claims)
        assert "Claims to Verify" in prompt
        assert "Fact 1" in prompt
        assert "0.9" in prompt

    def test_prompt_handles_empty_claims(self):
        claims = {"claims": []}
        prompt = _build_verification_prompt("Draft", claims)
        assert "Claims to Verify" not in prompt

    def test_prompt_handles_missing_claims_key(self):
        claims = {}
        prompt = _build_verification_prompt("Draft", claims)
        assert "Claims to Verify" not in prompt

    def test_draft_is_truncated(self):
        long_draft = "X" * 5000
        prompt = _build_verification_prompt(long_draft, {"claims": []})
        assert len([c for c in prompt if c == "X"]) <= 4000


class TestRunVerifier:
    def test_successful_verification(self, monkeypatch):
        mock_response = """{
            "items": [
                {
                    "claim_id": "C001",
                    "status": "SUPPORTED",
                    "repair_locus": "draft_writer",
                    "notes": "Well supported",
                    "required_action": null
                }
            ],
            "summary": "All claims verified",
            "passed": true
        }"""
        monkeypatch.setattr(
            "artifactforge.agents.verifier._call_llm",
            lambda system, prompt: mock_response,
        )
        result = run_verifier(
            draft="Draft",
            claim_ledger={"claims": []},
        )
        assert result["passed"] is True
        assert result["summary"] == "All claims verified"
        assert len(result["items"]) == 1

    def test_unsupported_claim_detected(self, monkeypatch):
        mock_response = """{
            "items": [
                {
                    "claim_id": "C001",
                    "status": "UNSUPPORTED",
                    "repair_locus": "research_lead",
                    "notes": "No evidence found",
                    "required_action": "add_source"
                }
            ],
            "summary": "Issues found",
            "passed": false
        }"""
        monkeypatch.setattr(
            "artifactforge.agents.verifier._call_llm",
            lambda system, prompt: mock_response,
        )
        result = run_verifier(
            draft="Draft",
            claim_ledger={"claims": []},
        )
        assert result["passed"] is False
        assert result["items"][0]["status"] == "UNSUPPORTED"

    def test_defaults_invalid_repair_locus(self, monkeypatch):
        mock_response = """{
            "items": [
                {
                    "claim_id": "C001",
                    "status": "WEAK",
                    "repair_locus": "invalid_locus",
                    "notes": "Needs work",
                    "required_action": null
                }
            ],
            "summary": "Summary",
            "passed": true
        }"""
        monkeypatch.setattr(
            "artifactforge.agents.verifier._call_llm",
            lambda system, prompt: mock_response,
        )
        result = run_verifier(
            draft="Draft",
            claim_ledger={"claims": []},
        )
        assert result["items"][0]["repair_locus"] == "evidence_ledger"

    def test_llm_failure_returns_fallback(self, monkeypatch):
        monkeypatch.setattr(
            "artifactforge.agents.verifier._call_llm",
            lambda system, prompt: "not json",
        )
        result = run_verifier(
            draft="Draft",
            claim_ledger={"claims": []},
        )
        assert result["items"] == []
        assert result["summary"] == "Verification not completed"
        assert result["passed"] is True

    def test_passed_computed_when_missing(self, monkeypatch):
        mock_response = """{
            "items": [
                {
                    "claim_id": "C001",
                    "status": "UNSUPPORTED",
                    "repair_locus": "research_lead",
                    "notes": "No support",
                    "required_action": "add_source"
                }
            ],
            "summary": "Issues"
        }"""
        monkeypatch.setattr(
            "artifactforge.agents.verifier._call_llm",
            lambda system, prompt: mock_response,
        )
        result = run_verifier(
            draft="Draft",
            claim_ledger={"claims": []},
        )
        assert result["passed"] is False

    def test_contract_is_registered(self):
        from artifactforge.coordinator.contracts import (
            VERIFIER_CONTRACT,
            AGENT_REGISTRY,
        )

        assert "verifier" in AGENT_REGISTRY
        assert VERIFIER_CONTRACT.name == "verifier"

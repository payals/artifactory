 ---
  Critical Issues

  1. ~~Double API call in Firecrawl scraper~~ **FIXED**

  ~~artifactforge/tools/research/firecrawl_scraper.py:199-204 — run_firecrawl_scraper() is called twice in sequence; the first result is immediately overwritten by the second, doubling API costs for every scrape.~~

  2. ~~Visual generator f-string interpolation bug~~ **FALSE POSITIVE**

  ~~artifactforge/agents/visual_generator.py:155-243 — _build_matplotlib_code() builds Python code strings with {visual_id} placeholders that are never interpolated.~~ All return statements use f-strings and `visual_id` is an in-scope parameter — interpolation works correctly. Tests confirm `"visual_V001"` appears in generated code.

  3. ~~OLLAMA_MODEL defined in two places with different defaults~~ **FIXED**

  ~~- artifactforge/agents/llm_gateway.py:20 — hardcoded "kimi-k2.5:cloud"~~
  ~~- artifactforge/agents/llm_client.py:23 — env-based, defaults to "qwen3.5:35b"~~

  ~~Agents get different models depending on which module resolves the default, causing inconsistent behavior.~~
  Fixed: llm_client.py default aligned to "kimi-k2.5:cloud" to match llm_gateway.py.

  4. ~~Global TRACE_ID_CTX is not thread/async-safe~~ **FIXED**

  ~~artifactforge/observability/middleware.py:17,65-76 — Uses a module-level global variable instead of contextvars.ContextVar. Concurrent requests will overwrite each other's trace IDs, breaking all observability.~~
  Fixed: Replaced TRACE_ID_CTX and _LLM_STATS_BEFORE module-level globals with contextvars.ContextVar for proper per-task/per-thread isolation.

  ---
  High Severity

  5. ~~Provider detection hardcodes OpenAI as OpenRouter~~ **FIXED**

  ~~artifactforge/agents/llm_client.py:35 — When OPENAI_API_KEY is set, get_provider() returns "openrouter", making the "openai" case in call_llm() unreachable dead code.~~
  Fixed: get_provider() now checks if OPENAI_API_BASE contains "openrouter.ai" to distinguish OpenRouter from native OpenAI. Tests added in tests/agents/test_llm_client.py.

  6. ~~Adversarial reviewer defaults all repair_locus to "draft_writer"~~ **FIXED**

  ~~artifactforge/agents/adversarial_reviewer.py:90-97 — When the LLM returns an invalid/missing repair_locus, it defaults to "draft_writer" regardless of problem type. Issues like missing_dimension should route to
  research_lead, unsupported_claim to evidence_ledger, etc. This defeats the repair routing system.~~
  Fixed: Added PROBLEM_TYPE_DEFAULT_LOCUS mapping that infers correct repair_locus from problem_type. Falls back to "draft_writer" only when problem_type is also missing/unknown.

  7. READY status routes to polisher instead of visual pipeline or END

  artifactforge/coordinator/mcrs_graph.py:464-471 — When final_arbiter marks status as "READY", it routes to polisher rather than proceeding to the visual pipeline or ending. Semantically wrong — READY should mean
  done.

  8. ~~Missing __init__.py files in 7 directories~~ **FIXED**

  ~~These directories won't work as Python packages:~~
  ~~- artifactforge/tools/generate/ (also empty)~~
  ~~- artifactforge/context/~~
  ~~- artifactforge/verification/~~
  ~~- artifactforge/learnings/~~
  ~~- artifactforge/evaluation/~~
  ~~- artifactforge/validation/~~
  ~~- artifactforge/router/~~
  Fixed: Added empty __init__.py to all 7 directories.

  9. Nested asyncio.run() in web_searcher

  artifactforge/tools/research/web_searcher.py:167-186 — If Tavily fails and falls back to DuckDuckGo, it calls asyncio.run() a second time. This crashes with "cannot be called from a running event loop" in async
  contexts.

  ---
  Medium Severity

  10. Validation system is entirely dead code

  artifactforge/coordinator/validation.py — validate_agent_output(), validate_all_agents(), and should_reroute_for_validation_failures() are defined but never called from the graph. The validation infrastructure
  exists but is unintegrated.

  11. TypedDict instantiation crashes on malformed LLM output

  Multiple agents construct TypedDicts from raw LLM JSON without field defaults:
  - evidence_ledger.py:137 — schemas.Claim(**claim)
  - adversarial_reviewer.py:99 — schemas.RedTeamIssue(**i)
  - verifier.py:94 — schemas.VerificationItem(**i)

  All crash with TypeError if the LLM omits any required field.

  12. Verifier silently passes on parsing failure

  artifactforge/agents/verifier.py:99 — When parsing produces no items, all() over an empty list returns True, so verification automatically passes. Should fail-safe to False.

  13. Prompt/schema mismatches

  - research_lead.py:214-225 — Prompt asks for title, url, relevance_score, key_findings but schema requires source_id, source_type, reliability, notes, publish_date
  - evidence_ledger.py:20-58 — Prompt says "return claims array" without specifying required fields (classification, confidence, importance, source_refs, dependent_on)

  14. Polisher has no return path after re-run

  artifactforge/coordinator/mcrs_graph.py:154 — If final_arbiter routes back to polisher for repair, the polisher proceeds directly to visual_designer. Changes are never re-verified.

  15. MCRSState dead fields

  - state.py:93 — draft_version is never incremented
  - state.py:119-120 — current_stage never set, retry_count never incremented
  - mcrs_graph.py:14 — MAX_RETRIES = 2 defined but never used

  16. Context7 sends empty Authorization header

  artifactforge/tools/research/context7_search.py:53-59 — When CONTEXT7_API_KEY is None, the nested ternary sends {"Authorization": ""} instead of {}.

  17. Contract/schema inconsistencies

  - Visual agent contracts declare singular output schemas but agents return lists
  - FINAL_ARBITER_CONTRACT lists "all_artifacts" as input, which doesn't exist in MCRSState
  - repair_locus Literal types exclude visual agents

  18. Outdated Anthropic API in deep_analyzer

  artifactforge/tools/research/deep_analyzer.py:96 — Uses claude-3-haiku-20240307 and API version 2023-06-01, both outdated.

  ---
  Test Suite Problems

  19. Zero test coverage for:

  - llm_client.py, all research tools (web_searcher, deep_analyzer, exa_search, perplexity_search, context7_search, firecrawl_scraper), coordinator/validation.py, coordinator/contracts.py, tests/review/ and
  tests/tools/ are empty stubs

  20. Vacuous test assertion

  tests/research/specialized/test_rfp_researcher.py:45-59 — assert len(competitors) >= 0 always passes (list length can never be negative).

  21. Shared mutable class state in test mock

  tests/cli/test_main.py:67-77 — _FakeWeasyHTML uses class-level variables (last_string, written_paths) shared across tests, creating order-dependent test failures.

  22. All E2E tests mock research tools

  tests/e2e/test_mcrs_pipeline.py:60-86 — Every research tool is patched with hardcoded perfect responses. Real integration failures are invisible.

  23. Weak quality gate assertions

  tests/e2e/test_mcrs_pipeline.py:471-502 — Quality checks are just len(final_artifact) > 100 and checking for keyword "Python". No structural, logical, or schema validation.

  ---
  Bottom line: The core pipeline architecture (LangGraph graph, agent contracts, epistemic tracking) is well-designed, but the implementation has significant gaps: the visual pipeline is buggy end-to-end (f-string
  bug, mermaid fallthrough, no re-verification), the repair routing system is undermined by wrong defaults, LLM output parsing is fragile throughout, and the validation system was built but never wired in. The test
  suite catches almost none of this because it mocks all LLM calls with perfect responses and has vacuous assertions.

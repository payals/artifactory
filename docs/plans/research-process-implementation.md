# Research Process Implementation Plan

**Project:** ArtifactForge - Research Layer Enhancement  
**Author:** Implementation Plan  
**Date:** 2026-03-27  
**Status:** Approved  
**Approved decisions:** Parallel queries only, Model configurable, No caching MVP, Learnings capture both, Specialized researchers implemented  

---

## 1. Executive Summary

This plan addresses the gaps between the architecture design and current implementation of the Research Layer. The current implementation is ~45% compliant with the architecture specification.

### Key Gaps Identified

| Gap | Priority | Impact |
|-----|----------|--------|
| Missing ResearchRouter | P0 | No intelligent strategy selection |
| No error handling | P0 | Silent failures return fake data |
| Missing tests | P0 | No quality assurance |
| Sequential execution | P1 | Latency issues |
| Missing specialized researchers | P1 | Lower quality for domain artifacts |
| No context layer integration | P2 | Misses patterns/learnings |

---

## 2. Implementation Phases

### Phase 1: Foundation (MVP) - 3-4 days

**Goal:** Fix critical issues, add tests, enable intelligent routing, prepare for specialized researchers

#### 1.1 ResearchRouter Implementation

**Files to create/modify:**
- `artifactforge/tools/research/research_router.py` (NEW)
- `artifactforge/tools/research/__init__.py` (MODIFY)

**Implementation:**

```python
# artifactforge/tools/research/research_router.py
from typing import Literal
from pydantic import BaseModel, Field

class ResearchStrategy(BaseModel):
    """Defines how to conduct research for an artifact type."""
    artifact_type: str
    depth: Literal["shallow", "medium", "deep"] = "medium"
    search_queries: list[str]
    domains: list[str] = []
    parallel_searches: bool = True

class ResearchRouter:
    """Routes to appropriate research strategy based on artifact type."""

    DEFAULT_STRATEGIES = {
        "rfp": ResearchStrategy(
            artifact_type="rfp",
            depth="deep",
            search_queries=[
                "competitor analysis {topic}",
                "industry best practices {topic}",
                "{topic} requirements template",
            ],
            domains=["competitor-analysis", "requirements-gathering"],
        ),
        "blog-post": ResearchStrategy(
            artifact_type="blog-post",
            depth="medium",
            search_queries=[
                "{topic} latest trends 2026",
                "{topic} SEO keywords",
                "related topics to {topic}",
            ],
            domains=["seo", "trending-topics"],
        ),
        "simple_report": ResearchStrategy(
            artifact_type="simple_report",
            depth="shallow",
            search_queries=["{topic} overview"],
            domains=[],
        ),
    }

    def route(self, artifact_type: str, user_description: str) -> ResearchStrategy:
        """Determine research strategy for artifact type."""
        strategy = self.DEFAULT_STRATEGIES.get(
            artifact_type,
            ResearchStrategy(
                artifact_type=artifact_type,
                depth="medium",
                search_queries=[user_description],
            )
        )
        # Substitute {topic} placeholder
        strategy.search_queries = [
            q.replace("{topic}", user_description) for q in strategy.search_queries
        ]
        return strategy

research_router = ResearchRouter()
```

**Router integration into research_node:**

```python
# artifactforge/coordinator/nodes.py - research_node
def research_node(state: GraphState) -> dict[str, Any]:
    """Research phase - intelligent strategy selection."""
    user_description = state.get("user_description", "")
    artifact_type = state.get("artifact_type", "simple_report")

    # Get strategy from router
    strategy = research_router.route(artifact_type, user_description)

    # Execute searches based on strategy
    if strategy.parallel_searches:
        results = execute_parallel_searches(strategy.search_queries, strategy.depth)
    else:
        results = execute_sequential_searches(strategy.search_queries, strategy.depth)

    return {
        "research_output": results["analysis"],
        "research_sources": results["sources"],
    }
```

#### 1.2 Error Handling Improvements

**Files to modify:**
- `artifactforge/tools/research/web_searcher.py`
- `artifactforge/tools/research/deep_analyzer.py`

**Changes:**

```python
# web_searcher.py - Add error result type
from dataclasses import dataclass
from typing import Union

@dataclass
class SearchResult:
    success: bool
    query: str
    results: list[dict]
    sources: list[str]
    error: str | None = None

async def _search_tavily(query: str, num_results: int) -> SearchResult:
    try:
        # ... existing code ...
        return SearchResult(success=True, query=query, results=..., sources=...)
    except httpx.HTTPStatusError as e:
        return SearchResult(
            success=False,
            query=query,
            results=[],
            sources=[],
            error=f"HTTP {e.response.status_code}: {e.response.text[:200]}"
        )
    except Exception as e:
        return SearchResult(
            success=False,
            query=query,
            results=[],
            sources=[],
            error=str(e)
        )

@tool(args_schema=WebSearchInput)
def web_searcher(query: str, num_results: int = 5) -> dict[str, Any]:
    """Search the web for information. Returns URLs and summaries.
    
    Raises:
        SearchError: If all search backends fail
    """
    result = asyncio.run(_search_tavily(query, num_results))
    
    if not result.success:
        # Try fallback
        fallback = asyncio.run(_search_ddg(query, num_results))
        if not fallback.success:
            raise SearchError(f"All search backends failed: {result.error}, {fallback.error}")
        return fallback
    
    return result
```

```python
# deep_analyzer.py - Add content validation
async def _fetch_url_content(url: str) -> dict[str, str]:
    """Fetch content from URL with proper error handling."""
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            text = response.text
            
            # Validate content is substantial
            if len(text) < 100:
                return {"url": url, "content": "", "error": "Content too short"}
            
            return {"url": url, "content": text[:10000], "error": None}
    except httpx.HTTPError as e:
        return {"url": url, "content": "", "error": str(e)}
```

#### 1.3 Unit Tests

**Files to create:**
- `tests/research/test_web_searcher.py`
- `tests/research/test_deep_analyzer.py`
- `tests/research/test_research_router.py`

**Test structure:**

```python
# tests/research/test_research_router.py
import pytest
from artifactforge.tools.research.research_router import ResearchRouter, ResearchStrategy

class TestResearchRouter:
    def setup_method(self):
        self.router = ResearchRouter()

    def test_route_rfp_returns_deep_strategy(self):
        strategy = self.router.route("rfp", "cloud migration")
        assert strategy.depth == "deep"
        assert len(strategy.search_queries) >= 3
        assert "cloud migration" in strategy.search_queries[0]

    def test_route_blog_post_returns_medium_strategy(self):
        strategy = self.router.route("blog-post", "LLM agents")
        assert strategy.depth == "medium"
        assert len(strategy.search_queries) >= 3

    def test_route_unknown_returns_default(self):
        strategy = self.router.route("unknown_type", "test query")
        assert strategy.depth == "medium"
        assert strategy.search_queries == ["test query"]

    def test_query_substitution(self):
        strategy = self.router.route("rfp", "AWS deployment")
        for q in strategy.search_queries:
            assert "{topic}" not in q

    def test_specialized_researcher_integrated(self):
        """RFP should have more queries after specialized researcher enhancement."""
        strategy_rfp = self.router.route("rfp", "cloud migration")
        strategy_report = self.router.route("simple_report", "cloud migration")
        # RFP should have more queries due to specialized researcher
        assert len(strategy_rfp.search_queries) > len(strategy_report.search_queries)
```

```python
# tests/research/specialized/test_rfp_researcher.py
import pytest
from artifactforge.tools.research.specialized.rfp_researcher import rfp_researcher

class TestRFPResearcher:
    def setup_method(self):
        self.researcher = rfp_researcher

    def test_expand_queries_adds_competitor_analysis(self):
        base = ["initial query"]
        expanded = self.researcher.expand_queries("cloud migration", base)
        assert len(expanded) > len(base)
        assert any("competitor" in q.lower() for q in expanded)

    def test_expand_queries_adds_compliance(self):
        base = ["initial query"]
        expanded = self.researcher.expand_queries("data processing", base)
        assert any("compliance" in q.lower() for q in expanded)

    def test_analyze_results_returns_required_keys(self):
        sources = [
            {"title": "Top Vendors", "snippet": "Vendor comparison", "url": "http://ex.com"},
        ]
        result = self.researcher.analyze_results(sources, "test query")
        assert "competitors" in result
        assert "requirements_patterns" in result
        assert "compliance_requirements" in result
```

```python
# tests/research/specialized/test_blog_researcher.py
import pytest
from artifactforge.tools.research.specialized.blog_researcher import blog_researcher

class TestBlogResearcher:
    def setup_method(self):
        self.researcher = blog_researcher

    def test_expand_queries_adds_seo_keywords(self):
        base = ["initial query"]
        expanded = self.researcher.expand_queries("AI agents", base)
        assert any("seo" in q.lower() for q in expanded)

    def test_expand_queries_adds_trending(self):
        base = ["initial query"]
        expanded = self.researcher.expand_queries("LLM", base)
        assert any("trend" in q.lower() for q in expanded)

    def test_analyze_results_returns_required_keys(self):
        sources = [
            {"title": "How to use AI", "snippet": "Guide for beginners", "url": "http://ex.com"},
        ]
        result = self.researcher.analyze_results(sources, "AI guide")
        assert "trending_angles" in result
        assert "seo_keywords" in result
        assert "content_gaps" in result
```

---

### Phase 2: Performance - 1-2 days

**Goal:** Add parallel execution, improve latency

#### 2.1 Parallel Search Execution

**Files to modify:**
- `artifactforge/tools/research/research_router.py`
- `artifactforge/coordinator/nodes.py`

**Implementation:**

```python
# artifactforge/tools/research/research_router.py

async def execute_parallel_searches(
    queries: list[str], 
    depth: str
) -> dict[str, Any]:
    """Execute multiple searches in parallel."""
    num_results = {"shallow": 3, "medium": 5, "deep": 10}[depth]
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        tasks = [
            _search_tavily_async(client, query, num_results)
            for query in queries
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Aggregate results
    all_sources = []
    all_results = []
    for result in results:
        if isinstance(result, Exception):
            continue  # Skip failed searches
        all_sources.extend(result.sources)
        all_results.extend(result.results)
    
    # Deduplicate by URL
    seen_urls = set()
    unique_results = []
    unique_sources = []
    for r in all_results:
        if r.url not in seen_urls:
            seen_urls.add(r.url)
            unique_results.append(r)
            unique_sources.append(r.url)
    
    # Analyze combined results
    analysis = await deep_analyze_async(unique_sources[:10], combined_query)
    
    return {
        "analysis": analysis,
        "sources": unique_sources,
        "results": unique_results,
    }
```

#### 2.2 Caching Layer (Optional Enhancement)

Add Redis or in-memory caching for frequent searches:
- Cache search results for 1 hour
- Use query hash as cache key
- Skip if same query executed recently

---

### Phase 3: Specialized Research - 2-3 days

**Goal:** Implement specialized researchers for domain artifacts

#### 3.1 RFP Researcher

**Files to create:**
- `artifactforge/tools/research/specialized/rfp_researcher.py`
- `artifactforge/tools/research/specialized/blog_researcher.py`

**Capabilities:**
- Competitor analysis queries
- Industry standards research
- Requirements template search
- Compliance framework discovery

**Implementation:**

```python
# artifactforge/tools/research/specialized/rfp_researcher.py
"""RFP-specific research strategies."""
from typing import Protocol

class RFPResearcher:
    """Expands RFP research with domain-specific queries."""
    
    def expand_queries(self, user_description: str, base_queries: list[str]) -> list[str]:
        """Add RFP-specific research queries."""
        expanded = list(base_queries)
        
        # Add competitor analysis
        expanded.append(f"top RFP software vendors competitive landscape")
        expanded.append(f"successful RFP examples {user_description}")
        
        # Add requirements gathering
        expanded.append(f"RFP requirements checklist best practices")
        expanded.append(f"industry standards for {user_description}")
        
        # Add compliance
        expanded.append(f"compliance requirements for {user_description}")
        
        return expanded
    
    def analyze_results(self, sources: list[dict], query: str) -> dict:
        """Extract RFP-specific insights from search results."""
        # Identify competitor mentions
        competitors = self._extract_competitors(sources)
        
        # Extract requirements patterns
        requirements = self._extract_requirements_patterns(sources)
        
        # Identify compliance requirements
        compliance = self._extract_compliance(sources)
        
        return {
            "competitors": competitors,
            "requirements_patterns": requirements,
            "compliance_requirements": compliance,
            "best_practices": self._extract_best_practices(sources),
        }
    
    def _extract_competitors(self, sources: list[dict]) -> list[str]:
        """Identify named competitors in results."""
        competitor_keywords = ["vendor", "solution", "platform", "provider"]
        competitors = []
        for source in sources:
            title = source.get("title", "").lower()
            snippet = source.get("snippet", "").lower()
            # Simple heuristic - in production would use NER
            if any(kw in title for kw in competitor_keywords):
                competitors.append(source.get("title", "")[:100])
        return list(set(competitors))[:5]
    
    def _extract_requirements_patterns(self, sources: list[dict]) -> list[str]:
        """Extract common requirements from RFP examples."""
        patterns = [
            "Technical requirements section",
            "Pricing and payment terms",
            "Implementation timeline",
            "Support and maintenance",
            "Security and compliance",
        ]
        return patterns
    
    def _extract_compliance(self, sources: list[dict]) -> list[str]:
        """Extract compliance/regulatory requirements."""
        compliance_keywords = ["compliance", "regulation", "certification", "GDPR", "SOC", "ISO"]
        compliance = []
        for source in sources:
            content = (source.get("title", "") + " " + source.get("snippet", "")).lower()
            for kw in compliance_keywords:
                if kw.lower() in content:
                    compliance.append(kw)
        return list(set(compliance))
    
    def _extract_best_practices(self, sources: list[dict]) -> list[dict]:
        """Extract RFP best practices from sources."""
        return [
            {"source": s.get("url", ""), "practice": s.get("snippet", "")[:200]}
            for s in sources[:3]
        ]


rfp_researcher = RFPResearcher()
```

#### 3.2 Blog Researcher

**Capabilities:**
- Trending topic detection
- SEO keyword extraction
- Related article discovery
- Content gap analysis

**Implementation:**

```python
# artifactforge/tools/research/specialized/blog_researcher.py
"""Blog post-specific research strategies."""
from typing import TypedDict

class BlogInsight(TypedDict):
    trending_angles: list[str]
    seo_keywords: list[str]
    related_topics: list[str]
    content_gaps: list[str]

class BlogResearcher:
    """Expands blog research with content marketing strategies."""
    
    def expand_queries(self, user_description: str, base_queries: list[str]) -> list[str]:
        """Add blog-specific research queries."""
        expanded = list(base_queries)
        
        # Add trending analysis
        expanded.append(f"{user_description} trends 2026")
        expanded.append(f"popular {user_description} articles")
        
        # Add SEO research
        expanded.append(f"{user_description} SEO keywords")
        expanded.append(f"{user_description} search volume")
        
        # Add related topics
        expanded.append(f"{user_description} related topics")
        expanded.append(f"questions about {user_description}")
        
        return expanded
    
    def analyze_results(self, sources: list[dict], query: str) -> dict:
        """Extract blog-specific insights from search results."""
        return {
            "trending_angles": self._extract_trending_angles(sources),
            "seo_keywords": self._extract_seo_keywords(sources, query),
            "related_topics": self._extract_related_topics(sources),
            "content_gaps": self._identify_content_gaps(sources, query),
        }
    
    def _extract_trending_angles(self, sources: list[dict]) -> list[str]:
        """Extract trending angles from top articles."""
        angles = []
        for source in sources[:5]:
            title = source.get("title", "")
            snippet = source.get("snippet", "")
            # Heuristic: titles with numbers, how-to, guide, tips
            if any(kw in title.lower() for kw in ["how", "guide", "tips", "best", "top"]):
                angles.append(title[:100])
        return angles
    
    def _extract_seo_keywords(self, sources: list[dict], query: str) -> list[str]:
        """Extract SEO keywords from search results."""
        # Common SEO patterns
        keywords = set()
        
        for source in sources[:10]:
            title = source.get("title", "").lower()
            snippet = source.get("snippet", "").lower()
            
            # Extract phrases in parentheses (often keywords)
            import re
            parens = re.findall(r'\(([^)]+)\)', title + snippet)
            keywords.update(parens)
            
            # Extract quoted phrases
            quoted = re.findall(r'"([^"]+)"', title + snippet)
            keywords.update(quoted)
        
        return list(keywords)[:10]
    
    def _extract_related_topics(self, sources: list[dict]) -> list[str]:
        """Extract related topics for internal linking."""
        topics = []
        for source in sources[:5]:
            title = source.get("title", "")
            if title:
                topics.append(title[:80])
        return topics
    
    def _identify_content_gaps(self, sources: list[dict], query: str) -> list[str]:
        """Identify content gaps that new article could fill."""
        gaps = []
        existing_titles = [s.get("title", "").lower() for s in sources]
        
        # Simple gap analysis based on common patterns
        common_patterns = ["beginner", "advanced", "comparison", "vs"]
        for pattern in common_patterns:
            if not any(pattern in t for t in existing_titles):
                gaps.append(f"No {pattern} guide found - potential gap")
        
        return gaps[:3]


blog_researcher = BlogResearcher()
```

**Integration with router:**

```python
# artifactforge/tools/research/research_router.py

from artifactforge.tools.research.specialized.rfp_researcher import rfp_researcher
from artifactforge.tools.research.specialized.blog_researcher import blog_researcher

class ResearchRouter:
    """Routes to appropriate research strategy based on artifact type."""
    
    SPECIALIZED_RESEARCHERS = {
        "rfp": rfp_researcher,
        "blog-post": blog_researcher,
    }
    
    def route(
        self, 
        artifact_type: str, 
        user_description: str
    ) -> ResearchStrategy:
        """Determine research strategy for artifact type."""
        # Get base strategy
        strategy = self.DEFAULT_STRATEGIES.get(
            artifact_type,
            ResearchStrategy(
                artifact_type=artifact_type,
                depth="medium",
                search_queries=[user_description],
            )
        )
        
        # Substitute {topic} placeholder
        strategy.search_queries = [
            q.replace("{topic}", user_description) 
            for q in strategy.search_queries
        ]
        
        # Enhance with specialized researcher if available
        if artifact_type in self.SPECIALIZED_RESEARCHERS:
            researcher = self.SPECIALIZED_RESEARCHERS[artifact_type]
            strategy.search_queries = researcher.expand_queries(
                user_description, 
                strategy.search_queries
            )
        
        return strategy
```

---

### Phase 4: Context Integration - 2-3 days

**Goal:** Integrate 6-layer context system and learnings

#### 4.1 Context Builder

**Files to create:**
- `artifactforge/context/context_builder.py`

**Implementation:**

```python
# artifactforge/context/context_builder.py
from typing import Any

class ContextBuilder:
    """Builds 6-layer research context."""
    
    async def build_research_context(
        self,
        artifact_type: str,
        user_description: str,
    ) -> dict[str, Any]:
        """Build complete context for research phase."""
        
        # Layer 1: Schema context
        schema_context = await self._get_schema_context(artifact_type)
        
        # Layer 2: Guidelines from knowledge base
        guidelines = await self._get_guidelines(artifact_type)
        
        # Layer 3: Patterns from prior generations
        patterns = await self._get_patterns(artifact_type)
        
        # Layer 4: Sources (current research - handled by research tools)
        sources_context = {}
        
        # Layer 5: Learnings from past failures
        learnings = await self._get_learnings(artifact_type)
        
        # Layer 6: Runtime preferences
        runtime = await self._get_runtime_context()
        
        return {
            "schema": schema_context,
            "guidelines": guidelines,
            "patterns": patterns,
            "learnings": learnings,
            "runtime": runtime,
        }
    
    async def _get_learnings(self, artifact_type: str) -> list[dict]:
        """Retrieve validated learnings for artifact type."""
        from artifactforge.db.crud import get_validated_learnings
        
        learnings = await get_validated_learnings(artifact_type)
        return [
            {
                "context": l.context,
                "fix": l.fix_applied,
                "confidence": l.confidence,
            }
            for l in learnings
            if l.confidence > 0.7
        ]
```

#### 4.2 Learnings Capture

**Files to modify:**
- `artifactforge/coordinator/nodes.py`

```python
def research_node(state: GraphState) -> dict[str, Any]:
    """Research phase with learnings integration."""
    try:
        # ... existing research logic ...
        
        return {
            "research_output": analysis.get("analysis", {}),
            "research_sources": sources,
        }
    except Exception as e:
        # Capture failure for learnings
        await capture_learning(
            artifact_type=state.get("artifact_type"),
            phase="research",
            failure_mode=str(e),
            context={"query": search_query},
        )
        raise
```

---

## 3. File Structure Changes

```
artifactforge/
├── tools/
│   └── research/
│       ├── __init__.py
│       ├── web_searcher.py          # MODIFY: Error handling
│       ├── deep_analyzer.py         # MODIFY: Content validation
│       ├── research_router.py       # NEW: Strategy selection
│       └── specialized/             # NEW: Phase 3
│           ├── __init__.py
│           ├── rfp_researcher.py
│           └── blog_researcher.py
├── context/                         # NEW: Phase 4
│   ├── __init__.py
│   └── context_builder.py
├── coordinator/
│   ├── __init__.py                 # MODIFY: Updated nodes
│   └── nodes.py                    # MODIFY: Research integration
└── tests/
    └── research/                    # NEW: Phase 1
        ├── __init__.py
        ├── test_web_searcher.py
        ├── test_deep_analyzer.py
        ├── test_research_router.py
        └── specialized/             # NEW: Phase 3
            ├── __init__.py
            ├── test_rfp_researcher.py
            └── test_blog_researcher.py
```

---

## 4. Testing Strategy

### 4.1 Unit Tests (Phase 1)
- ResearchRouter routing logic
- WebSearcher error handling
- DeepAnalyzer content validation

### 4.2 Integration Tests (Phase 2)
- Full research flow with mocked LLM
- Parallel execution verification
- Cache behavior

### 4.3 E2E Tests (Phase 3)
- Real API calls (with test API keys)
- End-to-end artifact generation
- Quality gate validation

---

## 5. Migration Strategy

### 5.1 Backward Compatibility
- ResearchRouter returns equivalent of current behavior for unknown artifact types
- No changes to public API signatures
- Graceful degradation if new features unavailable

### 5.2 Database Changes
- No new tables required (research_config JSONB already exists)
- Optional: Add indexes on learnings table for faster retrieval

---

## 6. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Research latency | < 5s (medium depth) | Instrumented timing |
| Search success rate | > 95% | Error log analysis |
| Test coverage | > 80% | pytest --cov |
| Routing accuracy | > 90% | A/B test on known artifact types |

---

## 7. Dependencies

### External
- httpx (already in use)
- pytest (already in dev deps)
- pytest-asyncio (NEW - for async tests)

### Internal
- artifactforge.db.crud (for learnings retrieval)
- artifactforge.schemas (for schema context)

---

## 8. Decisions (Finalized)

| Question | Decision | Rationale |
|----------|----------|-----------|
| Parallel execution scope | **Queries only** | Safe, good ROI, avoids complexity |
| Specialized researchers | **Implement now** | User priority |
| Model selection | **Configurable** | Future-proof, low effort |
| Caching | **Skip MVP** | Premature optimization |
| Learnings capture | **Both** | Most complete data |

---

## 9. Implementation Order

```
Week 1:
├── Day 1-2: ResearchRouter + error handling
├── Day 3:   Unit tests
└── Day 4-5: Parallel execution

Week 2:
├── Day 1-2: RFP Researcher + Blog Researcher
├── Day 3-4: Context layer integration
└── Day 5:   Integration tests
```

---

## Appendix A: Current vs. Target State

| Component | Current | Target |
|-----------|---------|--------|
| ResearchRouter | ❌ Missing | ✅ Intelligent selection |
| Error handling | ❌ Fake results | ✅ Proper errors |
| Parallel execution | ❌ Sequential | ✅ Async parallel (queries only) |
| Specialized researchers | ❌ Missing | ✅ RFP + Blog experts |
| 6-layer context | ❌ Missing | ✅ Full integration |
| Tests | ❌ None | ✅ >80% coverage |
| Learnings capture | ❌ Missing | ✅ Auto-capture |
| Model configurability | ❌ Hardcoded Haiku | ✅ Configurable per tool |

## Appendix B: Implementation Checklist

- [ ] Phase 1: ResearchRouter implementation
- [ ] Phase 1: Error handling improvements (web_searcher, deep_analyzer)
- [ ] Phase 1: Unit tests for core research tools
- [ ] Phase 2: Parallel query execution
- [ ] Phase 3: RFP Researcher implementation
- [ ] Phase 3: Blog Researcher implementation  
- [ ] Phase 3: Specialized researcher tests
- [ ] Phase 4: Context builder implementation
- [ ] Phase 4: Learnings capture integration
- [ ] Phase 4: Integration tests
- [ ] Verify >80% test coverage
- [ ] Instrument timing metrics

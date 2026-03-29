# MCRS Implementation Plan for ArtifactForge

## Executive Summary

| Aspect | Current State | Target State | Gap |
|--------|--------------|--------------|-----|
| Pipeline | 5-node simple pipeline | 10-agent MCRS system | **Massive** |
| State | 40-line GraphState | Full epistemic state with 7+ artifacts | **Large** |
| Tools | Generic (research, generate, review) | 10 specialized agents with contracts | **Large** |
| Quality Gates | Simple pass/fail | Blocking gates with revision loops | **Large** |
| Claims | None | VERIFIED/DERIVED/ASSUMED classification | **Massive** |

---

## Phase 1: Foundation (Week 1-2)

### 1.1 Expanded State Schema

Create new `MCRSState` in `coordinator/state.py` that holds all artifacts:

```python
class MCRSState(TypedDict):
    # Input
    user_prompt: str
    conversation_context: Optional[list]
    output_constraints: Optional[dict]
    
    # Phase 1: Intent
    execution_brief: Optional[ExecutionBrief]  # NEW
    
    # Phase 2: Research
    research_map: Optional[ResearchMap]  # NEW
    
    # Phase 3: Evidence
    claim_ledger: Optional[ClaimLedger]  # NEW - CORE
    
    # Phase 4: Analysis
    analytical_backbone: Optional[AnalyticalBackbone]  # NEW
    
    # Phase 5: Strategy
    content_blueprint: Optional[ContentBlueprint]  # NEW
    
    # Phase 6: Draft
    draft_v1: Optional[str]
    draft_version: int
    
    # Phase 7: Review
    red_team_review: Optional[RedTeamReview]  # NEW
    
    # Phase 8: Verification
    verification_report: Optional[VerificationReport]  # NEW
    
    # Phase 9: Polish
    polished_draft: Optional[str]
    
    # Phase 10: Release
    release_decision: Optional[ReleaseDecision]  # NEW
    
    # Revision tracking
    revision_history: list[dict]
    retry_count: int
    
    # Metadata
    errors: list[str]
    stage_timing: dict
```

### 1.2 Artifact Schemas

Create `coordinator/artifacts.py` with all schemas:

```python
# Phase 1: Execution Brief
class ExecutionBrief(TypedDict):
    user_goal: str
    output_type: str  # report, blog, slides, memo, etc.
    audience: str
    tone: str
    must_answer_questions: list[str]
    constraints: list[str]
    success_criteria: list[str]
    likely_missing_dimensions: list[str]
    decision_required: bool
    rigor_level: Literal["LOW", "MEDIUM", "HIGH"]
    persuasion_level: Literal["LOW", "MEDIUM", "HIGH"]
    open_questions_to_resolve: list[str]

# Phase 2: Research Map
class ResearchSource(TypedDict):
    source_id: str
    title: str
    source_type: Literal["official", "news", "research", "reference", "internal", "other"]
    reliability: Literal["HIGH", "MEDIUM", "LOW"]
    notes: str

class ResearchMap(TypedDict):
    sources: list[ResearchSource]
    facts: list[str]
    key_dimensions: list[str]
    competing_views: list[str]
    data_gaps: list[str]
    followup_questions: list[str]

# Phase 3: Claim Ledger - CORE
class Claim(TypedDict):
    claim_id: str
    claim_text: str
    classification: Literal["VERIFIED", "DERIVED", "ASSUMED"]
    source_refs: list[str]
    confidence: float  # 0.0-1.0
    importance: Literal["HIGH", "MEDIUM", "LOW"]
    dependent_on: list[str]  # claim_ids this depends on
    notes: str

class ClaimLedger(list[Claim]):
    pass

# Phase 4: Analytical Backbone
class AnalyticalBackbone(TypedDict):
    key_findings: list[str]
    primary_drivers: list[str]
    implications: list[str]
    risks: list[str]
    sensitivities: list[str]
    counterarguments: list[str]
    recommendation_logic: list[str]
    open_unknowns: list[str]

# Phase 5: Content Blueprint
class ContentBlueprint(TypedDict):
    structure: list[str]  # section headers
    section_purposes: dict[str, str]
    narrative_flow: str
    visual_elements: list[dict]
    key_takeaways: list[str]
    audience_guidance: list[str]

# Phase 7: Red Team Review
class RedTeamIssue(TypedDict):
    issue_id: str
    severity: Literal["HIGH", "MEDIUM", "LOW"]
    section: str
    problem_type: Literal["missing_dimension", "unsupported_claim", "shallow_analysis", 
                         "overconfidence", "weak_recommendation", "audience_mismatch",
                         "poor_structure", "misleading_framing", "unaddressed_risk",
                         "unexamined_assumption"]
    explanation: str
    suggested_fix: str

class RedTeamReview(list[RedTeamIssue]):
    pass

# Phase 8: Verification Report
class VerificationItem(TypedDict):
    claim_id: str
    status: Literal["SUPPORTED", "WEAK", "UNSUPPORTED", "INCONSISTENT"]
    notes: str
    required_action: Literal["add_source", "reclassify_claim", "downgrade_language",
                            "remove_claim", "fix_number", "resolve_contradiction"]

class VerificationReport(list[VerificationItem]):
    pass

# Phase 10: Release Decision
class ReleaseDecision(TypedDict):
    status: Literal["READY", "NOT_READY"]
    confidence: float
    remaining_risks: list[str]
    known_gaps: list[str]
    notes: str
```

### 1.3 Agent Contract System

Create `coordinator/contracts.py` with base contract:

```python
from typing import Any, Callable
from dataclasses import dataclass

@dataclass
class AgentContract:
    name: str
    mission: str
    inputs: list[str]
    required_output_schema: dict
    forbidden_behaviors: list[str]
    pass_fail_criteria: list[str]
    execute: Callable  # The actual agent function

# Decorator for registering agents
def agent_contract(contract: AgentContract):
    """Decorator to register an agent with its contract."""
    AGENT_REGISTRY[contract.name] = contract
    return contract
```

---

## Phase 2: Core Agents (Week 2-3)

### 2.1 Intent Architect Agent

Create `agents/intent_architect.py`:

```python
@agent_contract(AgentContract(
    name="intent_architect",
    mission="Convert user request into precise execution brief",
    inputs=["user_prompt", "conversation_context"],
    required_output_schema=EXECUTION_BRIEF_SCHEMA,
    forbidden_behaviors=[
        "Do not research",
        "Do not draft final prose",
        "Do not leave success criteria vague"
    ],
    pass_fail_criteria=[
        "Task is clearly framed",
        "Success criteria are actionable",
        "Likely missing dimensions are surfaced"
    ]
))
def run_intent_architect(user_prompt: str, context: list = None) -> ExecutionBrief:
    """Analyze intent and create execution brief."""
    # Prompt template here
    pass
```

### 2.2 Research Lead Agent

Create `agents/research_lead.py`:

```python
@agent_contract(AgentContract(
    name="research_lead",
    mission="Map information terrain and gather relevant material",
    inputs=["execution_brief"],
    required_output_schema=RESEARCH_MAP_SCHEMA,
    forbidden_behaviors=[
        "Do not analyze or draw conclusions",
        "Do not write content",
        "Do not limit to obvious sources"
    ],
    pass_fail_criteria=[
        "Source diversity achieved",
        "Key dimensions identified",
        "Data gaps surfaced"
    ]
))
def run_research_lead(brief: ExecutionBrief) -> ResearchMap:
    """Conduct research based on execution brief."""
    pass
```

### 2.3 Evidence Ledger Agent (CORE)

Create `agents/evidence_ledger.py` - this is the most critical agent:

```python
@agent_contract(AgentContract(
    name="evidence_ledger",
    mission="Separate facts from inference from assumption",
    inputs=["research_map"],
    required_output_schema=CLAIM_LEDGER_SCHEMA,
    forbidden_behaviors=[
        "Do not merge assumptions into verified claims",
        "Do not create broad uncheckable claims",
        "Do not omit confidence or dependency structure",
        "Do not assign VERIFIED without source refs"
    ],
    pass_fail_criteria=[
        "All meaningful claims are classified",
        "High-impact claims are traceable",
        "Assumptions are explicit"
    ]
))
def run_evidence_ledger(research_map: ResearchMap) -> ClaimLedger:
    """Classify all claims as VERIFIED/DERIVED/ASSUMED."""
    pass
```

### 2.4 Analyst/Reasoner Agent

Create `agents/analyst.py`:

```python
@agent_contract(AgentContract(
    name="analyst",
    mission="Convert evidence into actual thinking with second-order analysis",
    inputs=["execution_brief", "claim_ledger"],
    required_output_schema=ANALYTICAL_BACKBONE_SCHEMA,
    forbidden_behaviors=[
        "Do not merely summarize",
        "Do not skip risks and counterarguments",
        "Do not avoid sensitivity analysis"
    ],
    pass_fail_criteria=[
        "Second-order thinking present",
        "Risks and sensitivities identified",
        "Recommendation logic exists if needed"
    ]
))
def run_analyst(brief: ExecutionBrief, claims: ClaimLedger) -> AnalyticalBackbone:
    """Generate analytical backbone with second-order thinking."""
    pass
```

---

## Phase 3: Content Pipeline (Week 3-4)

### 3.1 Output Strategist Agent

Create `agents/output_strategist.py`:

```python
@agent_contract(AgentContract(
    name="output_strategist",
    mission="Design optimal communication structure",
    inputs=["execution_brief", "analytical_backbone"],
    required_output_schema=CONTENT_BLUEPRINT_SCHEMA,
    forbidden_behaviors=[
        "Do not write the content",
        "Do not ignore output type requirements",
        "Do not bury key insights"
    ],
    pass_fail_criteria=[
        "Structure matches output type",
        "Narrative flow is clear",
        "Key takeaways are identifiable"
    ]
))
def run_output_strategist(brief: ExecutionBrief, analysis: AnalyticalBackbone) -> ContentBlueprint:
    """Design content structure."""
    pass
```

### 3.2 Draft Writer Agent

Create `agents/draft_writer.py`:

```python
@agent_contract(AgentContract(
    name="draft_writer",
    mission="Generate first full draft preserving epistemic status",
    inputs=["execution_brief", "claim_ledger", "analytical_backbone", "content_blueprint"],
    required_output_schema={"type": "string"},  # Draft content
    forbidden_behaviors=[
        "Do not invent unsupported claims",
        "Do not upgrade assumptions to facts",
        "Do not remove uncertainty for style"
    ],
    pass_fail_criteria=[
        "Blueprint followed",
        "Claim epistemic status preserved",
        "No new unsupported claims"
    ]
))
def run_draft_writer(brief: ExecutionBrief, claims: ClaimLedger, 
                     analysis: AnalyticalBackbone, blueprint: ContentBlueprint) -> str:
    """Write draft following blueprint."""
    pass
```

---

## Phase 4: Quality Gates (Week 4-5)

### 4.1 Adversarial Reviewer Agent

Create `agents/adversarial_reviewer.py`:

```python
@agent_contract(AgentContract(
    name="adversarial_reviewer",
    mission="Try to break the draft",
    inputs=["draft_v1", "claim_ledger", "execution_brief"],
    required_output_schema=RED_TEAM_REVIEW_SCHEMA,
    forbidden_behaviors=[
        "Do not give generic feedback",
        "Do not ignore fragile assumptions",
        "Do not avoid critical flaws"
    ],
    pass_fail_criteria=[
        "Major flaws identified",
        "Severity differentiated",
        "Specific fixes suggested"
    ]
))
def run_adversarial_reviewer(draft: str, claims: ClaimLedger, 
                            brief: ExecutionBrief) -> RedTeamReview:
    """Attack the draft to find weaknesses."""
    pass
```

### 4.2 Verifier/Citation Auditor Agent

Create `agents/verifier.py`:

```python
@agent_contract(AgentContract(
    name="verifier",
    mission="Ensure support, traceability, and consistency",
    inputs=["draft_v1", "claim_ledger"],
    required_output_schema=VERIFICATION_REPORT_SCHEMA,
    forbidden_behaviors=[
        "Do not miss unsupported claims",
        "Do not ignore numerical inconsistencies",
        "Do not approve overconfident language"
    ],
    pass_fail_criteria=[
        "All claims verified",
        "No contradictions remain",
        "Language appropriately cautious"
    ]
))
def run_verifier(draft: str, claims: ClaimLedger) -> VerificationReport:
    """Verify claims and check consistency."""
    pass
```

### 4.3 Polisher/Formatter Agent

Create `agents/polisher.py`:

```python
@agent_contract(AgentContract(
    name="polisher",
    mission="Improve readability without changing substance",
    inputs=["polished_draft_input"],
    required_output_schema={"type": "string"},
    forbidden_behaviors=[
        "Do not change meaning of claims",
        "Do not remove uncertainty markers",
        "Do not hide unresolved issues"
    ],
    pass_fail_criteria=[
        "Readability improved",
        "Substance preserved",
        "Format matches medium"
    ]
))
def run_polisher(draft: str, output_type: str) -> str:
    """Polish draft for presentation."""
    pass
```

### 4.4 Final Arbiter Agent

Create `agents/final_arbiter.py`:

```python
@agent_contract(AgentContract(
    name="final_arbiter",
    mission="Decide whether output is ready to ship",
    inputs=["all_artifacts", "draft", "red_team_review", "verification_report"],
    required_output_schema=RELEASE_DECISION_SCHEMA,
    forbidden_behaviors=[
        "Do not approve with unresolved critical issues",
        "Do not ignore known gaps",
        "Do not treat polish as substitute for rigor"
    ],
    pass_fail_criteria=[
        "Core question answered",
        "Critical issues resolved",
        "Recommendation present if needed"
    ]
))
def run_final_arbiter(state: MCRSState) -> ReleaseDecision:
    """Make final release decision."""
    pass
```

---

## Phase 5: Orchestration (Week 5-6)

### 5.1 Enhanced Coordinator

Update `coordinator/nodes.py` to handle MCRS flow:

```python
def intent_architect_node(state: MCRSState) -> dict:
    """Phase 1: Create execution brief."""
    brief = run_intent_architect(
        user_prompt=state["user_prompt"],
        context=state.get("conversation_context")
    )
    return {"execution_brief": brief}

def research_lead_node(state: MCRSState) -> dict:
    """Phase 2: Research based on brief."""
    research = run_research_lead(state["execution_brief"])
    return {"research_map": research}

def evidence_ledger_node(state: MCRSState) -> dict:
    """Phase 3: Classify claims."""
    claims = run_evidence_ledger(state["research_map"])
    return {"claim_ledger": claims}

def analyst_node(state: MCRSState) -> dict:
    """Phase 4: Generate analysis."""
    analysis = run_analyst(state["execution_brief"], state["claim_ledger"])
    return {"analytical_backbone": analysis}

def output_strategist_node(state: MCRSState) -> dict:
    """Phase 5: Design structure."""
    blueprint = run_output_strategist(state["execution_brief"], state["analytical_backbone"])
    return {"content_blueprint": blueprint}

def draft_writer_node(state: MCRSState) -> dict:
    """Phase 6: Write draft."""
    draft = run_draft_writer(
        state["execution_brief"],
        state["claim_ledger"],
        state["analytical_backbone"],
        state["content_blueprint"]
    )
    return {"draft_v1": draft, "draft_version": 1}

def adversarial_reviewer_node(state: MCRSState) -> dict:
    """Phase 7: Review critically."""
    review = run_adversarial_reviewer(state["draft_v1"], state["claim_ledger"], 
                                      state["execution_brief"])
    return {"red_team_review": review}

def verifier_node(state: MCRSState) -> dict:
    """Phase 8: Verify claims."""
    verification = run_verifier(state["draft_v1"], state["claim_ledger"])
    return {"verification_report": verification}

def polisher_node(state: MCRSState) -> dict:
    """Phase 9: Polish."""
    polished = run_polisher(state["draft_v1"], state["execution_brief"]["output_type"])
    return {"polished_draft": polished}

def final_arbiter_node(state: MCRSState) -> dict:
    """Phase 10: Release decision."""
    decision = run_final_arbiter(state)
    return {"release_decision": decision}
```

### 5.2 Revision Loop Logic

Add conditional routing for revisions:

```python
def should_revise_after_review(state: MCRSState) -> bool:
    """Check if HIGH severity issues require revision."""
    review = state.get("red_team_review", [])
    return any(issue["severity"] == "HIGH" for issue in review)

def should_revise_after_verification(state: MCRSState) -> bool:
    """Check if unsupported claims require revision."""
    report = state.get("verification_report", [])
    return any(item["status"] == "UNSUPPORTED" for item in report)

def should_retry(state: MCRSState) -> bool:
    """Check if retries remaining."""
    return state.get("retry_count", 0) < MAX_RETRIES
```

### 5.3 Graph Definition

Update `coordinator/graph.py`:

```python
from langgraph.graph import StateGraph

# Build MCRS graph
workflow = StateGraph(MCRSState)

# Add all nodes
workflow.add_node("intent_architect", intent_architect_node)
workflow.add_node("research_lead", research_lead_node)
workflow.add_node("evidence_ledger", evidence_ledger_node)
workflow.add_node("analyst", analyst_node)
workflow.add_node("output_strategist", output_strategist_node)
workflow.add_node("draft_writer", draft_writer_node)
workflow.add_node("adversarial_reviewer", adversarial_reviewer_node)
workflow.add_node("verifier", verifier_node)
workflow.add_node("polisher", polisher_node)
workflow.add_node("final_arbiter", final_arbiter_node)

# Define edges with revision loops
workflow.add_edge("__start__", "intent_architect")
workflow.add_edge("intent_architect", "research_lead")
workflow.add_edge("research_lead", "evidence_ledger")
workflow.add_edge("evidence_ledger", "analyst")
workflow.add_edge("analyst", "output_strategist")
workflow.add_edge("output_strategist", "draft_writer")
workflow.add_edge("draft_writer", "adversarial_reviewer")

# Conditional: revision loop
workflow.add_conditional_edges(
    "adversarial_reviewer",
    should_revise_after_review,
    {
        True: "draft_writer",  # Revise
        False: "verifier"      # Proceed
    }
)

workflow.add_edge("verifier", "final_arbiter")

# Conditional: final decision
workflow.add_conditional_edges(
    "final_arbiter",
    lambda state: state["release_decision"]["status"],
    {
        "READY": "__end__",
        "NOT_READY": "research_lead"  # Or appropriate stage
    }
)
```

---

## Phase 6: Database & Persistence (Week 6-7)

### 6.1 Enhanced Models

Update `db/models.py`:

```python
from sqlalchemy import Column, String, Integer, JSON, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

class Artifact(Base):
    __tablename__ = "artifacts"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    
    # MCRS Artifacts (JSON)
    execution_brief = Column(JSON)
    research_map = Column(JSON)
    claim_ledger = Column(JSON)
    analytical_backbone = Column(JSON)
    content_blueprint = Column(JSON)
    draft_v1 = Column(Text)
    red_team_review = Column(JSON)
    verification_report = Column(JSON)
    polished_draft = Column(Text)
    release_decision = Column(JSON)
    
    # Metadata
    draft_version = Column(Integer, default=1)
    retry_count = Column(Integer, default=0)
    status = Column(String)  # in_progress, review, verified, released, failed
    
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
```

---

## Implementation Priority Matrix

| Priority | Agent | Impact | Difficulty | Reason |
|----------|-------|--------|------------|--------|
| P0 | Evidence Ledger | Prevents fake confidence | Medium | Core epistemic layer |
| P0 | Claim tracking in state | Enables traceability | Low | Foundation |
| P1 | Intent Architect | Prevents wrong question | Medium | High impact |
| P1 | Adversarial Reviewer | Prevents fragile output | Medium | Quality gate |
| P1 | Final Arbiter | Prevents premature release | Low | Decision gate |
| P2 | Research Lead | Prevents shallow research | Medium | Quality |
| P2 | Analyst | Prevents surface analysis | Medium | Quality |
| P2 | Verifier | Prevents unsupported claims | Medium | Quality gate |
| P3 | Output Strategist | Prevents bad structure | Low | Usability |
| P3 | Polisher | Prevents ugly output | Low | Usability |

---

## Key Decisions Required

1. **Parallel vs Sequential Research**: Should Research Lead run queries in parallel?
2. **Revision Depth Limit**: How many revision cycles before giving up?
3. **Simplified Mode**: Should MVP skip some agents per the spec's 6-agent suggestion?
4. **Agent Model Selection**: Which model for each agent? ( cheaper for mechanical, expensive for reasoning)
5. **Persistence Strategy**: Full artifact storage vs summarized?

---

## Success Metrics

- [ ] All 10 agents implemented with contracts
- [ ] Claim classification accuracy > 90% (VERIFIED/DERIVED/ASSUMED)
- [ ] Revision loop successfully triggers on HIGH severity issues
- [ ] Final Arbiter correctly rejects weak outputs
- [ ] Retry limits prevent infinite loops (max 3 retries per stage)
- [ ] Traceability: any claim in final output → source in ledger

---

## Files to Create/Modify

### New Files
- `coordinator/artifacts.py` - All schema definitions
- `coordinator/contracts.py` - Agent contract system
- `agents/intent_architect.py`
- `agents/research_lead.py`
- `agents/evidence_ledger.py` ⭐
- `agents/analyst.py`
- `agents/output_strategist.py`
- `agents/draft_writer.py`
- `agents/adversarial_reviewer.py`
- `agents/verifier.py`
- `agents/polisher.py`
- `agents/final_arbiter.py`

### Modified Files
- `coordinator/state.py` - Add MCRSState
- `coordinator/nodes.py` - Replace with MCRS nodes
- `coordinator/graph.py` - Update graph definition
- `db/models.py` - Add MCRS fields

---

*Generated from MCRS_pipeline_spec_detailed.md analysis*

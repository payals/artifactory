# Multi-Agent Content Reasoning System (MCRS)
## Complete Architecture Spec for a General-Purpose Content Reasoning Pipeline

## Overview

This document specifies a multi-agent content generation pipeline designed to produce outputs that are more rigorous, more useful, and more trustworthy than a strong single-shot LLM response.

The goal is not merely to generate polished content. The goal is to build a **content reasoning system** that can reliably produce high-quality blogs, reports, reviews, analyses, presentations, decision memos, technical writeups, and similar outputs by decomposing the work into specialized agents with narrow responsibilities and explicit quality gates.

This system is intended for **complex, high-value content tasks** where:
- evidence matters
- structure matters
- completeness matters
- second-order reasoning matters
- unsupported claims are costly
- revision and adversarial critique improve quality

This system is not optimized for minimal latency or casual one-off writing. It is optimized for **quality, traceability, and decision usefulness**.

---

## Why This Exists

A strong single-model response can already do a lot:
- produce polished prose
- synthesize broad context
- draft plausible analysis
- generate presentable outputs quickly

However, single-shot systems often fail in recurring ways:
- they answer the wrong question elegantly
- they mix facts with assumptions
- they stop at surface-level completeness
- they produce persuasive but fragile reasoning
- they bury uncertainty
- they sound better than they are

A multi-agent system is useful only if it solves those failure modes cleanly.

The key is not “more agents.” The key is:
- **sharp role separation**
- **structured intermediate artifacts**
- **blocking quality gates**
- **revision loops driven by concrete critiques**

Without those, multi-agent systems often become verbose, redundant, or self-congratulatory.

---

## Core Design Principles

### 1. Separation of Concerns
Each agent should own a specific failure mode.

Examples:
- one agent prevents answering the wrong question
- one agent prevents shallow research
- one agent prevents unsupported claims
- one agent prevents weak reasoning
- one agent prevents poor structure
- one agent tries to break the result
- one agent decides whether the output is ready

This is the core principle behind the architecture.

### 2. Artifact-Driven Workflow
Agents should communicate via structured artifacts, not vague prose.

Artifacts make the system inspectable and debuggable. They also prevent downstream stages from silently inventing work that was never justified upstream.

### 3. No Single Agent Can Both Create and Approve
The agent that drafts content must not also be the one that verifies or approves it.

This separation is critical. Otherwise the pipeline collapses back into a single opaque generation step.

### 4. Explicit Epistemology
Every meaningful claim should be tagged as one of:
- **VERIFIED**: source-backed fact
- **DERIVED**: inference from verified facts
- **ASSUMED**: explicit guess, estimate, scenario input, or planning placeholder

This prevents the system from laundering assumptions into facts.

### 5. Blocking Gates
Downstream stages should be allowed to fail the work.

Examples:
- unsupported high-impact claims block finalization
- missing critical dimensions block completion
- absence of recommendation blocks decision-oriented outputs
- unaddressed reviewer issues trigger mandatory revision

### 6. Revision Loops
Improvement should happen through explicit critique and targeted revision, not vague “make it better” prompts.

### 7. Coordinator as Workflow Judge, Not Main Thinker
The coordinator should not be the main intelligence in the system. It should:
- route artifacts
- enforce stage order
- detect failures
- trigger retries
- prevent premature release

The coordinator is a workflow controller, not the author.

---

## Quality Goals

If implemented correctly, this system should outperform single-shot generation on:

- **depth**
- **trustworthiness**
- **decision usefulness**
- **clarity under scrutiny**
- **explicit handling of uncertainty**
- **traceability from claims to evidence**
- **completeness for real-world use**

It may not outperform on:
- speed
- simple requests
- casual writing
- lightweight brainstorming
- highly intuitive creative work where heavy process adds friction

So the true target is:

> Build a system that consistently beats strong single-model responses on complex, high-value content tasks.

---

## High-Level Pipeline

1. Intent Architect  
2. Research Lead  
3. Evidence Ledger  
4. Analyst / Reasoner  
5. Output Strategist  
6. Draft Writer  
7. Adversarial Reviewer  
8. Verifier / Citation Auditor  
9. Polisher / Formatter  
10. Final Arbiter  

Each agent is described below in detail.

---

# Agent Architecture

## 1. Intent Architect

### Purpose
Translate the user request into a precise execution brief.

### Why This Agent Exists
Many weak outputs happen because the system writes an answer to the literal prompt rather than the user’s actual goal.

A user may ask:
- “market opportunity” but really need a go/no-go analysis
- “write a blog” but actually need thought leadership for a technical audience
- “make slides” but actually need persuasion for non-experts
- “review this design” but really need failure modes and risk prioritization

The Intent Architect exists to define what the task actually is.

### Inputs
- raw user prompt
- optional conversation context
- optional output constraints

### Outputs
#### Execution Brief
```json
{
  "user_goal": "",
  "output_type": "",
  "audience": "",
  "tone": "",
  "must_answer_questions": [],
  "constraints": [],
  "success_criteria": [],
  "likely_missing_dimensions": [],
  "decision_required": true,
  "rigor_level": "LOW | MEDIUM | HIGH",
  "persuasion_level": "LOW | MEDIUM | HIGH",
  "open_questions_to_resolve_via_research": []
}
```

### Responsibilities
- infer user intent
- determine output type
- determine audience
- determine expected rigor and persuasion level
- identify must-cover dimensions
- define what success looks like
- identify likely missing dimensions before research begins

### Examples of Missing Dimensions It Should Infer
If the user asks for:
- **market research** → demographics, demand, competition, cost, regulation, risk, recommendation
- **technical review** → architecture, tradeoffs, bottlenecks, risks, rollout concerns
- **slides** → narrative arc, audience sophistication, aha moments, objections to address
- **blog post** → audience, thesis, novelty, counterarguments, readability

### Failure Conditions
- success criteria are vague
- output type is misidentified
- important dimensions omitted
- task remains underspecified in a way that research cannot fix

### What It Prevents
- answering the wrong question
- building the wrong output shape
- technically correct but useless deliverables

---

## 2. Research Lead

### Purpose
Map the information terrain and gather relevant material.

### Why This Agent Exists
Research often fails not because the system cannot find facts, but because it locks in too early and fails to identify the real dimensions of the topic.

This agent’s job is not to argue or write. Its job is to gather enough breadth to know what matters.

### Inputs
- Execution Brief

### Outputs
#### Research Map
```json
{
  "sources": [
    {
      "source_id": "",
      "title": "",
      "type": "official | news | research | reference | internal | other",
      "reliability": "HIGH | MEDIUM | LOW",
      "notes": ""
    }
  ],
  "facts": [],
  "key_dimensions": [],
  "competing_views": [],
  "data_gaps": [],
  "followup_questions": []
}
```

### Responsibilities
- identify relevant sources
- extract factual material
- identify critical data domains
- note conflicting perspectives if applicable
- identify gaps and unknowns
- avoid interpretation beyond what is needed to structure later work

### Guidance
This agent should think:
- what would a serious person expect to see in this output?
- which dimensions will matter to the final decision?
- what is likely missing if I only follow the obvious path?
- where are the likely blind spots?

### Failure Conditions
- obvious source categories missing
- narrow or shallow source coverage
- premature analysis masquerading as research
- missing key data domains

### What It Prevents
- shallow research
- missing obvious dimensions
- overfitting to early information

---

## 3. Evidence Ledger

### Purpose
Separate facts from inference from assumption.

### Why This Agent Exists
This is one of the most important agents in the system.

Weak content systems constantly blur:
- what is true
- what is inferred
- what is guessed

The Evidence Ledger makes the epistemic status of each claim explicit.

### Inputs
- Research Map

### Outputs
#### Claim Ledger
```json
[
  {
    "claim_id": "C001",
    "claim_text": "",
    "classification": "VERIFIED | DERIVED | ASSUMED",
    "source_refs": [],
    "confidence": 0.0,
    "importance": "HIGH | MEDIUM | LOW",
    "dependent_on": [],
    "notes": ""
  }
]
```

### Responsibilities
- create atomic claims
- classify each claim
- attach evidence or dependencies
- mark confidence
- identify high-impact assumptions
- keep traceability for downstream validation

### Definitions
- **VERIFIED**: directly grounded in evidence or source material
- **DERIVED**: reasoned conclusion from one or more verified claims
- **ASSUMED**: scenario input, estimate, forecast input, placeholder, or explicit guess

### Example
```json
[
  {
    "claim_id": "C001",
    "claim_text": "Town population is 3,296.",
    "classification": "VERIFIED",
    "source_refs": ["SRC_01"],
    "confidence": 0.98,
    "importance": "HIGH",
    "dependent_on": []
  },
  {
    "claim_id": "C002",
    "claim_text": "An aging population may prefer approachable menu design and adjustable spice levels.",
    "classification": "DERIVED",
    "source_refs": ["SRC_01"],
    "confidence": 0.72,
    "importance": "MEDIUM",
    "dependent_on": ["C001"]
  },
  {
    "claim_id": "C003",
    "claim_text": "30 percent of local households could become active customers.",
    "classification": "ASSUMED",
    "source_refs": [],
    "confidence": 0.35,
    "importance": "HIGH",
    "dependent_on": []
  }
]
```

### Failure Conditions
- unlabeled claims
- overly broad claims that cannot be checked
- assumptions presented as verified
- no dependency structure

### What It Prevents
- fake confidence
- muddled reasoning
- unsupported persuasive writing

---

## 4. Analyst / Reasoner

### Purpose
Convert evidence into actual thinking.

### Why This Agent Exists
A lot of systems do “research + writing” and call that analysis. That is not enough.

This agent is responsible for:
- identifying the main drivers
- explaining causal relationships
- surfacing tradeoffs
- doing sensitivity and failure-mode thinking
- generating recommendation logic

### Inputs
- Execution Brief
- Claim Ledger

### Outputs
#### Analytical Backbone
```json
{
  "key_findings": [],
  "primary_drivers": [],
  "implications": [],
  "risks": [],
  "sensitivities": [],
  "counterarguments": [],
  "recommendation_logic": [],
  "open_unknowns": []
}
```

### Responsibilities
- produce first-order analysis
- add second-order analysis
- identify what changes the result
- identify what would invalidate the result
- identify alternative interpretations
- build reasoning that the writer can later express clearly

### Required Second-Order Thinking
The analyst must go beyond summary and include:
- implications
- edge cases
- risks
- fragility
- sensitivity analysis
- what happens if assumptions change
- what critics or experts might object to

### Example Questions This Agent Should Ask
- what are the primary drivers of the outcome?
- where is the conclusion most fragile?
- what assumptions dominate the result?
- what would make the recommendation change?
- what important uncertainty remains unresolved?

### Failure Conditions
- output is merely descriptive
- risks are missing
- no counterarguments or sensitivities
- recommendation logic is absent when needed

### What It Prevents
- research dump masquerading as intelligence
- shallow conclusions
- brittle recommendations

---

## 5. Output Strategist

### Purpose
Design the best communication structure for the audience and output type.

### Why This Agent Exists
A lot of high-quality reasoning gets buried inside poor presentation.

This agent decides how the content should be shaped so that it is:
- useful
- persuasive when needed
- easy to navigate
- aligned to audience needs

### Inputs
- Execution Brief
- Analytical Backbone

### Outputs
#### Content Blueprint
```json
{
  "structure": [],
  "section_purposes": [],
  "narrative_flow": "",
  "visual_elements": [],
  "key_takeaways": [],
  "audience_guidance": []
}
```

### Responsibilities
- choose the structure
- define section order
- determine narrative arc
- recommend tables, charts, diagrams, or emphasis blocks
- ensure “aha” moments surface
- align format to audience sophistication

### Examples
A report might need:
- executive summary
- key findings
- evidence sections
- model or framework
- risks
- recommendation
- next validation steps

A slide deck might need:
- hook
- problem
- insight progression
- contrast cases
- recommendation
- close

A blog might need:
- thesis
- narrative setup
- argument sequence
- examples
- counterarguments
- memorable close

### Failure Conditions
- structure does not match output type
- no clear reader journey
- insights buried in wrong order
- no visual strategy when visuals would help

### What It Prevents
- smart content with bad delivery
- unreadable dense output
- weak storytelling

---

## 6. Draft Writer

### Purpose
Generate the first full draft.

### Why This Agent Exists
Writing should be a downstream synthesis step, not where all hidden reasoning happens.

The writer receives enough structured upstream material that it should be assembling and expressing, not inventing the core logic from scratch.

### Inputs
- Execution Brief
- Claim Ledger
- Analytical Backbone
- Content Blueprint

### Outputs
- Draft v1 (markdown or other required format)

### Responsibilities
- write clearly
- follow the blueprint
- preserve epistemic status of claims
- ensure coherence across sections
- integrate evidence, analysis, and recommendation cleanly

### Strict Constraints
- must not invent unsupported claims
- must not silently upgrade assumptions into facts
- should not introduce new high-impact analysis without routing it back into the evidence/analysis layer if your implementation allows that
- must preserve uncertainty where uncertainty exists

### Failure Conditions
- new unsupported claims introduced
- structure deviates materially from blueprint
- reasoning is distorted
- uncertainty is erased for style

### What It Prevents
- magical unsupported polish
- style-driven distortion
- writer improvisation replacing analysis

---

## 7. Adversarial Reviewer

### Purpose
Try to break the draft.

### Why This Agent Exists
A polished draft can still be weak. This agent should act like a skeptical expert or critical stakeholder.

Its role is not to lightly edit. Its role is to attack the weak points:
- what is fragile?
- what is misleading?
- what is missing?
- what would an expert challenge?

### Inputs
- Draft v1
- Claim Ledger
- Execution Brief

### Outputs
#### Red Team Review
```json
[
  {
    "issue_id": "R001",
    "severity": "HIGH | MEDIUM | LOW",
    "section": "",
    "problem_type": "",
    "explanation": "",
    "suggested_fix": ""
  }
]
```

### Recommended Problem Types
- missing_dimension
- unsupported_claim
- shallow_analysis
- overconfidence
- weak_recommendation
- audience_mismatch
- poor_structure
- misleading_framing
- unaddressed_risk
- unexamined_assumption

### Responsibilities
- identify the weakest claims
- identify shallow sections
- identify omissions that matter
- identify misleading framing
- identify places where an expert would push back
- force revision where needed

### Temperament
This agent should be rigorous and uncompromising. It should not be “helpful” in the vague sense. It should be sharp.

### Failure Conditions
- feedback is generic
- misses obvious critical flaws
- fails to challenge fragile assumptions
- does not distinguish severity

### What It Prevents
- polished nonsense
- easy-to-miss weaknesses
- outputs that sound good but collapse under scrutiny

---

## 8. Verifier / Citation Auditor

### Purpose
Ensure support, traceability, and consistency.

### Why This Agent Exists
Even strong drafts can contain:
- unsupported claims
- mismatched citations
- inconsistent numbers
- overconfident language
- stale or weakly supported assertions

This agent is a grounding and consistency check.

### Inputs
- latest draft
- Claim Ledger
- source material if available in implementation

### Outputs
#### Verification Report
```json
[
  {
    "claim_id": "C001",
    "status": "SUPPORTED | WEAK | UNSUPPORTED | INCONSISTENT",
    "notes": "",
    "required_action": ""
  }
]
```

### Responsibilities
- check whether claims are supported
- verify citation linkage if citations exist
- check math and internal consistency
- identify contradictions
- downgrade overconfident language when needed

### Typical Required Actions
- add_source
- reclassify_claim
- downgrade_language
- remove_claim
- fix_number
- resolve_contradiction

### Example Language Downgrades
- “is” → “appears to be”
- “will” → “may”
- “proves” → “suggests”
- “clearly” → remove unless truly justified

### Failure Conditions
- unsupported claims slip through
- citation mismatches missed
- internal numerical inconsistency not caught
- no distinction between weak and unsupported support

### What It Prevents
- fake grounding
- subtle numerical and factual errors
- unjustified certainty

---

## 9. Polisher / Formatter

### Purpose
Improve readability, scanability, and presentation without changing substance.

### Why This Agent Exists
A technically strong output can still fail if it is unpleasant or hard to consume.

This agent makes the content readable and presentable.

### Inputs
- approved draft

### Outputs
- polished final draft

### Responsibilities
- improve clarity
- improve flow and transitions
- improve section headers
- improve table and chart labeling
- improve skimmability
- tighten repetition
- adapt formatting to medium (markdown, pdf, slides, etc.)

### Strict Constraint
This agent should not change the meaning of claims, conclusions, or uncertainty.

### Failure Conditions
- substance altered
- nuance lost
- clarity worsened
- polish hides unresolved quality issues

### What It Prevents
- ugly dense output
- buried insights
- poor usability

---

## 10. Final Arbiter

### Purpose
Decide whether the output is ready to ship.

### Why This Agent Exists
Without a final release decision, pipelines tend to ship “good enough” outputs too early.

This agent is the final quality gate.

### Inputs
- all artifacts
- latest draft
- reviewer output
- verifier output

### Outputs
#### Release Decision
```json
{
  "status": "READY | NOT_READY",
  "confidence": 0.0,
  "remaining_risks": [],
  "known_gaps": [],
  "notes": ""
}
```

### Responsibilities
- determine readiness
- ensure core question is answered
- ensure critical issues are resolved
- ensure recommendation exists if needed
- ensure known gaps are explicitly surfaced
- prevent release when the work is still materially weak

### Release Criteria
Do not ship unless all are true:
- the user’s core question is answered
- evidence and assumptions are separated
- critical unsupported claims are resolved or removed
- major risks or counterarguments are addressed
- recommendation is present if the task requires one
- known gaps are disclosed
- structure matches output type
- output is usable by the intended audience

### Failure Conditions
- approves despite unresolved critical issues
- ignores task-specific completeness gaps
- treats polish as a substitute for rigor

### What It Prevents
- premature release
- silent quality regressions
- weak deliverables reaching the user

---

# Artifact Schemas

## Execution Brief
```json
{
  "user_goal": "",
  "output_type": "",
  "audience": "",
  "tone": "",
  "must_answer_questions": [],
  "constraints": [],
  "success_criteria": [],
  "likely_missing_dimensions": [],
  "decision_required": true,
  "rigor_level": "LOW | MEDIUM | HIGH",
  "persuasion_level": "LOW | MEDIUM | HIGH",
  "open_questions_to_resolve_via_research": []
}
```

## Research Map
```json
{
  "sources": [
    {
      "source_id": "",
      "title": "",
      "type": "official | news | research | reference | internal | other",
      "reliability": "HIGH | MEDIUM | LOW",
      "notes": ""
    }
  ],
  "facts": [],
  "key_dimensions": [],
  "competing_views": [],
  "data_gaps": [],
  "followup_questions": []
}
```

## Claim Ledger
```json
[
  {
    "claim_id": "",
    "claim_text": "",
    "classification": "VERIFIED | DERIVED | ASSUMED",
    "source_refs": [],
    "confidence": 0.0,
    "importance": "HIGH | MEDIUM | LOW",
    "dependent_on": [],
    "notes": ""
  }
]
```

## Analytical Backbone
```json
{
  "key_findings": [],
  "primary_drivers": [],
  "implications": [],
  "risks": [],
  "sensitivities": [],
  "counterarguments": [],
  "recommendation_logic": [],
  "open_unknowns": []
}
```

## Content Blueprint
```json
{
  "structure": [],
  "section_purposes": [],
  "narrative_flow": "",
  "visual_elements": [],
  "key_takeaways": [],
  "audience_guidance": []
}
```

## Red Team Review
```json
[
  {
    "issue_id": "",
    "severity": "HIGH | MEDIUM | LOW",
    "section": "",
    "problem_type": "",
    "explanation": "",
    "suggested_fix": ""
  }
]
```

## Verification Report
```json
[
  {
    "claim_id": "",
    "status": "SUPPORTED | WEAK | UNSUPPORTED | INCONSISTENT",
    "notes": "",
    "required_action": ""
  }
]
```

## Release Decision
```json
{
  "status": "READY | NOT_READY",
  "confidence": 0.0,
  "remaining_risks": [],
  "known_gaps": [],
  "notes": ""
}
```

---

# Revision Loops

## Required Loops

### 1. Reviewer → Writer
If the Adversarial Reviewer finds significant issues, the Draft Writer must revise the draft in response to specific findings.

### 2. Verifier → Writer
If the Verifier finds unsupported claims, contradictions, or weak support, the Draft Writer must correct, downgrade, remove, or explicitly qualify them.

### 3. Arbiter → Coordinator
If the Final Arbiter decides the output is NOT_READY, the coordinator must send the draft back through the appropriate corrective path rather than trying to polish it into acceptability.

---

# Coordinator Responsibilities

The coordinator should not act like a giant catch-all intelligence layer. Its role is orchestration.

## Coordinator Responsibilities
- route artifacts between agents
- enforce stage order
- ensure required artifacts exist before downstream execution
- detect blocking failures
- trigger revision loops
- prevent stages from being skipped
- stop polish from masking unresolved upstream weakness
- terminate only when release criteria are met or the system gives an honest incomplete result

## Coordinator Must Not
- silently rewrite outputs in lieu of proper agent execution
- collapse all thinking back into a single step
- bypass verification because the draft “looks good”
- treat lack of evidence as permission to improvise

---

# Failure Mode Mapping

Each agent should own one or more distinct failure modes.

| Layer | Agent | Failure Mode Prevented |
|---|---|---|
| Intent | Intent Architect | Answering the wrong question |
| Research | Research Lead | Shallow or narrow coverage |
| Grounding | Evidence Ledger | Facts mixed with assumptions |
| Reasoning | Analyst | Surface-level analysis |
| Usefulness | Output Strategist | Technically correct but unusable output |
| Writing | Draft Writer | Unclear or incoherent draft |
| Adversarial | Reviewer | Fragile reasoning slipping through |
| Verification | Verifier | Unsupported or inconsistent claims |
| Presentation | Polisher | Poor readability and structure |
| Completion | Final Arbiter | Premature release |

---

# Minimal Viable Version

If implementing all ten agents is too heavy initially, compress into six logical components while preserving separation of concerns:

1. Intent Architect  
2. Research Lead  
3. Evidence Ledger  
4. Analyst  
5. Writer  
6. Reviewer-Arbiter  

Even in the compact version, do not collapse these separations:
- research vs analysis
- analysis vs writing
- writing vs verification/review
- production vs approval

If you collapse those, quality drops quickly.

---

# Suggested Pass / Fail Logic

## Intent Architect
Fail if:
- output type unclear
- success criteria too vague
- must-cover dimensions missing

## Research Lead
Fail if:
- key data domains missing
- no meaningful source diversity
- obvious gaps unflagged

## Evidence Ledger
Fail if:
- claims unlabeled
- important assumptions hidden
- evidence links absent

## Analyst
Fail if:
- only summary, no reasoning
- no risks, counterarguments, or sensitivities
- no recommendation logic when decision required

## Output Strategist
Fail if:
- structure misaligned to output type
- narrative flow weak
- key insights buried

## Draft Writer
Fail if:
- unsupported claims introduced
- blueprint ignored
- uncertainty removed

## Adversarial Reviewer
Fail if:
- feedback generic
- major flaws unflagged
- severity not differentiated

## Verifier
Fail if:
- unsupported claims remain
- contradictions remain
- numerical inconsistencies remain

## Polisher
Fail if:
- meaning altered
- readability not improved
- polish used to mask weakness

## Final Arbiter
Fail if:
- approves work with unresolved critical weaknesses
- known gaps omitted
- output not decision-usable when required

---

# Recommended Implementation Pattern

## Agent Contracts
Each agent should have:
1. a narrow mission
2. fixed input schema
3. fixed output schema
4. explicit forbidden behaviors
5. pass/fail criteria

This is what turns agents from vague personalities into reliable system components.

## Example Contract Template
```json
{
  "agent_name": "",
  "mission": "",
  "inputs": [],
  "required_output_schema": {},
  "forbidden_behaviors": [],
  "pass_fail_criteria": []
}
```

---

# Example Agent Contract Definitions

## Intent Architect Contract
```json
{
  "agent_name": "Intent Architect",
  "mission": "Convert the user request into a precise execution brief with clear success criteria and inferred missing dimensions.",
  "inputs": ["user_prompt", "conversation_context"],
  "required_output_schema": {
    "user_goal": "string",
    "output_type": "string",
    "audience": "string",
    "tone": "string",
    "must_answer_questions": ["string"],
    "constraints": ["string"],
    "success_criteria": ["string"],
    "likely_missing_dimensions": ["string"],
    "decision_required": "boolean"
  },
  "forbidden_behaviors": [
    "Do not research",
    "Do not draft final prose",
    "Do not leave success criteria vague"
  ],
  "pass_fail_criteria": [
    "Task is clearly framed",
    "Success criteria are actionable",
    "Likely missing dimensions are surfaced"
  ]
}
```

## Evidence Ledger Contract
```json
{
  "agent_name": "Evidence Ledger",
  "mission": "Convert research findings into atomic claims with explicit epistemic classification and traceability.",
  "inputs": ["research_map"],
  "required_output_schema": {
    "claims": [
      {
        "claim_id": "string",
        "claim_text": "string",
        "classification": "VERIFIED | DERIVED | ASSUMED",
        "source_refs": ["string"],
        "confidence": "number",
        "importance": "HIGH | MEDIUM | LOW",
        "dependent_on": ["string"]
      }
    ]
  },
  "forbidden_behaviors": [
    "Do not merge assumptions into verified claims",
    "Do not create broad uncheckable claims",
    "Do not omit confidence or dependency structure"
  ],
  "pass_fail_criteria": [
    "All meaningful claims are classified",
    "High-impact claims are traceable",
    "Assumptions are explicit"
  ]
}
```

---

# Design Notes for the Coding Agent

## 1. Use Structured JSON Between Agents
Freeform text between stages will make the system harder to validate and debug.

## 2. Preserve Claim IDs Across the Pipeline
If a claim appears in:
- the ledger
- the draft
- the review
- the verification report

it should be traceable via consistent IDs if possible.

## 3. Add Explicit Severity Levels
Both reviewer and verifier outputs should support severity so the coordinator knows what blocks release.

## 4. Support Revisions, Not Just Linear Execution
The graph should allow:
- writer revision after review
- writer revision after verification
- arbiter rejections returning to appropriate stage

## 5. Log Failure Reasons
Persist why a stage failed. That is valuable for improving prompts and orchestration logic later.

## 6. Don’t Reward Verbosity
Longer outputs are not automatically better. Optimize for:
- signal
- usefulness
- clarity
- traceability

## 7. Keep Writing Separate From Thinking
Do not let the Draft Writer become the hidden analysis layer.

## 8. Allow Honest Incompleteness
If the system lacks evidence, it should explicitly say so rather than hallucinating completeness.

---

# Release Standard

The system should only mark output READY if it is:
- aligned to the user’s real goal
- substantively researched
- epistemically clean
- analytically useful
- explicitly aware of uncertainty
- appropriately structured for the output type
- checked by both adversarial review and verification
- readable and usable

---

# Strategic Positioning of This System

This is not just a “content generator.”

It is a **content reasoning engine**.

That distinction matters.

A content generator optimizes for plausible output.
A content reasoning engine optimizes for:
- correctness
- decision value
- structured thought
- explicit uncertainty
- resilience under critique

That is the standard this architecture is designed to meet.

---

# Final Goal

Build a system that does not merely produce convincing content.

Build a system that can reliably produce content that survives scrutiny and is more useful than a strong single-model response on complex, high-value tasks.

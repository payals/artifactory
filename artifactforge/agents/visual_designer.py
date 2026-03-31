"""Visual Designer Agent - Analyzes documents and suggests visual elements."""

import json
from typing import Any, Optional

from artifactforge.agents.llm_gateway import extract_json
from artifactforge.coordinator import artifacts as schemas
from artifactforge.coordinator.contracts import VISUAL_DESIGNER_CONTRACT, agent_contract


VISUAL_DESIGNER_SYSTEM = """You are a Visual Designer - an expert at identifying opportunities for visuals in documents.

Your job is to analyze a document and suggest appropriate visualizations.

## Visual Types by Complexity

### SIMPLE (Mermaid - no external deps)
- flowchart: Process flows, decision trees
- sequence_diagram: Interactions between actors
- org_chart: Hierarchical structures
- timeline: Chronological events
- gantt_chart: Project schedules
- concept_diagram: Abstract relationships

### COMPLEX (Python/matplotlib)
- bar_chart: Comparisons between categories
- line_chart: Trends over time
- pie_chart: Proportions/percentages
- scatter_plot: Correlations
- heatmap: Density/intensity
- statistical_chart: Complex data viz

## Decision Criteria
1. Does the section contain data that could be visualized?
2. Would a visual make it easier to understand?
3. Is the visual type appropriate for the data?
4. Where in the section should it be placed?

## Output Format
Return a JSON array of visual specs, each with:
- visual_id: Unique ID (V001, V002, etc.)
- section_anchor: Section header to anchor to
- visual_type: One of the types above
- title: Clear title for the visual
- description: What this visual shows
- data_spec: The actual data extracted from the document. For COMPLEX types, include:
  - "labels": array of category/axis labels from the document (e.g. ["Local Residents", "Tourists", "Seasonal Workers"])
  - "data": object with "values" (for bar/pie), "x" and "y" (for line/scatter) — use real numbers from the document
  - "x_label": axis label
  - "y_label": axis label
  IMPORTANT: Extract real data points, numbers, and categories from the document. NEVER use placeholder values like A/B/C or 10/20/30. If the document contains specific figures (populations, costs, percentages), use those exact values.
- complexity: "SIMPLE" or "COMPLEX"
- mermaid_code: If SIMPLE, provide complete Mermaid code
- placeholder_position: Where in the section to insert

If no visuals are needed, return an empty array []."""


@agent_contract(VISUAL_DESIGNER_CONTRACT)
def run_visual_designer(
    draft: str,
    content_blueprint: Optional[dict] = None,
    output_type: str = "report",
) -> list[schemas.VisualSpec]:
    """Analyze document and suggest visual elements.

    Args:
        draft: Current document draft
        content_blueprint: The content structure
        output_type: Type of output (report, blog, whitepaper, etc.)

    Returns:
        List of VisualSpec objects
    """
    prompt = _build_visual_prompt(draft, content_blueprint, output_type)
    result = _call_llm(system=VISUAL_DESIGNER_SYSTEM, prompt=prompt)

    try:
        parsed = json.loads(extract_json(result))
        if isinstance(parsed, list):
            return [_normalize_spec(v, i) for i, v in enumerate(parsed)]
        return []
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


def _build_visual_prompt(
    draft: str, content_blueprint: Optional[dict], output_type: str
) -> str:
    blueprint_text = ""
    if content_blueprint:
        structure = content_blueprint.get("structure", [])
        blueprint_text = f"\n## Content Structure\n{json.dumps(structure)}"

    return f"""## Document Draft
{draft}

## Output Type
{output_type}
{blueprint_text}

Analyze this document and suggest appropriate visualizations. Return a JSON array of visual specifications. If no visuals are helpful, return []."""


def _normalize_spec(spec: dict, index: int) -> schemas.VisualSpec:
    visual_id = spec.get("visual_id", f"V{index + 1:03d}")

    visual_type = spec.get("visual_type", "bar_chart")
    simple_types = {
        "flowchart",
        "sequence_diagram",
        "org_chart",
        "timeline",
        "gantt_chart",
        "concept_diagram",
    }
    complexity = "SIMPLE" if visual_type in simple_types else "COMPLEX"

    return {
        "visual_id": visual_id,
        "section_anchor": spec.get("section_anchor", ""),
        "visual_type": visual_type,
        "title": spec.get("title", "Visual"),
        "description": spec.get("description", ""),
        "data_spec": spec.get("data_spec", {}),
        "complexity": complexity,
        "mermaid_code": spec.get("mermaid_code") if complexity == "SIMPLE" else None,
        "placeholder_position": spec.get(
            "placeholder_position", "after_first_paragraph"
        ),
    }


def _call_llm(system: str, prompt: str) -> str:
    from artifactforge.agents.llm_gateway import call_llm_sync

    return call_llm_sync(
        system_prompt=system, user_prompt=prompt, agent_name="visual_designer"
    )


__all__ = ["run_visual_designer", "VISUAL_DESIGNER_CONTRACT"]

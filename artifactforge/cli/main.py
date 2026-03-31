"""CLI entry point for artifactory."""

import asyncio
import html
import logging
import re
import shutil
import subprocess
from datetime import date
from importlib import import_module
from pathlib import Path
from typing import Any, Optional, cast

from artifactforge.config import get_settings
from artifactforge.coordinator import app

logger = logging.getLogger(__name__)
settings = get_settings()

OUTPUTS_DIR = Path(__file__).parent.parent.parent / "outputs"


def _ends_with_complete_markdown_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False

    if stripped.endswith((".", "!", "?", ":", ")")):
        return True

    if stripped.startswith(("#", "-", "*", "+", ">")):
        return True

    return bool(re.match(r"^\d+[.)]\s", stripped))


def select_output_content(result: dict) -> str | None:
    if final_with_visuals := result.get("final_with_visuals"):
        return final_with_visuals

    polished = result.get("polished_draft")
    draft = result.get("draft_v1")

    if not polished:
        return draft

    if not draft:
        return polished

    polish_lines = polished.strip().split("\n")
    draft_lines = draft.strip().split("\n")

    if len(polish_lines) < len(draft_lines) * 0.5:
        return draft

    last_line = polish_lines[-1].strip() if polish_lines else ""
    if last_line and not _ends_with_complete_markdown_line(last_line):
        return draft

    return polished


def slugify(text: str) -> str:
    """Convert text to a URL-safe slug."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)  # Remove special chars
    text = re.sub(r"[\s_]+", "-", text)  # Replace spaces/underscores with hyphens
    text = re.sub(r"-+", "-", text)  # Replace multiple hyphens
    return text.strip("-")


def _render_inline_markdown(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"__(.+?)__", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"`(.+?)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*(.+?)\*", r"<em>\1</em>", escaped)
    escaped = re.sub(r"_(.+?)_", r"<em>\1</em>", escaped)
    return escaped


def _markdown_to_html(content: str) -> str:
    blocks = content.strip().split("\n\n")
    rendered: list[str] = []

    for block in blocks:
        lines = [line.rstrip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue

        # Skip HTML comments (<!-- VISUAL: ... --> anchors)
        if all(re.match(r"^<!--.*-->$", line.strip()) for line in lines):
            continue

        # Markdown images: ![alt](path)
        if len(lines) == 1 and re.match(r"^!\[.*\]\(.*\)$", lines[0].strip()):
            match = re.match(r"^!\[(.*?)\]\((.*?)\)$", lines[0].strip())
            if match:
                alt, src = match.group(1), match.group(2)
                rendered.append(
                    f'<figure style="margin: 1em 0; text-align: center;">'
                    f'<img src="{html.escape(src)}" alt="{html.escape(alt)}" '
                    f'style="max-width: 100%; height: auto;" />'
                    f'<figcaption style="font-size: 0.9em; color: #6b7280; margin-top: 0.3em;">'
                    f'{html.escape(alt)}</figcaption></figure>'
                )
                continue

        # Filter out any remaining HTML comment lines from mixed blocks
        lines = [l for l in lines if not re.match(r"^<!--.*-->$", l.strip())]
        if not lines:
            continue

        # Pure unordered list
        if all(re.match(r"^[\s]*[-*+]\s+", line) for line in lines):
            rendered.append(_render_list_block(lines))
            continue

        # Pure ordered list
        if all(re.match(r"^[\s]*\d+[.)]\s+", line) for line in lines):
            items = "".join(
                f"<li>{_render_inline_markdown(re.sub(r'^[\s]*\d+[.)]\s+', '', line))}</li>"
                for line in lines
            )
            rendered.append(f"<ol>{items}</ol>")
            continue

        # Heading
        if len(lines) == 1 and (heading := re.match(r"^(#{1,6})\s+(.*)$", lines[0])):
            level = len(heading.group(1))
            text = _render_inline_markdown(heading.group(2))
            rendered.append(f"<h{level}>{text}</h{level}>")
            continue

        # Table (lines starting with |)
        if all(line.startswith("|") for line in lines):
            rendered.append(_render_table_block(lines))
            continue

        # Mixed block: some lines are list items, some are not.
        # Split into runs of list vs non-list and render each.
        has_list = any(re.match(r"^[\s]*[-*+]\s+", line) for line in lines)
        if has_list:
            rendered.extend(_render_mixed_block(lines))
            continue

        paragraph = " ".join(_render_inline_markdown(line) for line in lines)
        rendered.append(f"<p>{paragraph}</p>")

    return "\n".join(rendered)


def _render_list_block(lines: list[str]) -> str:
    """Render a list block, handling nested items (indented lines)."""
    items: list[str] = []
    for line in lines:
        indent = len(line) - len(line.lstrip())
        text = re.sub(r"^[\s]*[-*+]\s+", "", line)
        style = ' style="margin-left: 1.2em;"' if indent >= 4 else ""
        items.append(f"<li{style}>{_render_inline_markdown(text)}</li>")
    return f"<ul>{''.join(items)}</ul>"


def _render_table_block(lines: list[str]) -> str:
    """Render a markdown table as HTML."""
    rows: list[list[str]] = []
    separator_idx = -1
    for i, line in enumerate(lines):
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(re.match(r"^[-:]+$", c) for c in cells):
            separator_idx = i
            continue
        rows.append(cells)

    if not rows:
        return ""

    html_parts = ["<table style='border-collapse: collapse; width: 100%; margin: 0.75em 0;'>"]
    for i, row in enumerate(rows):
        tag = "th" if i == 0 and separator_idx == 1 else "td"
        style = "border: 1px solid #d1d5db; padding: 0.4em 0.7em;"
        if tag == "th":
            style += " background: #f3f4f6; font-weight: bold;"
        cells_html = "".join(f"<{tag} style='{style}'>{_render_inline_markdown(c)}</{tag}>" for c in row)
        html_parts.append(f"<tr>{cells_html}</tr>")
    html_parts.append("</table>")
    return "\n".join(html_parts)


def _render_mixed_block(lines: list[str]) -> list[str]:
    """Split a block with mixed paragraphs and list items into separate elements."""
    result: list[str] = []
    current_para: list[str] = []
    current_list: list[str] = []

    def flush_para():
        if current_para:
            text = " ".join(_render_inline_markdown(l) for l in current_para)
            result.append(f"<p>{text}</p>")
            current_para.clear()

    def flush_list():
        if current_list:
            result.append(_render_list_block(current_list))
            current_list.clear()

    for line in lines:
        if re.match(r"^[\s]*[-*+]\s+", line):
            flush_para()
            current_list.append(line)
        else:
            flush_list()
            current_para.append(line)

    flush_para()
    flush_list()
    return result


def _build_styled_html_document(content: str) -> str:
    body = _markdown_to_html(content)
    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <style>
    @page {{ margin: 0.9in; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #1f2937; line-height: 1.65; font-size: 11pt; }}
    h1, h2, h3, h4, h5, h6 {{ color: #111827; margin: 1.4em 0 0.45em; line-height: 1.2; }}
    h1 {{ font-size: 24pt; border-bottom: 2px solid #e5e7eb; padding-bottom: 0.25em; }}
    h2 {{ font-size: 18pt; border-bottom: 1px solid #e5e7eb; padding-bottom: 0.2em; }}
    h3 {{ font-size: 14pt; }}
    p {{ margin: 0.75em 0; }}
    ul, ol {{ margin: 0.75em 0 0.75em 1.4em; padding: 0; }}
    li {{ margin: 0.35em 0; }}
    code {{ font-family: "SFMono-Regular", "Menlo", monospace; background: #f3f4f6; padding: 0.12em 0.35em; border-radius: 4px; font-size: 0.95em; }}
    strong {{ color: #111827; }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""


def _save_pdf_with_pandoc(markdown_path: Path, pdf_path: Path) -> bool:
    if not shutil.which("pandoc") or not shutil.which("xelatex"):
        return False

    subprocess.run(
        [
            "pandoc",
            str(markdown_path),
            "-o",
            str(pdf_path),
            "--pdf-engine=xelatex",
            "--toc",
            "--syntax-highlighting=pygments",
            "-V",
            "geometry:margin=1in",
        ],
        check=True,
    )
    return True


def _save_pdf_with_weasyprint(content: str, pdf_path: Path) -> None:
    HTML = import_module("weasyprint").HTML
    html_document = _build_styled_html_document(content)
    HTML(string=html_document, base_url=str(OUTPUTS_DIR)).write_pdf(str(pdf_path))


def save_output(content: str, description: str) -> Path:
    """Save content to outputs directory as .md and .pdf."""
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    today = date.today().strftime("%Y-%m-%d")
    slug = slugify(description[:50])  # First 50 chars as slug
    base_name = f"{today}-{slug}"

    # Save markdown
    md_path = OUTPUTS_DIR / f"{base_name}.md"
    md_path.write_text(content, encoding="utf-8")
    logger.info("Saved markdown to %s", md_path)

    pdf_path = OUTPUTS_DIR / f"{base_name}.pdf"
    try:
        try:
            if _save_pdf_with_pandoc(md_path, pdf_path):
                logger.info("Saved PDF to %s", pdf_path)
                return md_path
        except (subprocess.CalledProcessError, OSError) as e:
            logger.warning(
                "Pandoc PDF generation failed, falling back to WeasyPrint: %s", e
            )

        _save_pdf_with_weasyprint(content, pdf_path)
        logger.info("Saved PDF to %s", pdf_path)
    except ImportError:
        logger.debug("weasyprint not installed, skipping PDF")
    except Exception as e:
        logger.warning("Failed to generate PDF: %s", e)

    return md_path


def ask_proceed_mode() -> str:
    """Ask user how they want to proceed."""
    print("\nHow would you like to proceed?")
    print("  [1] Auto-run (use prompt as-is)")
    print("  [2] Answer questions first")
    while True:
        choice = input("\nEnter choice [1-2]: ").strip()
        if choice in ("1", "2"):
            return "2" if choice == "2" else "auto"
        print("Please enter 1 or 2")


def ask_clarification_questions(questions: list, description: str) -> dict[str, str]:
    """Ask clarification questions and collect answers."""
    answers = {}
    print(f"\n{'=' * 50}")
    print(f"Clarification Questions")
    print(f"{'=' * 50}")

    for q in questions:
        print(f"\n{q.question}")
        for i, opt in enumerate(q.options, 1):
            print(f"  [{i}] {opt}")

        while True:
            try:
                choice = input(f"\nEnter choice [1-{len(q.options)}]: ").strip()
                idx = int(choice) - 1
                if 0 <= idx < len(q.options):
                    if idx == len(q.options) - 1:
                        answer = input("  Enter your answer: ").strip()
                        answers[q.id] = answer
                    else:
                        answers[q.id] = q.options[idx]
                    break
                print(f"Please enter a number between 1 and {len(q.options)}")
            except ValueError:
                print("Please enter a number")

    print(f"\n{'=' * 50}")
    print("Thanks! Generating your artifact...")
    print(f"{'=' * 50}\n")

    return answers


async def generate_with_clarification(
    description: str, output_type: str, skip_proceed_prompt: bool = False
) -> dict:
    """Generate with optional clarification questions."""
    from artifactforge.agents.intent_architect import generate_clarification_questions

    if not skip_proceed_prompt:
        proceed_mode = ask_proceed_mode()
        if proceed_mode == "auto":
            return await _run_pipeline(description, output_type, intent_mode="auto")

    questions = generate_clarification_questions(description, output_type)

    if not questions:
        print("Could not generate questions, proceeding with auto mode")
        return await _run_pipeline(description, output_type, intent_mode="auto")

    answers = ask_clarification_questions(questions, description)

    enriched_prompt = f"""{description}

Additional context from user:
"""
    for qid, answer in answers.items():
        enriched_prompt += f"- {answer}\n"

    return await _run_pipeline(
        enriched_prompt,
        output_type,
        intent_mode="interactive",
        answers_collected=answers,
    )


async def _run_pipeline(
    description: str,
    output_type: str,
    intent_mode: str = "auto",
    answers_collected: Optional[dict] = None,
) -> dict:
    """Generate an artifact using the MCRS pipeline."""
    import uuid
    from artifactforge.observability.metrics import get_metrics_collector
    from artifactforge.observability.events import (
        get_event_emitter,
        enable_live_display,
    )

    enable_live_display()

    from artifactforge.db.persistence import get_persistence

    emitter = get_event_emitter()
    trace_id = str(uuid.uuid4())
    emitter.emit_pipeline_start(trace_id, description, output_type)

    metrics = get_metrics_collector()
    await metrics.initialize()
    await metrics.start_pipeline(description, output_type, trace_id=trace_id)

    # Create artifact row in DB (no-op if DATABASE_URL not set)
    persistence = get_persistence()
    artifact_id = persistence.start_run(trace_id, description, output_type)

    # Fetch learnings from prior runs for this artifact type
    learnings_context = persistence.fetch_learnings(
        agent_name="pipeline", artifact_type=output_type
    )

    initial_state = {
        "user_prompt": description,
        "conversation_context": None,
        "output_constraints": {"output_type": output_type},
        "revision_history": [],
        "current_stage": "",
        "errors": [],
        "stage_timing": {},
        "intent_mode": intent_mode,
        "answers_collected": answers_collected or {},
        "trace_id": trace_id,
        "artifact_id": artifact_id,
        "learnings_context": learnings_context,
        "repair_context": None,
    }

    logger.info("Starting MCRS pipeline for %s (%s)", description, output_type)

    result = await cast(Any, app).ainvoke(
        initial_state,
        config={"configurable": {"thread_id": "cli-session", "trace_id": trace_id}},
    )

    from artifactforge.observability.events import get_event_emitter

    emitter = get_event_emitter()
    emitter.emit_pipeline_end(
        trace_id=trace_id,
        success=len(result.get("errors", [])) == 0,
        final_stage=result.get("current_stage"),
    )

    tokens_used = result.get("tokens_used", {})
    costs = result.get("costs", {})
    total_tokens = sum(tokens_used.values()) if isinstance(tokens_used, dict) else 0
    total_cost = sum(costs.values()) if isinstance(costs, dict) else 0.0

    await metrics.complete_pipeline(
        trace_id=trace_id,
        status="completed" if len(result.get("errors", [])) == 0 else "failed",
        final_stage=result.get("current_stage"),
        total_tokens=total_tokens,
        total_cost=total_cost,
    )

    # Persist completion + metrics + learnings to DB
    run_status = "completed" if len(result.get("errors", [])) == 0 else "failed"
    final_draft = result.get("polished_draft") or result.get("draft_v1")
    persistence.complete_run(
        artifact_id=artifact_id or "",
        status=run_status,
        final_draft=final_draft,
        stage_timing=result.get("stage_timing", {}),
        tokens_used=tokens_used if isinstance(tokens_used, dict) else {},
        costs=costs if isinstance(costs, dict) else {},
        release_decision=result.get("release_decision"),
        review_results=result.get("red_team_review"),
        verification_report=result.get("verification_report"),
    )

    # Extract learnings from this run
    persistence.extract_learnings(
        artifact_id=artifact_id or "",
        artifact_type=output_type,
        revision_history=result.get("revision_history", []),
        release_decision=result.get("release_decision"),
        errors=result.get("errors", []),
        red_team_review=result.get("red_team_review"),
    )

    logger.info("Pipeline complete at stage %s", result.get("current_stage"))
    return result


def main():
    """Main CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="artifactory CLI")
    subparsers = parser.add_subparsers(dest="command")

    gen_parser = subparsers.add_parser("generate", help="Generate an artifact")
    gen_parser.add_argument("description", help="What you want to generate")
    gen_parser.add_argument(
        "--type",
        "-t",
        default="report",
        help="Output type: report, blog, slides, memo, technical_writeup, decision_doc",
    )
    gen_parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Answer questions before generating",
    )
    gen_parser.add_argument(
        "--auto",
        "-a",
        action="store_true",
        help="Run automatically without questions",
    )

    args = parser.parse_args()

    if args.command == "generate":
        if args.auto:
            result = asyncio.run(_run_pipeline(args.description, args.type))
        else:
            result = asyncio.run(
                generate_with_clarification(
                    args.description, args.type, skip_proceed_prompt=args.interactive
                )
            )

        content = select_output_content(result)

        if content:
            saved_path = save_output(content, args.description)
            print(f"Saved to: {saved_path}")
            print("\n--- Content ---\n")
            print(content)
        else:
            print(result)


if __name__ == "__main__":
    main()

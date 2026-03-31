import asyncio
import importlib

import pytest

cli_main = importlib.import_module("artifactforge.cli.main")


class _FakeEmitter:
    def __init__(self) -> None:
        self.pipeline_starts: list[tuple[str, str, str]] = []
        self.pipeline_ends: list[tuple[str, bool, str | None]] = []

    def emit_pipeline_start(
        self, trace_id: str, description: str, output_type: str
    ) -> None:
        self.pipeline_starts.append((trace_id, description, output_type))

    def emit_pipeline_end(
        self, trace_id: str, success: bool, final_stage: str | None
    ) -> None:
        self.pipeline_ends.append((trace_id, success, final_stage))


class _FakeMetricsCollector:
    def __init__(self) -> None:
        self.initialize_calls = 0
        self.start_calls: list[tuple[str, str, str | None]] = []
        self.complete_calls: list[dict] = []

    async def initialize(self) -> None:
        self.initialize_calls += 1

    async def start_pipeline(
        self, user_prompt: str, output_type: str, trace_id: str | None = None
    ) -> str:
        self.start_calls.append((user_prompt, output_type, trace_id))
        return trace_id or "generated-trace-id"

    async def complete_pipeline(
        self,
        trace_id: str,
        status: str,
        final_stage: str | None = None,
        total_tokens: int = 0,
        total_cost: float = 0.0,
    ) -> None:
        self.complete_calls.append(
            {
                "trace_id": trace_id,
                "status": status,
                "final_stage": final_stage,
                "total_tokens": total_tokens,
                "total_cost": total_cost,
            }
        )


class _FakeApp:
    def __init__(self, result: dict) -> None:
        self.result = result
        self.calls: list[tuple[dict, dict]] = []

    async def ainvoke(self, initial_state: dict, config: dict) -> dict:
        self.calls.append((initial_state, config))
        return self.result


def _make_fake_weasy_class() -> type:
    """Return a fresh _FakeWeasyHTML class with isolated class-level state."""

    class _FakeWeasyHTML:
        last_string: str | None = None
        last_base_url: str | None = None
        written_paths: list[str] = []

        def __init__(self, string: str, base_url: str | None = None) -> None:
            type(self).last_string = string
            type(self).last_base_url = base_url

        def write_pdf(self, path: str) -> None:
            type(self).written_paths.append(path)

    return _FakeWeasyHTML


@pytest.fixture
def fake_weasy():
    """Provide a fresh _FakeWeasyHTML class per test — no shared mutable state."""
    return _make_fake_weasy_class()


class _CalledProcess:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def run(self, command: list[str], check: bool) -> None:
        self.commands.append(command)


def test_run_pipeline_records_pipeline_metrics(monkeypatch) -> None:
    emitter = _FakeEmitter()
    collector = _FakeMetricsCollector()
    fake_app = _FakeApp(
        {
            "current_stage": "polisher",
            "errors": [],
            "tokens_used": {"draft_writer": 1200, "polisher": 300},
            "costs": {"draft_writer": 0.12, "polisher": 0.03},
        }
    )

    monkeypatch.setattr(cli_main, "app", fake_app)
    monkeypatch.setattr(
        "artifactforge.observability.events.enable_live_display", lambda: None
    )
    monkeypatch.setattr(
        "artifactforge.observability.events.get_event_emitter", lambda: emitter
    )
    monkeypatch.setattr(
        "artifactforge.observability.metrics.get_metrics_collector", lambda: collector
    )

    result = asyncio.run(cli_main._run_pipeline("Build a report", "report"))

    assert result["current_stage"] == "polisher"
    assert collector.initialize_calls == 1
    assert collector.start_calls == [
        ("Build a report", "report", emitter.pipeline_starts[0][0])
    ]
    assert collector.complete_calls == [
        {
            "trace_id": emitter.pipeline_starts[0][0],
            "status": "completed",
            "final_stage": "polisher",
            "total_tokens": 1500,
            "total_cost": 0.15,
        }
    ]


def test_save_output_converts_markdown_to_styled_html_for_pdf(
    monkeypatch, tmp_path, fake_weasy
) -> None:
    markdown = "# Title\n\nA **bold** paragraph.\n\n- First\n- Second"

    class _FakeModule:
        HTML = fake_weasy

    monkeypatch.setattr(cli_main, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(cli_main.shutil, "which", lambda name: None)
    monkeypatch.setattr(cli_main, "import_module", lambda name: _FakeModule)

    saved_path = cli_main.save_output(markdown, "Styled PDF Example")

    assert saved_path == next(tmp_path.glob("*.md"))
    assert fake_weasy.last_string is not None
    assert "<html" in fake_weasy.last_string
    assert "<h1>Title</h1>" in fake_weasy.last_string
    assert "<strong>bold</strong>" in fake_weasy.last_string
    assert "<li>First</li>" in fake_weasy.last_string
    assert "font-family" in fake_weasy.last_string
    assert fake_weasy.last_base_url == str(tmp_path)
    assert len(fake_weasy.written_paths) == 1


def test_save_output_prefers_pandoc_for_pdf_generation(monkeypatch, tmp_path) -> None:
    runner = _CalledProcess()
    markdown = "# Title\n\n- First\n- Second"

    monkeypatch.setattr(cli_main, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(
        cli_main.shutil,
        "which",
        lambda name: (
            f"/usr/local/bin/{name}" if name in {"pandoc", "xelatex"} else None
        ),
    )
    monkeypatch.setattr(cli_main.subprocess, "run", runner.run)
    monkeypatch.setattr(
        cli_main,
        "import_module",
        lambda name: (_ for _ in ()).throw(
            AssertionError("weasyprint fallback should not run")
        ),
    )

    saved_path = cli_main.save_output(markdown, "Pandoc PDF Example")

    assert runner.commands == [
        [
            "pandoc",
            str(saved_path),
            "-o",
            str(saved_path.with_suffix(".pdf")),
            "--pdf-engine=xelatex",
            "--toc",
            "--syntax-highlighting=pygments",
            "-V",
            "geometry:margin=1in",
        ]
    ]


def test_save_output_falls_back_to_weasyprint_when_pandoc_generation_fails(
    monkeypatch, tmp_path, fake_weasy
) -> None:
    markdown = "# Title\n\n- First\n- Second"

    class _FakeModule:
        HTML = fake_weasy

    monkeypatch.setattr(cli_main, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(
        cli_main.shutil,
        "which",
        lambda name: (
            f"/usr/local/bin/{name}" if name in {"pandoc", "xelatex"} else None
        ),
    )

    def fail_pandoc(command: list[str], check: bool) -> None:
        raise cli_main.subprocess.CalledProcessError(returncode=1, cmd=command)

    monkeypatch.setattr(cli_main.subprocess, "run", fail_pandoc)
    monkeypatch.setattr(cli_main, "import_module", lambda name: _FakeModule)

    saved_path = cli_main.save_output(markdown, "Fallback PDF Example")

    assert saved_path == next(tmp_path.glob("*.md"))
    assert fake_weasy.last_string is not None
    assert "<html" in fake_weasy.last_string
    assert "<li>First</li>" in fake_weasy.last_string
    assert fake_weasy.last_base_url == str(tmp_path)
    assert len(fake_weasy.written_paths) == 1


def test_select_output_content_falls_back_to_draft_when_polish_is_truncated() -> None:
    draft = "# Investment Analysis Report\n\n## 1. Executive Summary\nFull section\n\n## 2. Opportunity Overview\nFull section\n\n## 3. Risks\nFull section"
    broken_polish = "# Investment Analysis Report\n\n## 1. Executive Summary\nShort summary\n\n## 2. Opportunity Overview\nThe concept relies on providing authentic cuisine to a market with"

    selected = cli_main.select_output_content(
        {"draft_v1": draft, "polished_draft": broken_polish}
    )

    assert selected == draft


def test_select_output_content_keeps_valid_markdown_polish_without_terminal_punctuation() -> (
    None
):
    draft = "# Investment Analysis Report\n\n## Executive Summary\nComplete summary.\n\n## Key Risks\n- Supply volatility.\n- Margin pressure."
    polished = "# Investment Analysis Report\n\n## Executive Summary\nRefined summary.\n\n## Key Risks\n- Supply volatility\n- Margin pressure"

    selected = cli_main.select_output_content(
        {"draft_v1": draft, "polished_draft": polished}
    )

    assert selected == polished


def test_run_pipeline_passes_intent_metadata_to_graph(monkeypatch) -> None:
    emitter = _FakeEmitter()
    collector = _FakeMetricsCollector()
    fake_app = _FakeApp({"current_stage": "intent_architect", "errors": []})

    monkeypatch.setattr(cli_main, "app", fake_app)
    monkeypatch.setattr(
        "artifactforge.observability.events.enable_live_display", lambda: None
    )
    monkeypatch.setattr(
        "artifactforge.observability.events.get_event_emitter", lambda: emitter
    )
    monkeypatch.setattr(
        "artifactforge.observability.metrics.get_metrics_collector", lambda: collector
    )
    asyncio.run(
        cli_main._run_pipeline(
            "Build a report",
            "report",
            intent_mode="interactive",
            answers_collected={"q1": "Executive audience"},
        )
    )

    initial_state, _config = fake_app.calls[0]
    assert initial_state["intent_mode"] == "interactive"
    assert initial_state["answers_collected"] == {"q1": "Executive audience"}
    assert initial_state["trace_id"] == emitter.pipeline_starts[0][0]
    assert initial_state["repair_context"] is None

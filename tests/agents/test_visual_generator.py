from artifactforge.agents.visual_generator import (
    run_visual_generator,
    _generate_mermaid,
    _generate_python,
    _build_matplotlib_code,
)


class TestBuildMatplotlibCode:
    def test_bar_chart_code(self):
        data_spec = {
            "data": {"values": [10, 20, 30]},
            "labels": ["A", "B", "C"],
        }
        code = _build_matplotlib_code("bar_chart", data_spec, "Test Chart", "V001")
        assert "bar" in code
        assert "10" in code
        assert "Test Chart" in code
        assert "visual_V001" in code

    def test_line_chart_code(self):
        data_spec = {
            "data": {"x": [1, 2, 3], "y": [4, 5, 6]},
            "labels": [],
        }
        code = _build_matplotlib_code("line_chart", data_spec, "Line", "V002")
        assert "plot" in code
        assert "marker='o'" in code

    def test_pie_chart_code(self):
        data_spec = {
            "data": {"values": [25, 50, 25]},
            "labels": ["A", "B", "C"],
        }
        code = _build_matplotlib_code("pie_chart", data_spec, "Pie", "V003")
        assert "pie" in code
        assert "autopct" in code

    def test_scatter_plot_code(self):
        data_spec = {
            "data": {"x": [1, 2], "y": [3, 4]},
            "labels": [],
        }
        code = _build_matplotlib_code("scatter_plot", data_spec, "Scatter", "V004")
        assert "scatter" in code
        assert "alpha=0.6" in code

    def test_unknown_type_fallback(self):
        code = _build_matplotlib_code("unknown_type", {}, "Fallback", "V005")
        assert "subplots" in code
        assert "Fallback" in code


class TestGenerateMermaid:
    def test_successful_mermaid_render(self, monkeypatch):
        import sys
        import types

        fake_mermaid = types.ModuleType("mermaid")
        fake_mermaid.render = lambda code: "<svg>rendered</svg>"
        monkeypatch.setitem(sys.modules, "mermaid", fake_mermaid)

        spec = {
            "visual_id": "V001",
            "visual_type": "flowchart",
            "mermaid_code": "graph TD; A-->B;",
        }
        result = _generate_mermaid(spec)
        assert result["visual_id"] == "V001"
        assert result["generation_method"] == "mermaid"
        assert result["svg_output"] == "<svg>rendered</svg>"

    def test_mermaid_failure(self, monkeypatch):
        import sys
        import types

        fake_mermaid = types.ModuleType("mermaid")
        fake_mermaid.render = lambda code: (_ for _ in ()).throw(
            RuntimeError("Render failed")
        )
        monkeypatch.setitem(sys.modules, "mermaid", fake_mermaid)

        spec = {
            "visual_id": "V001",
            "visual_type": "flowchart",
            "mermaid_code": "invalid code",
        }
        result = _generate_mermaid(spec)
        assert "failed" in result["notes"]
        assert result["svg_output"] is None

    def test_no_mermaid_code_returns_error(self):
        spec = {
            "visual_id": "V001",
            "visual_type": "flowchart",
            "mermaid_code": "",
        }
        result = _generate_mermaid(spec)
        assert "No Mermaid code provided" in result["notes"]


class TestGeneratePython:
    def test_generates_bar_chart(self):
        spec = {
            "visual_id": "V001",
            "visual_type": "bar_chart",
            "title": "Sales",
            "data_spec": {
                "data": {"values": [10, 20, 30]},
                "labels": ["A", "B", "C"],
            },
        }
        result = _generate_python(spec)
        assert result["visual_id"] == "V001"
        assert result["visual_type"] == "bar_chart"
        assert result["generation_method"] == "python"
        assert result["generated_code"] is not None
        assert "bar" in result["generated_code"]


class TestRunVisualGenerator:
    def test_empty_specs_returns_empty(self):
        result = run_visual_generator(visual_specs=[])
        assert result == []

    def test_simple_mermaid_spec(self, monkeypatch):
        import sys
        import types

        fake_mermaid = types.ModuleType("mermaid")
        fake_mermaid.render = lambda code: "<svg>ok</svg>"
        monkeypatch.setitem(sys.modules, "mermaid", fake_mermaid)

        specs = [
            {
                "visual_id": "V001",
                "visual_type": "flowchart",
                "complexity": "SIMPLE",
                "mermaid_code": "graph TD; A-->B;",
            }
        ]
        result = run_visual_generator(visual_specs=specs)
        assert len(result) == 1
        assert result[0]["generation_method"] == "mermaid"

    def test_filters_by_approved_reviews(self, monkeypatch):
        import sys
        import types

        fake_mermaid = types.ModuleType("mermaid")
        fake_mermaid.render = lambda code: "<svg>ok</svg>"
        monkeypatch.setitem(sys.modules, "mermaid", fake_mermaid)

        specs = [
            {
                "visual_id": "V001",
                "visual_type": "flowchart",
                "complexity": "SIMPLE",
                "mermaid_code": "graph TD; A-->B;",
            },
            {
                "visual_id": "V002",
                "visual_type": "flowchart",
                "complexity": "SIMPLE",
                "mermaid_code": "graph TD; C-->D;",
            },
        ]
        reviews = [
            {"visual_id": "V001", "is_appropriate": True},
            {"visual_id": "V002", "is_appropriate": False},
        ]
        result = run_visual_generator(visual_specs=specs, approved_reviews=reviews)
        assert len(result) == 1
        assert result[0]["visual_id"] == "V001"

    def test_processes_all_approved_specs(self, monkeypatch):
        import sys
        import types

        fake_mermaid = types.ModuleType("mermaid")
        fake_mermaid.render = lambda code: "<svg>ok</svg>"
        monkeypatch.setitem(sys.modules, "mermaid", fake_mermaid)

        specs = [
            {
                "visual_id": "V001",
                "visual_type": "flowchart",
                "complexity": "SIMPLE",
                "mermaid_code": "graph TD; A-->B;",
            },
            {
                "visual_id": "V002",
                "visual_type": "timeline",
                "complexity": "SIMPLE",
                "mermaid_code": "gantt; title Timeline;",
            },
        ]
        result = run_visual_generator(visual_specs=specs)
        assert len(result) == 2

    def test_contract_is_registered(self):
        from artifactforge.coordinator.contracts import (
            VISUAL_GENERATOR_CONTRACT,
            AGENT_REGISTRY,
        )

        assert "visual_generator" in AGENT_REGISTRY
        assert VISUAL_GENERATOR_CONTRACT.name == "visual_generator"

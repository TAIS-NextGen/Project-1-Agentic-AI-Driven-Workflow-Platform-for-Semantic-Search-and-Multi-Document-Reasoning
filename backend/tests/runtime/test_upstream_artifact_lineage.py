from __future__ import annotations

from backend.runtime.executor import WorkflowExecutor
from backend.runtime.graph import WorkflowGraph
from backend.sdk import NodeResult


def successful_result(node_id: str, outputs: dict) -> NodeResult:
    result = NodeResult(node_id)
    result.start()
    result.succeed(outputs)
    return result


def test_executor_exposes_nearest_upstream_outputs_first():
    graph = WorkflowGraph()
    graph.add_node("input", "document-upload")
    graph.add_node("converter", "file-converter")
    graph.add_node("parser", "document-parser")
    graph.add_edge("input", "document", "converter", "document")
    # Simulate an older UI edge that used generic ports. The parser lineage must
    # still see converter outputs even if the direct port lookup returns nothing.
    graph.add_edge("converter", "output", "parser", "document")

    executor = WorkflowExecutor(graph)
    executor._results = {
        "input": successful_result("input", {"document": {"path": "original.docx"}}),
        "converter": successful_result("converter", {"converted_path": "latest.pdf", "text": ""}),
    }

    inputs = executor._resolve_inputs("parser")
    lineage = inputs["__upstream_artifacts__"]
    input_sources = inputs["__input_sources__"]

    assert inputs.get("document") is None
    assert input_sources == []
    assert lineage[0]["source_node_id"] == "converter"
    assert lineage[0]["output_port"] == "converted_path"
    assert lineage[0]["distance"] == 1
    assert any(item["source_node_id"] == "input" and item["distance"] == 2 for item in lineage)


def test_executor_reports_the_direct_input_source_and_ports():
    graph = WorkflowGraph()
    graph.add_node("parser", "document-parser")
    graph.add_node("dates", "date-normalizer")
    graph.add_edge("parser", "text", "dates", "text")

    executor = WorkflowExecutor(graph)
    executor._results = {
        "parser": successful_result("parser", {"text": "Rendez-vous le 12/08/2026"}),
    }

    inputs = executor._resolve_inputs("dates")

    assert inputs["text"] == "Rendez-vous le 12/08/2026"
    assert inputs["__input_sources__"] == [
        {
            "source_node_id": "parser",
            "source_node_type": "document-parser",
            "source_port": "text",
            "target_port": "text",
        }
    ]

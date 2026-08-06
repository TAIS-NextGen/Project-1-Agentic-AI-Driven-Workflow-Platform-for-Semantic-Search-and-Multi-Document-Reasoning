from __future__ import annotations

import json
from typing import Any

from backend.sdk import (
    BaseNode,
    ConfigField,
    ExecutionContext,
    NodeRegistry,
    NodeResult,
    NodeStatus,
    Port,
    PortType,
)
from backend.runtime.executor import WorkflowExecutor
from backend.runtime.graph import WorkflowGraph
from backend.runtime.scheduler import WorkflowScheduler


class ForEachNode(BaseNode):
    type = "for-each"
    name = "For Each"
    category = "orchestration"
    icon = "🔄"
    color = "#a855f7"
    description = "Run a subgraph once per document in a collection, injecting each document into the first node"
    version = "1.0.0"

    inputs = [
        Port(
            name="documents",
            type=PortType.DOCUMENT_COLLECTION,
            label="Documents",
            description="Collection of documents to iterate over",
            required=True,
        ),
    ]

    outputs = [
        Port(
            name="results",
            type=PortType.JSON,
            label="Results",
            description="Array of per-document execution results",
        ),
        Port(
            name="succeeded",
            type=PortType.JSON,
            label="Succeeded",
            description="Number of documents processed successfully",
        ),
        Port(
            name="failed",
            type=PortType.JSON,
            label="Failed",
            description="Number of documents that failed processing",
        ),
        Port(
            name="total",
            type=PortType.JSON,
            label="Total",
            description="Total number of documents processed",
        ),
    ]

    config_fields = [
        ConfigField(
            key="subgraph_template",
            label="Subgraph Template",
            type="json",
            required=True,
            default={"nodes": [], "edges": []},
            description="WorkflowGraph dict defining nodes and edges to run per document. Node IDs will be suffixed with iteration index.",
        ),
    ]

    def _parse_subgraph_template(self, template: Any) -> dict[str, Any]:
        if isinstance(template, str):
            return json.loads(template)
        if isinstance(template, dict):
            return template
        return {"nodes": [], "edges": []}

    def _find_root_nodes(self, template: dict[str, Any]) -> list[str]:
        all_node_ids = {n["id"] for n in template.get("nodes", [])}
        target_ids = {e.get("target", e["target"]) for e in template.get("edges", [])}
        return sorted(all_node_ids - target_ids)

    def _build_indexed_subgraph(self, template: dict[str, Any], index: int) -> WorkflowGraph:
        indexed_nodes = []
        for n in template.get("nodes", []):
            indexed_nodes.append({
                "id": f"{n['id']}-{index}",
                "type": n["type"],
                "config": n.get("config", {}),
            })

        indexed_edges = []
        for e in template.get("edges", []):
            indexed_edges.append({
                "source": f"{e['source']}-{index}",
                "source_port": e.get("source_port", "output"),
                "target": f"{e['target']}-{index}",
                "target_port": e.get("target_port", "input"),
            })

        return WorkflowGraph.from_dict({"nodes": indexed_nodes, "edges": indexed_edges})

    def _get_root_node_id(self, subgraph: WorkflowGraph, template_root_ids: list[str], index: int) -> str:
        if template_root_ids:
            candidate = f"{template_root_ids[0]}-{index}"
            if subgraph.get_node(candidate):
                return candidate

        ordered = WorkflowScheduler(subgraph).topological_sort()
        if ordered:
            return ordered[0]
        return ""

    async def _execute_iteration(
        self,
        document: dict[str, Any],
        subgraph: WorkflowGraph,
        root_node_id: str,
        index: int,
    ) -> dict[str, Any]:
        node_results: dict[str, Any] = {}
        registry = NodeRegistry()

        if not root_node_id:
            return {"error": "No root node found in subgraph", "node_results": {}}

        root_node = subgraph.get_node(root_node_id)
        root_cls = registry.get(root_node.node_type)
        if not root_cls:
            return {"error": f"Unknown node type '{root_node.node_type}'", "node_results": {}}

        root_instance = root_cls(node_id=root_node_id, config=root_node.config)
        root_ctx = ExecutionContext(
            workflow_id=f"{self.node_id}-{index}",
            node_id=root_node_id,
            inputs={"document": document},
            config=root_node.config,
        )
        root_result = await root_instance.execute(root_ctx)

        executor = WorkflowExecutor(subgraph, registry)
        executor._build_node_map()
        executor._results = {root_node_id: root_result}

        node_results[root_node_id] = root_result

        scheduler = WorkflowScheduler(subgraph)
        ordered = scheduler.topological_sort()

        for nid in ordered:
            if nid == root_node_id:
                continue
            try:
                r = await executor.execute_node(nid)
                node_results[nid] = r
            except Exception as exc:
                nr = NodeResult(node_id=nid)
                nr.fail(str(exc))
                node_results[nid] = nr

        return {"node_results": {nid: r.to_dict() for nid, r in node_results.items()}}

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            collection: list[dict[str, Any]] = ctx.get_input("documents") or []
            config = self.get_resolved_config()
            template = self._parse_subgraph_template(config.get("subgraph_template", {}))

            if not collection:
                result.succeed({"results": [], "succeeded": 0, "failed": 0, "total": 0})
                return result

            if not template.get("nodes"):
                result.fail("Subgraph template has no nodes defined")
                return result

            root_ids = self._find_root_nodes(template)
            all_results: list[dict[str, Any]] = []
            succeeded = 0
            failed = 0

            for i, document in enumerate(collection):
                try:
                    subgraph = self._build_indexed_subgraph(template, i)
                    root_node_id = self._get_root_node_id(subgraph, root_ids, i)

                    iteration_result = await self._execute_iteration(document, subgraph, root_node_id, i)

                    if "error" in iteration_result:
                        failed += 1
                        all_results.append({
                            "document": document,
                            "node_results": iteration_result.get("node_results", {}),
                            "error": iteration_result["error"],
                            "succeeded": 0,
                            "failed": 1,
                        })
                    else:
                        any_failed = any(
                            r.get("status") == "failure"
                            for r in iteration_result.get("node_results", {}).values()
                            if isinstance(r, dict)
                        )
                        if any_failed:
                            failed += 1
                        else:
                            succeeded += 1

                        all_results.append({
                            "document": document,
                            "node_results": iteration_result["node_results"],
                            "succeeded": 0 if any_failed else 1,
                            "failed": 1 if any_failed else 0,
                        })
                except Exception as exc:
                    failed += 1
                    all_results.append({
                        "document": document,
                        "node_results": {},
                        "error": str(exc),
                        "succeeded": 0,
                        "failed": 1,
                    })

            result.succeed({
                "results": all_results,
                "succeeded": succeeded,
                "failed": failed,
                "total": len(collection),
            })

        except Exception as e:
            result.fail(str(e))

        return result

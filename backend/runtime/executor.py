from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from backend.sdk import (
    BaseNode,
    ExecutionContext,
    NodeRegistry,
    NodeResult,
    NodeStatus,
)
from backend.sdk.exceptions import NodeExecutionError

from .graph import WorkflowGraph
from .scheduler import WorkflowScheduler
from .validator import WorkflowValidator


class WorkflowExecutor:
    def __init__(
        self,
        graph: WorkflowGraph,
        registry: NodeRegistry | None = None,
        services: dict[str, Any] | None = None,
    ):
        self.graph = graph
        self.registry = registry or NodeRegistry()
        self.services = services or {}
        self.logger = logging.getLogger("workflow.executor")
        self._node_map: dict[str, type[BaseNode]] = {}
        self._results: dict[str, NodeResult] = {}

    def _build_node_map(self) -> None:
        self._node_map = {}
        for n in self.graph.nodes.values():
            cls = self.registry.get(n.node_type)
            if cls is None:
                raise NodeExecutionError(n.node_type, n.node_id,
                                         f"Unknown node type '{n.node_type}'")
            self._node_map[n.node_id] = cls

    def validate(self, mode: str = "strict") -> list[str]:
        self._build_node_map()
        validator = WorkflowValidator(self.graph, self._node_map)
        return validator.validate(mode)

    def _resolve_inputs(self, node_id: str) -> dict[str, Any]:
        inputs: dict[str, Any] = {}
        incoming, _ = self.graph.get_edges(node_id)
        for edge in incoming:
            source_result = self._results.get(edge.source_id)
            if source_result and source_result.status == NodeStatus.SUCCESS:
                value = source_result.get_output(edge.source_port)
                inputs[edge.target_port] = value
        return inputs

    def _create_context(self, node_id: str, node_cls: type[BaseNode],
                        config: dict[str, Any]) -> ExecutionContext:
        resolved_inputs = self._resolve_inputs(node_id)
        return ExecutionContext(
            workflow_id=self.graph.to_dict().get("id", "unknown"),
            node_id=node_id,
            inputs=resolved_inputs,
            config=config,
            logger=self.logger,
            services=self.services,
            metadata={"started_at": datetime.utcnow().isoformat()},
        )

    async def execute_node(self, node_id: str) -> NodeResult:
        node_def = self.graph.get_node(node_id)
        if not node_def:
            raise ValueError(f"Node '{node_id}' not found in graph")

        cls = self.registry.get(node_def.node_type)
        if not cls:
            raise NodeExecutionError(node_def.node_type, node_id,
                                     f"Unknown node type '{node_def.node_type}'")

        instance = cls(node_id=node_id, config=node_def.config)
        ctx = self._create_context(node_id, cls, node_def.config)

        self.logger.info(f"Executing node '{node_id}' ({instance.name})")
        result = await instance.execute(ctx)
        self._results[node_id] = result
        self.logger.info(f"Node '{node_id}' completed: {result.status.value}")
        return result

    async def execute(self, validate_mode: str = "strict") -> dict[str, NodeResult]:
        self._results = {}
        self._build_node_map()

        if validate_mode:
            errors = self.validate(validate_mode)
            if errors:
                self.logger.error(f"Validation failed: {errors}")
                for nid in self.graph.nodes:
                    r = NodeResult(nid)
                    r.fail("; ".join(errors))
                    self._results[nid] = r
                return self._results

        scheduler = WorkflowScheduler(self.graph)
        groups = scheduler.parallel_groups()

        for group in groups:
            tasks = [self.execute_node(nid) for nid in group]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for nid, res in zip(group, results):
                if isinstance(res, Exception):
                    r = NodeResult(nid)
                    r.fail(str(res))
                    self._results[nid] = r

                if nid in self.graph.nodes:
                    node_def = self.graph.get_node(nid)
                    if node_def and node_def.node_type in ("planner", "router"):
                        await self._handle_dynamic_subgraph(nid)

        return self._results

    async def _handle_dynamic_subgraph(self, planner_node_id: str) -> None:
        result = self._results.get(planner_node_id)
        if not result or result.status != NodeStatus.SUCCESS:
            return

        subgraph_data = result.get_output("subgraph")
        if not subgraph_data:
            return

        try:
            subgraph = WorkflowGraph.from_dict(subgraph_data)
            for n in subgraph.nodes.values():
                if n.node_id not in self.graph.nodes:
                    self.graph.add_node(n.node_id, n.node_type, n.config)
            for e in subgraph.edges:
                self.graph.add_dynamic_edge(
                    e.source_id, e.source_port,
                    e.target_id, e.target_port
                )

            sub_executor = WorkflowExecutor(self.graph, self.registry, self.services)
            sub_executor._results = self._results
            sub_executor._node_map = self._node_map

            scheduler = WorkflowScheduler(subgraph)
            try:
                ordered = scheduler.topological_sort()
            except ValueError:
                self.logger.warning(f"Dynamic sub-graph from '{planner_node_id}' contains a cycle")
                return

            for nid in ordered:
                if nid not in self._results:
                    await sub_executor.execute_node(nid)
        except Exception as e:
            self.logger.error(f"Failed to execute dynamic sub-graph from '{planner_node_id}': {e}")

    def get_result(self, node_id: str) -> NodeResult | None:
        return self._results.get(node_id)

    @property
    def results(self) -> dict[str, NodeResult]:
        return dict(self._results)

    @property
    def is_complete(self) -> bool:
        if not self._results:
            return False
        for n in self.graph.nodes:
            r = self._results.get(n)
            if not r or r.status in (NodeStatus.PENDING, NodeStatus.RUNNING):
                return False
        return True

    @property
    def has_errors(self) -> bool:
        return any(
            r.status == NodeStatus.FAILURE
            for r in self._results.values()
        )
